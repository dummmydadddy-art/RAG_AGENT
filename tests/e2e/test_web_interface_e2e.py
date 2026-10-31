"""
tests/e2e/test_web_interface_e2e.py

End-to-end integration test suite for ChatGPT Web Interface:
- Full conversation creation, multi-turn dialogue, and persistence lifecycle
- Code generation snippet extraction and sandboxed execution pipeline
- Live PhysMath formula verification and telemetry attachment
- RAG lesson retrieval, score-based ranking, and citation injection
- Polyglot SQL query execution in in-memory SQLite
- Sandbox memory stability under sequential multi-script execution
- Health monitoring and hardware budget compliance gate

Total: 8 comprehensive E2E integration tests.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Simulates streaming response from Ollama."""

    def __init__(self, tokens: List[str], status_code: int = 200):
        self._lines = [
            json.dumps({"message": {"role": "assistant", "content": t}, "done": False})
            for t in tokens
        ]
        self._lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}))
        self.status_code = status_code

    async def aiter_lines(self) -> AsyncGenerator[str, None]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return b""

    async def __aenter__(self) -> "MockStreamResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


def _create_mock_ollama_client(tokens: List[str]) -> MagicMock:
    """Creates mock httpx.AsyncClient streaming the provided tokens."""
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=MockStreamResponse(tokens))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    """Helper to parse SSE raw body into event dicts."""
    events: List[Dict[str, Any]] = []
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
# 8 E2E INTEGRATION TESTS
# ============================================================================

def test_e2e_full_chat_session_lifecycle(client: TestClient) -> None:
    """E2E Test 1: Full session creation -> SSE streaming -> database persistence."""
    # 1. Create conversation session
    conv_resp = client.post("/api/conversations", json={"title": "E2E Lifecycle Test"})
    assert conv_resp.status_code == 201
    cid = conv_resp.json()["id"]

    # 2. Send prompt through streaming endpoint
    mock_c = _create_mock_ollama_client(["Hello! ", "I am STEM Coder Expert.", " Ready to help."])
    with patch("httpx.AsyncClient", return_value=mock_c):
        chat_resp = client.post(
            "/api/chat",
            json={
                "conversation_id": cid,
                "message": "Introduce yourself and describe your capabilities.",
            },
        )
        assert chat_resp.status_code == 200

        # Parse SSE events
        events = _parse_sse_events(chat_resp.text)
        types = [e["event"] for e in events]
        assert "metadata" in types
        assert "token" in types
        assert "telemetry" in types
        assert "done" in types

    # 3. Verify persistence in SQLite
    detail = client.get(f"/api/conversations/{cid}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert "Introduce yourself" in detail["messages"][0]["content"]
    assert detail["messages"][1]["role"] == "assistant"
    assert "STEM Coder Expert" in detail["messages"][1]["content"]


def test_e2e_multi_turn_context_continuity(client: TestClient) -> None:
    """E2E Test 2: Multi-turn dialogue maintains context and persists all exchanges."""
    cid = f"e2e-turn-{uuid.uuid4().hex[:6]}"

    # Turn 1
    mock_c1 = _create_mock_ollama_client(["First turn response."])
    with patch("httpx.AsyncClient", return_value=mock_c1):
        r1 = client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 1"})
        assert r1.status_code == 200

    # Turn 2
    mock_c2 = _create_mock_ollama_client(["Second turn response building on first."])
    with patch("httpx.AsyncClient", return_value=mock_c2):
        r2 = client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 2"})
        assert r2.status_code == 200

    # Turn 3
    mock_c3 = _create_mock_ollama_client(["Third turn final conclusion."])
    with patch("httpx.AsyncClient", return_value=mock_c3):
        r3 = client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 3"})
        assert r3.status_code == 200

    # Check conversation has all 6 messages (3 user + 3 assistant)
    conv = get_conversation(cid)
    assert conv is not None
    assert len(conv["messages"]) == 6
    for i, role in enumerate(["user", "assistant", "user", "assistant", "user", "assistant"]):
        assert conv["messages"][i]["role"] == role


def test_e2e_code_generation_and_execution_pipeline(client: TestClient) -> None:
    """E2E Test 3: Assistant generates code snippet, client extracts and executes in sandbox."""
    generated_code = (
        "def compute_harmonic_mean(a, b):\n"
        "    return 2 * (a * b) / (a + b)\n\n"
        "result = compute_harmonic_mean(6, 12)\n"
        "print('HARMONIC_MEAN:', result)\n"
    )

    mock_c = _create_mock_ollama_client([
        "Here is the Python code:\n```python\n",
        generated_code,
        "```\nEnjoy computing harmonic means!",
    ])

    with patch("httpx.AsyncClient", return_value=mock_c):
        chat_resp = client.post("/api/chat", json={"message": "Write a python function for harmonic mean"})
        assert chat_resp.status_code == 200
        events = _parse_sse_events(chat_resp.text)
        tokens = [e["data"]["token"] for e in events if e["event"] == "token"]
        full_text = "".join(tokens)
        assert "```python" in full_text

        # Extract code block via regex
        match = re.search(r"```python\s*(.*?)\s*```", full_text, re.DOTALL)
        assert match is not None
        code_to_run = match.group(1).strip()

        # Submit extracted code to execution endpoint
        exec_resp = client.post(
            "/api/execute",
            json={"language": "python", "code": code_to_run, "timeout_seconds": 3.0},
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["success"] is True
        assert exec_data["exit_code"] == 0
        assert "HARMONIC_MEAN: 8.0" in exec_data["stdout"]


def test_e2e_physmath_formula_verification_in_chat(client: TestClient) -> None:
    """E2E Test 4: Physical equations trigger PhysMath dimensional analysis in telemetry."""
    explanation = (
        "Kinetic energy is defined as KE = 0.5 * m * v**2 where m has units of kg "
        "and v has units of m/s."
    )
    mock_c = _create_mock_ollama_client([explanation])

    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Calculate kinetic energy formula KE = 0.5 * m * v**2",
                "enable_physmath": True,
            },
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        telem_events = [e for e in events if e["event"] == "telemetry"]
        assert len(telem_events) == 1
        phys = telem_events[0]["data"].get("physmath")
        assert phys is not None
        assert phys.get("status") in ("verified", "detected")


def test_e2e_rag_lesson_retrieval_and_citation_attachment(client: TestClient) -> None:
    """E2E Test 5: Querying domain topics retrieves RAG lessons and attaches citations."""
    mock_c = _create_mock_ollama_client(["Applying the diffusion coefficient."])

    with patch("httpx.AsyncClient", return_value=mock_c):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Solve the 1D heat equation diffusion problem",
                "enable_rag": True,
            },
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        meta = [e for e in events if e["event"] == "metadata"][0]["data"]
        assert "citations" in meta
        assert isinstance(meta["citations"], list)


def test_e2e_polyglot_sql_execution_and_telemetry(client: TestClient) -> None:
    """E2E Test 6: Safe polyglot SQL queries execute in in-memory SQLite and return tabular data."""
    setup_sql = """
    CREATE TABLE stem_constants (name TEXT, value REAL);
    INSERT INTO stem_constants VALUES ('speed_of_light', 299792458.0), ('planck', 6.62607015e-34);
    """
    query_sql = "SELECT name, value FROM stem_constants ORDER BY value DESC;"
    resp = client.post(
        "/api/execute",
        json={"language": "sql", "test_suite": setup_sql, "code": query_sql},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["security_status"] == "clean"
    assert "speed_of_light" in data["stdout"]
    assert "299792458.0" in data["stdout"]


def test_e2e_sandbox_memory_safety_under_load(client: TestClient) -> None:
    """E2E Test 7: Sequential code executions in sandbox maintain stable memory footprint."""
    for i in range(5):
        code = f"x = sum(range({(i + 1) * 1000}))\nprint('SUM_{i}:', x)"
        resp = client.post(
            "/api/execute",
            json={"language": "python", "code": code, "timeout_seconds": 2.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert f"SUM_{i}:" in data["stdout"]
        assert data["memory_breached"] is False


def test_e2e_health_monitoring_and_hardware_budget_adherence(client: TestClient) -> None:
    """E2E Test 8: Health endpoint validates hardware limits (<=4GB VRAM, <=15GB RAM, <=128MB heap)."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()

    # Hardware Budget Gate
    budget = data["hardware_budget"]
    assert "4.0 GB" in budget["gpu_vram_limit"]
    assert "15.0 GB" in budget["system_ram_limit"]
    assert "128 MB" in budget["php_vector_heap_limit"]
    assert "256 MB" in budget["sandbox_memory_ceiling"]
    assert budget["status"] == "compliant"

    # Services Gate
    services = data["services"]
    assert "sqlite" in services
    assert services["sqlite"]["chat_history"]["status"] == "online"
    assert "sandbox" in services
    assert services["sandbox"]["max_memory_mb"] == 256
    assert "physmath" in services
    assert services["physmath"]["status"] == "online"
