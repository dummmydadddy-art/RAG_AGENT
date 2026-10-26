import json
import pytest
from datetime import datetime, timedelta
from rag_adapter.sqlite_backend import LocalSqliteRagBackend
from rag_adapter.models import LessonStatus
from scripts.rollback_lessons import rollback_lessons


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "rollback_test.sqlite"
    backend = LocalSqliteRagBackend(str(db_file))
    return backend, str(db_file)


def test_rollback_by_lesson_id(test_db):
    backend, db_path = test_db
    lesson = {
        "id": "L-BAD-0001",
        "title": "Bad advice rule",
        "rule": "When encountering errors, do suppress exceptions silently, because crashes look bad.",
        "evidence": {"task_id": "TASK-01", "commit": "1111111", "tests": ["t1"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
    }
    backend.upsert_lesson(lesson)

    # Rollback by ID
    res = rollback_lessons(db_path=db_path, lesson_id="L-BAD-0001", reason="Causes silent regressions")
    assert res["rolled_back_count"] == 1
    assert "L-BAD-0001" in res["rolled_back_ids"]

    # Verify status in database
    doc = backend.get("lessons", "L-BAD-0001")
    assert doc.metadata["status"] == LessonStatus.RETIRED
    assert "Causes silent regressions" in doc.metadata.get("status_reason", "")


def test_rollback_by_failed_task(test_db):
    backend, db_path = test_db
    lesson1 = {
        "id": "L-TASK-0001",
        "title": "Rule from task 06",
        "rule": "When solving heat equation, do ignore CFL condition, because modern computers are fast.",
        "evidence": {"task_id": "TASK-06-PHYS-HEAT-1D", "commit": "2222222", "tests": ["t2"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
    }
    lesson2 = {
        "id": "L-TASK-0002",
        "title": "Rule from task 01",
        "rule": "When caching keys, do use LRU eviction, because recent entries have highest locality.",
        "evidence": {"task_id": "TASK-01-CODE-LRU", "commit": "3333333", "tests": ["t3"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
    }
    backend.upsert_lesson(lesson1)
    backend.upsert_lesson(lesson2)

    # Rollback lessons tied to TASK-06
    res = rollback_lessons(db_path=db_path, failed_task="TASK-06-PHYS-HEAT-1D", reason="Task 06 failed eval")
    assert res["rolled_back_count"] == 1
    assert "L-TASK-0001" in res["rolled_back_ids"]

    # Check lesson1 retired, lesson2 untouched
    doc1 = backend.get("lessons", "L-TASK-0001")
    doc2 = backend.get("lessons", "L-TASK-0002")
    assert doc1.metadata["status"] == LessonStatus.RETIRED
    assert doc2.metadata["status"] == LessonStatus.VERIFIED


def test_rollback_by_timestamp(test_db):
    backend, db_path = test_db
    now = datetime.utcnow()
    old_time = (now - timedelta(hours=2)).isoformat()
    new_time = (now + timedelta(seconds=10)).isoformat()

    lesson_old = {
        "id": "L-OLD-0001",
        "title": "Old stable rule",
        "rule": "When writing Python, do follow PEP 8, because readability counts.",
        "evidence": {"task_id": "TASK-01", "commit": "4444444", "tests": ["t4"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
        "created_at": old_time,
    }
    lesson_new = {
        "id": "L-NEW-0001",
        "title": "New regression rule",
        "rule": "When compiling regex, do recompile on every call, because memory is cheap.",
        "evidence": {"task_id": "TASK-02", "commit": "5555555", "tests": ["t5"], "review": "passed"},
        "status": LessonStatus.CANDIDATE,
        "created_at": new_time,
    }
    backend.upsert_lesson(lesson_old)
    backend.upsert_lesson(lesson_new)

    # Cutoff timestamp: 1 hour ago
    cutoff = (now - timedelta(hours=1)).isoformat()
    res = rollback_lessons(db_path=db_path, since_timestamp=cutoff, reason="Rollback recent batch")
    assert res["rolled_back_count"] == 1
    assert "L-NEW-0001" in res["rolled_back_ids"]

    doc_old = backend.get("lessons", "L-OLD-0001")
    doc_new = backend.get("lessons", "L-NEW-0001")
    assert doc_old.metadata["status"] == LessonStatus.VERIFIED
    assert doc_new.metadata["status"] == LessonStatus.RETIRED


def test_rollback_dry_run(test_db):
    backend, db_path = test_db
    lesson = {
        "id": "L-DRY-0001",
        "title": "Dry run target",
        "rule": "When doing dry run, do check safety, because tests should not mutate.",
        "evidence": {"task_id": "TASK-01", "commit": "6666666", "tests": ["t6"], "review": "passed"},
        "status": LessonStatus.VERIFIED,
    }
    backend.upsert_lesson(lesson)

    res = rollback_lessons(db_path=db_path, lesson_id="L-DRY-0001", dry_run=True)
    assert res["rolled_back_count"] == 1
    assert "L-DRY-0001" in res["rolled_back_ids"]

    # Verify status is NOT changed in database
    doc = backend.get("lessons", "L-DRY-0001")
    assert doc.metadata["status"] == LessonStatus.VERIFIED
