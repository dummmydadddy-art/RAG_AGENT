import tempfile
import pytest
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Doc, Hit, LessonStatus
from rag_adapter.sqlite_backend import LocalSqliteRagBackend
from rag_adapter.stub_backend import StubBackend


@pytest.fixture(params=["stub", "sqlite"])
def backend(request):
    """Parametrized fixture providing both StubBackend and LocalSqliteRagBackend for contract testing."""
    if request.param == "stub":
        return StubBackend()
    elif request.param == "sqlite":
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            tmp_path = tmp.name
        return LocalSqliteRagBackend(db_path=tmp_path)


def test_upsert_and_get_roundtrip(backend: RagAdapter):
    doc_id = "doc-001"
    text = "Newton's second law: F = m * a states force equals mass times acceleration."
    meta = {"domain": "physics", "author": "Newton"}

    backend.upsert("knowledge", doc_id, text, meta)
    doc = backend.get("knowledge", doc_id)

    assert doc is not None
    assert doc.doc_id == doc_id
    assert doc.collection == "knowledge"
    assert doc.text == text
    assert doc.metadata.get("domain") == "physics"
    assert doc.metadata.get("author") == "Newton"


def test_search_retrieval(backend: RagAdapter):
    backend.upsert("knowledge", "doc-1", "Conservation of linear momentum in isolated systems.", {"domain": "physics"})
    backend.upsert("knowledge", "doc-2", "Symplectic integrators preserve phase space volume.", {"domain": "numerics"})
    backend.upsert("knowledge", "doc-3", "General relativity and Riemannian manifolds.", {"domain": "maths"})

    hits = backend.search("symplectic integrators", ["knowledge"], k=2)
    assert len(hits) > 0
    assert hits[0].doc_id == "doc-2"
    assert "Symplectic" in hits[0].text


def test_lesson_lifecycle_and_exclusion(backend: RagAdapter):
    lesson_id = "L-2026-10-0001"
    rule_text = "When integrating Hamiltonian systems, use symplectic integrators, because they conserve phase space volume."
    meta = {
        "title": "Use symplectic integrators for Hamiltonians",
        "status": LessonStatus.CANDIDATE,
        "domain": ["physics", "numerics"],
    }

    # 1. Upsert candidate lesson
    backend.upsert("lessons", lesson_id, rule_text, meta)
    lesson_doc = backend.get("lessons", lesson_id)
    assert lesson_doc is not None
    assert lesson_doc.metadata["status"] == LessonStatus.CANDIDATE

    # 2. Promote to verified
    backend.set_status("lessons", lesson_id, LessonStatus.VERIFIED, reason="Passed benchmark tests")
    lesson_doc = backend.get("lessons", lesson_id)
    assert lesson_doc.metadata["status"] == LessonStatus.VERIFIED
    assert lesson_doc.metadata["status_reason"] == "Passed benchmark tests"

    # Search should find the verified lesson
    hits = backend.search("Hamiltonian systems", ["lessons"], k=5)
    assert any(h.doc_id == lesson_id for h in hits)

    # 3. Retire lesson
    backend.set_status("lessons", lesson_id, LessonStatus.RETIRED, reason="Superseded by higher-order integrator")
    lesson_doc = backend.get("lessons", lesson_id)
    assert lesson_doc.metadata["status"] == LessonStatus.RETIRED

    # Search should exclude retired lesson by default
    hits_after_retire = backend.search("Hamiltonian systems", ["lessons"], k=5)
    assert not any(h.doc_id == lesson_id for h in hits_after_retire)


def test_delete_document(backend: RagAdapter):
    backend.upsert("traces", "trace-999", "Raw execution trace log", {"task": "task-01"})
    assert backend.get("traces", "trace-999") is not None

    backend.delete("traces", "trace-999")
    assert backend.get("traces", "trace-999") is None
