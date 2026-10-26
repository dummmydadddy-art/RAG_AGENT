import os
import pytest
from rag_adapter.http_backend import HttpRagBackend
from rag_adapter.models import LessonStatus

ENDPOINT = os.getenv("RAG_HTTP_ENDPOINT")


@pytest.mark.integration
@pytest.mark.skipif(not ENDPOINT, reason="RAG_HTTP_ENDPOINT environment variable is unset")
def test_http_rag_backend_contract():
    backend = HttpRagBackend(base_url=ENDPOINT)
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
