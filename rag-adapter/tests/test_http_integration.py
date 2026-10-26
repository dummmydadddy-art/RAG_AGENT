import os
import pytest
from rag_adapter.http_backend import HttpRagBackend
from rag_adapter.models import LessonStatus

ENDPOINT = os.getenv("RAG_HTTP_ENDPOINT", "http://127.0.0.1:8000")


@pytest.mark.integration
def test_http_rag_backend_contract():
    backend = HttpRagBackend(base_url=ENDPOINT, strict_mode=False)
    doc_id = "http-test-doc-001"
    text = "Hamiltonian mechanics and symplectic geometry integration test."
    meta = {"domain": "physics", "author": "Hamilton"}

    # 1. Upsert
    backend.upsert("knowledge", doc_id, text, meta)

    # 2. Get
    doc = backend.get("knowledge", doc_id)
    assert doc is not None
    assert doc.doc_id == doc_id
    assert doc.text == text
    assert doc.metadata.get("domain") == "physics"

    # 3. Search
    hits = backend.search("symplectic geometry", ["knowledge"], k=5)
    assert len(hits) > 0
    assert any(h.doc_id == doc_id for h in hits)

    # 4. Lesson Lifecycle
    lesson_id = "L-HTTP-0001"
    lesson_rule = "When solving symplectic systems, use leapfrog integrators, because phase volume is preserved."
    backend.upsert("lessons", lesson_id, lesson_rule, {"status": LessonStatus.CANDIDATE, "title": "Leapfrog"})

    backend.set_status("lessons", lesson_id, LessonStatus.VERIFIED, reason="Passed live integration test")
    lesson = backend.get("lessons", lesson_id)
    assert lesson is not None
    assert lesson.metadata.get("status") == LessonStatus.VERIFIED

    # 5. Delete
    backend.delete("knowledge", doc_id)
    assert backend.get("knowledge", doc_id) is None


@pytest.mark.integration
def test_http_rag_backend_strict_mode():
    """Verify strict mode operates against live HTTP endpoint and verifies backend identity."""
    backend = HttpRagBackend(base_url=ENDPOINT, strict_mode=True)
    assert "strict" in backend.backend_identity
    assert backend.retrieval_mode == "hybrid_rrf_dense_sparse"

    doc_id = "http-strict-001"
    text = "Strict mode verification document testing nomic-embed-text dense embeddings."
    meta = {"domain": "test", "type": "strict"}

    backend.upsert("knowledge", doc_id, text, meta)
    doc = backend.get("knowledge", doc_id)
    assert doc is not None
    assert doc.doc_id == doc_id

    # Search should query HTTP endpoint directly
    hits = backend.search("dense embeddings nomic", ["knowledge"], k=5)
    assert len(hits) > 0


@pytest.mark.integration
def test_http_rag_backend_strict_mode_rejects_fallback():
    """Verify that strict mode raises RuntimeError and refuses to silently fallback to SQLite when endpoint is down."""
    broken_backend = HttpRagBackend(base_url="http://127.0.0.1:59999", strict_mode=True, timeout=1.0)
    
    with pytest.raises(RuntimeError) as exc_info:
        broken_backend.search("query on down server", ["knowledge"], k=5)
    assert "Strict mode active" in str(exc_info.value) or "HTTP search failed" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info_upsert:
        broken_backend.upsert("knowledge", "fail-doc", "content", {})
    assert "HTTP ingest failed in strict mode" in str(exc_info_upsert.value)
