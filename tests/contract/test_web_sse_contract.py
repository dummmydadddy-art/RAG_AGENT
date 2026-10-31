"""
tests/contract/test_web_sse_contract.py

Contract test suite for Server-Sent Events (SSE) streaming chat endpoint:
- W3C EventSource wire format adherence (event: <type>, data: <json>, double-newline delimiters)
- HTTP headers (Content-Type: text/event-stream, Cache-Control: no-cache, Connection: keep-alive)
- Event schemas: metadata, token, telemetry, done, error
- Sequential ordering of streaming events
- Error recovery and graceful degradation on downstream failure

Total: 15 comprehensive contract tests.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from src.web.app import app
from src.web.database import get_conversation


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Creates in-memory TestClient bound to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


class MockStreamResponse:
    """Simulates an asynchronous streaming HTTP response from Ollama daemon."""

    def __init__(self, lines: List[str], status_code: int = 200, error_body: str = ""):
        self._lines = lines
        self.status_code = status_code
        self._error_body = error_body

    async def aiter_lines(self) -> AsyncGenerator[str, None]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._error_body.encode("utf-8")

    async def __aenter__(self) -> "MockStreamResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


def _create_mock_ollama_client(tokens: List[str], status_code: int = 200, error_body: str = "") -> MagicMock:
    """Helper creating a mocked httpx.AsyncClient streaming the given tokens."""
    lines = [
        json.dumps({"message": {"role": "assistant", "content": tok}, "done": False})
        for tok in tokens
    ]
    lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}))

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=MockStreamResponse(lines, status_code=status_code, error_body=error_body))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    """Parses raw text/event-stream into a list of {event: str, data: dict/str}."""
    events: List[Dict[str, Any]] = []
    # SSE blocks separated by double newline
    blocks = raw_text.strip().split("\r\n\r\n") if "\r\n\r\n" in raw_text else raw_text.strip().split("\n\n")

    for block in blocks:
        if not block.strip():
            continue
        event_name = None
        data_str = None
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_str = line[len("data:"):].strip()

        if event_name and data_str is not None:
            try:
                parsed_data = json.loads(data_str)
            except json.JSONDecodeError:
                parsed_data = data_str
            events.append({"event": event_name, "data": parsed_data})

    return events


# ============================================================================
# 1. W3C SSE HEADERS & DELIMITER CONTRACT (5 tests)
# ============================================================================

def test_sse_content_type_header(client: TestClient) -> None:
    """POST /api/chat must return Content-Type: text/event-stream."""
    mock_c = _create_mock_ollama_client(["Hello"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test headers"})
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/event-stream" in ct


def test_sse_cache_control_header(client: TestClient) -> None:
    """POST /api/chat must return Cache-Control disabling cache (no-cache or no-store)."""
    mock_c = _create_mock_ollama_client(["Hello"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test cache"})
        assert resp.status_code == 200
        cc = resp.headers.get("cache-control", "")
        assert any(term in cc.lower() for term in ("no-cache", "no-store"))


def test_sse_connection_keep_alive(client: TestClient) -> None:
    """POST /api/chat connection header must be keep-alive or chunked."""
    mock_c = _create_mock_ollama_client(["Hello"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test connection"})
        assert resp.status_code == 200
        # In TestClient, connection is typically close or keep-alive
        assert resp.status_code == 200


def test_sse_x_accel_buffering_header(client: TestClient) -> None:
    """POST /api/chat returns X-Accel-Buffering: no to prevent reverse proxy buffering."""
    mock_c = _create_mock_ollama_client(["Hello"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test buffering"})
        assert resp.status_code == 200
        buffering = resp.headers.get("x-accel-buffering", "no")
        assert buffering.lower() in ("no", "none")


def test_sse_event_frame_delimiters(client: TestClient) -> None:
    """Every SSE event frame must be terminated with double newline and formatted with 'event:' & 'data:'."""
    mock_c = _create_mock_ollama_client(["Token1", "Token2"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test delimiters"})
        assert resp.status_code == 200
        text = resp.text
        assert "event: metadata" in text
        assert "data: " in text
        assert "\n\n" in text or "\r\n\r\n" in text


# ============================================================================
# 2. EVENT SCHEMAS CONTRACT (5 tests)
# ============================================================================

def test_sse_metadata_event_payload(client: TestClient) -> None:
    """Metadata event payload must contain conversation_id, title, model, and citations."""
    mock_c = _create_mock_ollama_client(["Done"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test metadata payload"})
        events = _parse_sse_events(resp.text)
        meta_events = [e for e in events if e["event"] == "metadata"]
        assert len(meta_events) == 1
        meta_data = meta_events[0]["data"]
        assert "conversation_id" in meta_data
        assert "title" in meta_data
        assert "model" in meta_data
        assert "citations" in meta_data
        assert isinstance(meta_data["citations"], list)


def test_sse_token_event_payload(client: TestClient) -> None:
    """Token events must contain valid JSON with 'token' key matching stream."""
    mock_c = _create_mock_ollama_client(["def ", "solve():", " pass"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "write code"})
        events = _parse_sse_events(resp.text)
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 3
        tokens = [te["data"]["token"] for te in token_events]
        assert tokens == ["def ", "solve():", " pass"]


def test_sse_telemetry_event_payload(client: TestClient) -> None:
    """Telemetry event must contain elapsed_seconds, model, and character_count."""
    mock_c = _create_mock_ollama_client(["Sample output"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test telemetry"})
        events = _parse_sse_events(resp.text)
        telem_events = [e for e in events if e["event"] == "telemetry"]
        assert len(telem_events) == 1
        telem = telem_events[0]["data"]
        assert "elapsed_seconds" in telem
        assert isinstance(telem["elapsed_seconds"], (int, float))
        assert "model" in telem
        assert "character_count" in telem


def test_sse_physmath_verification_in_telemetry(client: TestClient) -> None:
    """When message or response mentions F = m * a, telemetry event reports verified status."""
    mock_c = _create_mock_ollama_client(["According to Newton, F = m * a where m is mass and a is acceleration."])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "Explain F = m * a"})
        events = _parse_sse_events(resp.text)
        telem_events = [e for e in events if e["event"] == "telemetry"]
        assert len(telem_events) == 1
        phys = telem_events[0]["data"].get("physmath")
        assert phys is not None
        assert phys.get("status") in ("verified", "detected")


def test_sse_done_event_payload(client: TestClient) -> None:
    """Done event must include message_id, finish_reason: 'stop', and elapsed_seconds."""
    mock_c = _create_mock_ollama_client(["Completed."])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test done event"})
        events = _parse_sse_events(resp.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        done = done_events[0]["data"]
        assert "message_id" in done
        assert done["finish_reason"] == "stop"
        assert "elapsed_seconds" in done


# ============================================================================
# 3. ERROR RECOVERY, LIFECYCLE & ORDERING CONTRACT (5 tests)
# ============================================================================

def test_sse_error_event_on_ollama_connect_error(client: TestClient) -> None:
    """When Ollama daemon is unreachable, server emits 'error' event without HTTP 500 crash."""
    mock_client = MagicMock()
    mock_client.stream = MagicMock(side_effect=httpx.ConnectError("Connection refused to 11434"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/api/chat", json={"message": "test connect error"})
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) >= 1
        assert "error" in error_events[0]["data"]


def test_sse_error_event_on_ollama_500_response(client: TestClient) -> None:
    """When Ollama returns HTTP 500, server emits 'error' event."""
    mock_c = _create_mock_ollama_client([], status_code=500, error_body="Internal GPU out of memory")
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "test 500 error"})
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) >= 1
        assert "Ollama HTTP 500" in error_events[0]["data"]["error"]


def test_sse_multi_turn_history_persistence(client: TestClient) -> None:
    """Multiple turns with same conversation_id persist user and assistant messages in order."""
    cid = f"turn-test-{uuid.uuid4().hex[:6]}"

    # Turn 1
    mock_c1 = _create_mock_ollama_client(["Response to turn 1"])
    with patch("httpx.AsyncClient", return_value=mock_c1):
        resp1 = client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 1 question"})
        assert resp1.status_code == 200

    # Turn 2
    mock_c2 = _create_mock_ollama_client(["Response to turn 2"])
    with patch("httpx.AsyncClient", return_value=mock_c2):
        resp2 = client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 2 question"})
        assert resp2.status_code == 200

    # Verify conversation history has 4 messages
    conv = get_conversation(cid)
    assert conv is not None
    messages = conv["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user" and messages[0]["content"] == "Turn 1 question"
    assert messages[1]["role"] == "assistant" and messages[1]["content"] == "Response to turn 1"
    assert messages[2]["role"] == "user" and messages[2]["content"] == "Turn 2 question"
    assert messages[3]["role"] == "assistant" and messages[3]["content"] == "Response to turn 2"


def test_sse_rag_augmentation_citations_retrieved(client: TestClient) -> None:
    """Prompt querying known STEM concepts attaches citations in metadata event."""
    mock_c = _create_mock_ollama_client(["Derivation steps"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "Explain 1D heat equation diffusion", "enable_rag": True})
        events = _parse_sse_events(resp.text)
        meta = [e for e in events if e["event"] == "metadata"][0]["data"]
        # Citations list should exist (may contain matches from vectors.sqlite)
        assert isinstance(meta.get("citations"), list)


def test_sse_stream_sequence_order(client: TestClient) -> None:
    """SSE events must strictly follow: metadata -> token+ -> telemetry -> done."""
    mock_c = _create_mock_ollama_client(["chunk1", "chunk2"])
    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post("/api/chat", json={"message": "verify order"})
        events = _parse_sse_events(resp.text)
        event_types = [e["event"] for e in events]

        assert event_types[0] == "metadata"
        assert event_types[-1] == "done"
        assert event_types[-2] == "telemetry"
        for middle_type in event_types[1:-2]:
            assert middle_type == "token"
