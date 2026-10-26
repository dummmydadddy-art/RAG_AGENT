import pytest
from rag_adapter.sqlite_backend import LocalSqliteRagBackend
from rag_adapter.models import LessonStatus
from rag_adapter.lifecycle import (
    validate_lesson_format,
    check_duplicate_lesson,
    check_contradiction,
    can_promote_lesson,
    format_rule_citation,
)


@pytest.fixture
def backend(tmp_path):
    db_file = tmp_path / "test_lifecycle.sqlite"
    return LocalSqliteRagBackend(str(db_file))


def test_rule_canonical_format_valid():
    rule = "When integrating stiff ODEs, do use implicit Euler, because explicit Euler becomes unstable."
    is_valid, msg = validate_lesson_format(rule)
    assert is_valid is True
    assert msg == "Valid"


def test_rule_canonical_format_invalid_patterns():
    invalid_rules = [
        "Always use implicit Euler for stiff ODEs.",
        "When integrating stiff ODEs, use implicit Euler.",  # missing 'do' and 'because'
        "When integrating stiff ODEs, do use implicit Euler.",  # missing 'because'
        "Do use implicit Euler because explicit Euler is unstable.",  # missing 'When'
    ]
    for r in invalid_rules:
        is_valid, msg = validate_lesson_format(r)
        assert is_valid is False
        assert "When <situation>, do <action>, because <reason>" in msg


def test_duplicate_detection(backend):
    lesson1 = {
        "id": "L-2026-10-0001",
        "title": "Use implicit Euler for stiff ODEs",
        "rule": "When integrating stiff ODEs, do use implicit Euler, because explicit Euler becomes unstable.",
        "domain": ["numerics", "physics"],
        "evidence": {"task_id": "TASK-08", "commit": "abc1234", "tests": ["test_stiff_ode"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
    }
    backend.upsert_lesson(lesson1)

    # Identical rule
    is_dup, dup_id = check_duplicate_lesson(backend, lesson1["rule"])
    assert is_dup is True
    assert dup_id == "L-2026-10-0001"

    # Different rule
    is_dup2, _ = check_duplicate_lesson(backend, "When solving linear systems, do use LU decomposition, because it is efficient.")
    assert is_dup2 is False


def test_contradiction_detection(backend):
    # Establish a verified lesson
    lesson_v = {
        "id": "L-2026-10-0002",
        "title": "Use Newton-Raphson for Kepler",
        "rule": "When solving Kepler equation, do use Newton-Raphson iteration, because it converges quadratically.",
        "domain": ["numerics", "physics"],
        "evidence": {"task_id": "TASK-05", "commit": "def5678", "tests": ["test_kepler"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
    }
    backend.upsert_lesson(lesson_v)

    # Contradictory rule with opposite action for same situation
    contra_rule = "When solving Kepler equation, do not use Newton-Raphson iteration, because it can diverge on high eccentricity."
    is_contra, contra_id, reason = check_contradiction(backend, contra_rule)
    assert is_contra is True
    assert contra_id == "L-2026-10-0002"

    # Non-contradictory rule
    clean_rule = "When solving Kepler equation with high eccentricity, do provide a good initial guess, because standard M initial guess diverges."
    is_contra2, _, _ = check_contradiction(backend, clean_rule)
    assert is_contra2 is False


def test_promotion_invariants(backend):
    lesson_data = {
        "id": "L-2026-10-0003",
        "title": "Use Halley method for roots",
        "rule": "When finding roots with available second derivative, do use Halley method, because it exhibits cubic convergence.",
        "domain": ["numerics", "maths"],
        "evidence": {"task_id": "TASK-03", "commit": "aaa1111", "tests": ["test_halley"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
    }
    backend.upsert_lesson(lesson_data)

    # Ineligible promotion: no merge and no reuse
    ok, err = can_promote_lesson(backend, "L-2026-10-0003", pr_merged=False)
    assert ok is False
    assert "PR merged or successful reuse" in err

    # Eligible via pr_merged
    ok2, err2 = can_promote_lesson(backend, "L-2026-10-0003", pr_merged=True)
    assert ok2 is True

    # Record 1 successful reuse
    backend.record_lesson_use("L-2026-10-0003", success=True, task_id="TASK-09")
    ok3, err3 = can_promote_lesson(backend, "L-2026-10-0003", pr_merged=False)
    assert ok3 is True


def test_auto_retirement_on_failures(backend):
    lesson_data = {
        "id": "L-2026-10-0004",
        "title": "Use forward Euler for wave",
        "rule": "When solving wave equation, do use forward Euler, because it is simple to implement.",
        "domain": ["numerics"],
        "evidence": {"task_id": "TASK-04", "commit": "bbb2222", "tests": ["test_wave"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
    }
    backend.upsert_lesson(lesson_data)

    # First failure
    res1 = backend.record_lesson_use("L-2026-10-0004", success=False, task_id="TASK-04A")
    assert res1["retired"] is False
    assert res1["status"] == LessonStatus.CANDIDATE

    # Second failure (0/2 success = 0.0 < 0.5) -> Auto-retired
    res2 = backend.record_lesson_use("L-2026-10-0004", success=False, task_id="TASK-04B")
    assert res2["retired"] is True
    assert res2["status"] == LessonStatus.RETIRED


def test_retrieval_invariants_and_citations(backend):
    # Insert 1 candidate, 1 verified, 1 retired
    backend.upsert_lesson({
        "id": "L-2026-10-0010",
        "title": "Verified rule",
        "rule": "When testing floating point equality, do use math.isclose with explicit tolerances, because exact float comparison fails.",
        "domain": ["python", "numerics"],
        "evidence": {"task_id": "TASK-01", "commit": "ccc3333", "tests": ["t1"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
    })
    backend.upsert_lesson({
        "id": "L-2026-10-0011",
        "title": "Candidate rule",
        "rule": "When testing matrix equality, do use np.allclose with atol, because roundoff occurs in matrix inversion.",
        "domain": ["python", "numerics"],
        "evidence": {"task_id": "TASK-02", "commit": "ddd4444", "tests": ["t2"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
    })
    backend.upsert_lesson({
        "id": "L-2026-10-0012",
        "title": "Retired rule",
        "rule": "When testing equality, do use exact == operator, because floats are exact.",
        "domain": ["python"],
        "evidence": {"task_id": "TASK-03", "commit": "eee5555", "tests": ["t3"], "review": "passed"},
        "status": LessonStatus.RETIRED,
    })

    hits = backend.search_lessons("equality testing floating point")
    doc_ids = [h.doc_id for h in hits]
    assert "L-2026-10-0012" not in doc_ids  # Retired excluded!
    assert "L-2026-10-0010" in doc_ids
    assert "L-2026-10-0011" in doc_ids

    # Verified prioritized first
    assert doc_ids[0] == "L-2026-10-0010"

    # Citation formatting: candidate must be marked [unverified]
    citation = format_rule_citation(hits)
    assert "[VERIFIED] L-2026-10-0010" in citation
    assert "[UNVERIFIED] L-2026-10-0011" in citation
