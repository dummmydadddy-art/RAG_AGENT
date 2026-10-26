import pytest
from rag_mcp.server import (
    rag_demote,
    rag_promote,
    rag_record_use,
    rag_search,
    rag_stats,
    rag_upsert_lesson,
)


def test_rag_upsert_permission_denied():
    lesson = {
        "id": "L-TEST-0001",
        "title": "Unapproved lesson",
        "rule": "When doing X do Y because Z",
    }
    with pytest.raises(PermissionError):
        rag_upsert_lesson(lesson, caller_role="implementer")


def test_rag_upsert_and_search_by_librarian():
    lesson_id = "L-TEST-0002"
    lesson = {
        "id": lesson_id,
        "title": "Always verify units before integration",
        "rule": "When solving PDEs with physical dimensions, verify units first, because unit errors corrupt fluxes.",
        "domain": ["physics", "numerics"],
        "evidence": {"task_id": "task-01", "tests": ["test_flux"]},
    }

    res = rag_upsert_lesson(lesson, caller_role="librarian")
    assert res.get("success") is True
    assert res.get("lesson_id") == lesson_id

    # Search should retrieve it
    search_res = rag_search("PDEs physical dimensions", collections=["lessons"])
    assert search_res.get("count") > 0
    assert any(r["doc_id"] == lesson_id for r in search_res["results"])


def test_rag_record_use_and_auto_retire():
    lesson_id = "L-TEST-0003"
    lesson = {
        "id": lesson_id,
        "title": "Flawed advice lesson",
        "rule": "When encountering NaN, replace with 0.0, because it avoids crashing.",
    }
    rag_upsert_lesson(lesson, caller_role="librarian")

    # Record first failure
    r1 = rag_record_use(lesson_id, success=False, task_id="task-fail-1")
    assert r1.get("retired") is False
    assert r1.get("fail_count") == 1

    # Record second failure (0 successes, 2 failures -> < 50% success)
    r2 = rag_record_use(lesson_id, success=False, task_id="task-fail-2")
    assert r2.get("retired") is True
    assert r2.get("status") == "retired"

    # Search should no longer retrieve this retired lesson by default
    search_res = rag_search("replace with 0.0", collections=["lessons"])
    assert not any(r["doc_id"] == lesson_id for r in search_res["results"])


def test_rag_promote_and_demote():
    lesson_id = "L-TEST-0004"
    lesson = {
        "id": lesson_id,
        "title": "Symplectic leapfrog conservation",
        "rule": "When integrating N-body gravitational systems, use leapfrog, because it preserves symplectic form.",
    }
    rag_upsert_lesson(lesson, caller_role="librarian")

    # Promote
    p_res = rag_promote(lesson_id, reason="PR merged cleanly with full verification", caller_role="librarian")
    assert p_res.get("success") is True
    assert p_res.get("status") == "verified"

    # Demote
    d_res = rag_demote(lesson_id, reason="New higher-order method preferred", caller_role="rollback")
    assert d_res.get("success") is True
    assert d_res.get("status") == "retired"


def test_rag_stats():
    stats = rag_stats()
    assert "lessons_total" in stats
    assert "lessons_verified" in stats
    assert "lessons_retired" in stats
    assert isinstance(stats["lessons_total"], int)
