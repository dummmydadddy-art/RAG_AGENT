"""
tests/unit/test_web_api.py

Unit test suite for FastAPI Web API routes:
- GET /api/health (subsystem health, services, hardware budget adherence)
- GET /api/lessons (filtering by query, collection, status, pagination limit)
- POST /api/lessons/search (structured search and validation)
- Conversations CRUD (GET /api/conversations, POST, GET /{id}, PATCH /{id}, DELETE /{id})
- POST /api/chat input validation and error responses

Total: 25 comprehensive unit tests.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.web.app import app
from src.web.config import get_config


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Creates in-memory TestClient bound to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# 1. HEALTH & HARDWARE TELEMETRY ENDPOINT TESTS (5 tests)
# ============================================================================

def test_health_endpoint_returns_200_and_expected_structure(client: TestClient) -> None:
    """GET /api/health should return HTTP 200 with status, services, and hardware_budget."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "services" in data
    assert "hardware_budget" in data
    assert "timestamp" in data


def test_health_hardware_budget_contains_strict_limits(client: TestClient) -> None:
    """GET /api/health must report hardware boundaries <= 4GB VRAM, <= 15GB RAM, <= 128MB PHP heap."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    hw = resp.json()["hardware_budget"]
    assert "gpu_vram_limit" in hw
    assert "4.0 GB" in hw["gpu_vram_limit"]
    assert "system_ram_limit" in hw
    assert "15.0 GB" in hw["system_ram_limit"]
    assert "php_vector_heap_limit" in hw
    assert "128 MB" in hw["php_vector_heap_limit"]
    assert hw.get("status") == "compliant"


def test_health_services_sqlite_structure(client: TestClient) -> None:
    """GET /api/health must report status of vectors.sqlite and chat_history.sqlite."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "sqlite" in services
    sqlite_info = services["sqlite"]
    assert "vector_database" in sqlite_info
    assert "chat_history" in sqlite_info
    assert sqlite_info["chat_history"]["status"] == "online"


def test_health_services_physmath_tools_count(client: TestClient) -> None:
    """GET /api/health must verify that PhysMath MCP toolsuite is registered."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "physmath" in services
    physmath = services["physmath"]
    assert physmath["status"] == "online"
    assert physmath["tools_count"] >= 7
    assert "units_check" in physmath["features"]
    assert "sym_equiv" in physmath["features"]


def test_health_services_sandbox_details(client: TestClient) -> None:
    """GET /api/health must report the Win32 Job Object sandbox ceiling of 256MB and 5.0s."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "sandbox" in services
    sb = services["sandbox"]
    assert sb["max_memory_mb"] == 256
    assert sb["timeout_seconds"] == 5.0


# ============================================================================
# 2. LESSONS & RAG STORE ENDPOINT TESTS (8 tests)
# ============================================================================

def test_lessons_list_default_returns_200(client: TestClient) -> None:
    """GET /api/lessons should return HTTP 200 with total count and lessons list."""
    resp = client.get("/api/lessons")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "lessons" in data
    assert isinstance(data["lessons"], list)
    assert data["total"] == len(data["lessons"])


def test_lessons_list_with_query_filter(client: TestClient) -> None:
    """GET /api/lessons?q=... returns scored lessons matching search term."""
    resp = client.get("/api/lessons?q=equation")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["lessons"], list)
    for item in data["lessons"]:
        assert "id" in item
        assert "text" in item
        assert "score" in item
        assert item["score"] > 0.0


def test_lessons_list_with_collection_filter(client: TestClient) -> None:
    """GET /api/lessons?collection=lessons filters by collection."""
    resp = client.get("/api/lessons?collection=lessons")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["lessons"]:
        assert item["collection"] == "lessons"


def test_lessons_list_with_status_filter(client: TestClient) -> None:
    """GET /api/lessons?status=verified filters by verified status."""
    resp = client.get("/api/lessons?status=verified")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["lessons"]:
        if item.get("status"):
            assert item["status"].lower() == "verified"


def test_lessons_list_respects_limit_parameter(client: TestClient) -> None:
    """GET /api/lessons?limit=2 returns at most 2 items."""
    resp = client.get("/api/lessons?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["lessons"]) <= 2


def test_lessons_list_rejects_invalid_limit(client: TestClient) -> None:
    """GET /api/lessons with limit <= 0 or > 100 should return HTTP 422."""
    resp_zero = client.get("/api/lessons?limit=0")
    assert resp_zero.status_code == 422
    resp_over = client.get("/api/lessons?limit=101")
    assert resp_over.status_code == 422


def test_lessons_search_post_endpoint(client: TestClient) -> None:
    """POST /api/lessons/search with valid payload returns ranked results."""
    payload = {"query": "heat conduction", "limit": 5}
    resp = client.post("/api/lessons/search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "lessons" in data
    assert len(data["lessons"]) <= 5


def test_lessons_search_post_validation_error(client: TestClient) -> None:
    """POST /api/lessons/search without query field returns HTTP 422."""
    resp = client.post("/api/lessons/search", json={"limit": 5})
    assert resp.status_code == 422


def test_lesson_feedback_helpful_success(client: TestClient) -> None:
    """POST /api/lessons/{id}/feedback records positive feedback successfully."""
    resp = client.post("/api/lessons/lesson-001/feedback", json={"helpful": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["lesson_id"] == "lesson-001"
    assert data["helpful"] is True


def test_lesson_feedback_unhelpful_with_comment(client: TestClient) -> None:
    """POST /api/lessons/{id}/feedback records negative feedback with comment."""
    payload = {"helpful": False, "comment": "Outdated rule"}
    resp = client.post("/api/lessons/lesson-002/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["lesson_id"] == "lesson-002"
    assert data["helpful"] is False
    assert data["comment"] == "Outdated rule"


def test_lesson_feedback_validation_error(client: TestClient) -> None:
    """POST /api/lessons/{id}/feedback without helpful field returns HTTP 422."""
    resp = client.post("/api/lessons/lesson-001/feedback", json={})
    assert resp.status_code == 422


# ============================================================================
# 3. CONVERSATIONS CRUD LIFECYCLE TESTS (10 tests)
# ============================================================================

def test_conversations_list_returns_200(client: TestClient) -> None:
    """GET /api/conversations should return HTTP 200 and a list of summaries."""
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_conversations_create_with_title(client: TestClient) -> None:
    """POST /api/conversations with title creates session and returns 201."""
    title = f"Test Session {uuid.uuid4().hex[:6]}"
    resp = client.post("/api/conversations", json={"title": title})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["title"] == title
    assert "created_at" in data
    assert "messages" in data
    assert data["messages"] == []


def test_conversations_create_default_title(client: TestClient) -> None:
    """POST /api/conversations without title defaults to 'New Conversation'."""
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "New Conversation"


def test_conversations_get_by_id_success(client: TestClient) -> None:
    """GET /api/conversations/{id} retrieves existing conversation."""
    # Create conversation
    create_resp = client.post("/api/conversations", json={"title": "Detail Test"})
    cid = create_resp.json()["id"]

    resp = client.get(f"/api/conversations/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cid
    assert data["title"] == "Detail Test"
    assert "messages" in data


def test_conversations_get_by_id_not_found(client: TestClient) -> None:
    """GET /api/conversations/{id} with nonexistent ID returns HTTP 404."""
    non_existent = str(uuid.uuid4())
    resp = client.get(f"/api/conversations/{non_existent}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_conversations_patch_title_success(client: TestClient) -> None:
    """PATCH /api/conversations/{id} updates conversation title."""
    create_resp = client.post("/api/conversations", json={"title": "Original Title"})
    cid = create_resp.json()["id"]

    new_title = "Updated New Title"
    patch_resp = client.patch(f"/api/conversations/{cid}", json={"title": new_title})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "updated"
    assert patch_resp.json()["title"] == new_title

    # Confirm change persisted
    get_resp = client.get(f"/api/conversations/{cid}")
    assert get_resp.json()["title"] == new_title


def test_conversations_patch_title_empty_validation_error(client: TestClient) -> None:
    """PATCH /api/conversations/{id} with empty title string returns HTTP 422."""
    create_resp = client.post("/api/conversations", json={"title": "Valid"})
    cid = create_resp.json()["id"]

    resp = client.patch(f"/api/conversations/{cid}", json={"title": ""})
    assert resp.status_code == 422


def test_conversations_patch_nonexistent_id_returns_404(client: TestClient) -> None:
    """PATCH /api/conversations/{id} with unknown ID returns HTTP 404."""
    non_existent = str(uuid.uuid4())
    resp = client.patch(f"/api/conversations/{non_existent}", json={"title": "New Title"})
    assert resp.status_code == 404


def test_conversations_delete_success(client: TestClient) -> None:
    """DELETE /api/conversations/{id} deletes conversation and returns status deleted."""
    create_resp = client.post("/api/conversations", json={"title": "To Delete"})
    cid = create_resp.json()["id"]

    del_resp = client.delete(f"/api/conversations/{cid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Verify 404 on subsequent get
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_conversations_delete_nonexistent_returns_404(client: TestClient) -> None:
    """DELETE /api/conversations/{id} with unknown ID returns HTTP 404."""
    non_existent = str(uuid.uuid4())
    resp = client.delete(f"/api/conversations/{non_existent}")
    assert resp.status_code == 404


# ============================================================================
# 4. CHAT ENDPOINT INPUT VALIDATION TESTS (2 tests)
# ============================================================================

def test_chat_validation_missing_message(client: TestClient) -> None:
    """POST /api/chat with missing message field returns HTTP 422 Unprocessable Entity."""
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 422


def test_chat_validation_empty_message(client: TestClient) -> None:
    """POST /api/chat with empty string message returns HTTP 422."""
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
