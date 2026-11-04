"""
tests/unit/test_accuracy_tracker.py

Unit tests for Feature F10: Closed-Loop Accuracy Tracker.
Verifies AccuracyMetricPoint dataclass, SQLite persistence, longitudinal querying,
RAG lesson retrieval with domain filtering, and automated ablation evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import pytest

from scripts.learning.accuracy_tracker import AccuracyMetricPoint, AccuracyTracker
from scripts.learning.synthetic_challenge_generator import SyntheticChallengeGenerator


class TestAccuracyMetricPointDataclass:
    """Verifies AccuracyMetricPoint dataclass contracts and serialization."""

    def test_to_dict_serialization(self):
        point = AccuracyMetricPoint(
            id="bench_001",
            timestamp="2026-11-04T10:00:00Z",
            cycle_iteration=5,
            pass_at_1=0.85,
            test_pass_rate=0.90,
            avg_patch_iterations=1.2,
            invariant_violation_rate=0.05,
            lessons_count=14,
            lessons_enabled=True,
            details={"domain": "dynamic_programming"},
        )
        d = point.to_dict()
        assert d["id"] == "bench_001"
        assert d["cycle_iteration"] == 5
        assert d["pass_at_1"] == 0.85
        assert d["invariant_compliance"] == 0.95
        assert d["lessons_count"] == 14
        assert d["lessons_enabled"] is True
        assert d["details"]["domain"] == "dynamic_programming"

    def test_from_row_with_dict(self):
        data = {
            "id": "bench_002",
            "timestamp": "2026-11-04T10:05:00Z",
            "cycle_iteration": 6,
            "pass_at_1": 1.0,
            "test_pass_rate": 1.0,
            "avg_patch_iterations": 0.0,
            "invariant_violation_rate": 0.0,
            "lessons_count": 15,
            "lessons_enabled": 1,
            "details": json.dumps({"passed": True}),
        }
        point = AccuracyMetricPoint.from_row(data)
        assert point.id == "bench_002"
        assert point.cycle_iteration == 6
        assert point.pass_at_1 == 1.0
        assert point.lessons_enabled is True
        assert point.details == {"passed": True}

    def test_from_row_with_tuple(self):
        row = (
            "bench_003",
            "2026-11-04T10:10:00Z",
            7,
            0.75,
            0.80,
            1.5,
            0.10,
            16,
            0,
            json.dumps({"ablation": True}),
        )
        point = AccuracyMetricPoint.from_row(row)
        assert point.id == "bench_003"
        assert point.cycle_iteration == 7
        assert point.pass_at_1 == 0.75
        assert point.lessons_enabled is False
        assert point.details == {"ablation": True}


class TestAccuracyTrackerPersistence:
    """Verifies SQLite database operations and benchmark persistence."""

    @pytest.fixture
    def tracker(self, tmp_path: Path):
        db_path = tmp_path / "test_accuracy.sqlite"
        return AccuracyTracker(db_path=db_path)

    def test_table_and_indexes_created(self, tracker: AccuracyTracker):
        with tracker._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accuracy_benchmarks';")
            assert cur.fetchone() is not None

            cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_acc_bench_cycle';")
            assert cur.fetchone() is not None

    def test_record_benchmark_and_get_latest(self, tracker: AccuracyTracker):
        bench_id = tracker.record_benchmark(
            cycle=1,
            pass_at_1=0.75,
            test_pass_rate=0.85,
            avg_patches=1.0,
            invariant_violations=0.10,
            lessons_count=5,
            lessons_enabled=True,
            details={"test": "record_1"},
        )
        assert bench_id.startswith("bench_")

        latest = tracker.get_latest_metrics()
        assert latest is not None
        assert latest.id == bench_id
        assert latest.cycle_iteration == 1
        assert latest.pass_at_1 == 0.75
        assert latest.test_pass_rate == 0.85
        assert latest.lessons_count == 5
        assert latest.details.get("test") == "record_1"

    def test_get_history_ordering_and_limit(self, tracker: AccuracyTracker):
        for i in range(1, 6):
            tracker.record_benchmark(
                cycle=i,
                pass_at_1=0.2 * i,
                test_pass_rate=0.2 * i,
                avg_patches=0.5,
                invariant_violations=0.0,
                lessons_count=i * 2,
            )

        # Chronological ascending
        asc_history = tracker.get_history(limit=3, ascending=True)
        assert len(asc_history) == 3
        # Should be cycles 3, 4, 5 (the last 3 recorded, in chronological order)
        assert [p.cycle_iteration for p in asc_history] == [3, 4, 5]

        # Descending
        desc_history = tracker.get_history(limit=3, ascending=False)
        assert len(desc_history) == 3
        assert [p.cycle_iteration for p in desc_history] == [5, 4, 3]

    def test_clamping_metrics(self, tracker: AccuracyTracker):
        bench_id = tracker.record_benchmark(
            cycle=10,
            pass_at_1=1.5,  # should be clamped to 1.0
            test_pass_rate=-0.5,  # should be clamped to 0.0
            avg_patches=-2.0,  # should be clamped to 0.0
            invariant_violations=2.0,  # should be clamped to 1.0
            lessons_count=10,
        )
        latest = tracker.get_latest_metrics()
        assert latest is not None
        assert latest.pass_at_1 == 1.0
        assert latest.test_pass_rate == 0.0
        assert latest.avg_patch_iterations == 0.0
        assert latest.invariant_violation_rate == 1.0

    def test_get_summary_stats_and_clear_history(self, tracker: AccuracyTracker):
        # Empty stats
        empty_stats = tracker.get_summary_stats()
        assert empty_stats["total_benchmarks"] == 0

        tracker.record_benchmark(cycle=1, pass_at_1=0.6, test_pass_rate=0.7, avg_patches=1.0, invariant_violations=0.1, lessons_count=2)
        tracker.record_benchmark(cycle=2, pass_at_1=0.8, test_pass_rate=0.9, avg_patches=0.5, invariant_violations=0.0, lessons_count=4)

        stats = tracker.get_summary_stats()
        assert stats["total_benchmarks"] == 2
        assert stats["avg_pass_at_1"] == 0.7
        assert stats["max_pass_at_1"] == 0.8
        assert stats["avg_invariant_compliance"] == 0.95

        deleted = tracker.clear_history()
        assert deleted == 2
        assert tracker.get_latest_metrics() is None


class TestLessonsRetrievalAndCounting:
    """Verifies counting and filtering of lessons stored in SQLite."""

    @pytest.fixture
    def db_with_lessons(self, tmp_path: Path):
        db_path = tmp_path / "test_lessons.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE rag_documents (
                    id TEXT PRIMARY KEY,
                    collection TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Active DP lesson
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l1",
                    "When solving multi-constrained 0/1 knapsack problems, do iterate backwards, because it bounds space.",
                    json.dumps({"domain": "dynamic_programming", "status": "candidate"}),
                ),
            )
            # Verified Physics lesson
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l2",
                    "When integrating Hamiltonian dynamics, do use symplectic Velocity-Verlet, because it bounds energy drift.",
                    json.dumps({"domain": "numerical_physics", "status": "verified"}),
                ),
            )
            # Retired lesson
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l3",
                    "When old lesson, do retire, because stale.",
                    json.dumps({"domain": "graph_algorithms", "status": "retired"}),
                ),
            )
            # Legacy "When None" poisoned lesson
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l4",
                    "When None in python, do nothing, because none.",
                    json.dumps({"domain": "dynamic_programming", "status": "candidate"}),
                ),
            )
            conn.commit()
        return db_path

    def test_get_current_lessons_count_excludes_retired(self, db_with_lessons: Path):
        tracker = AccuracyTracker(db_path=db_with_lessons)
        # Total 4 lessons, 1 is retired -> 3 non-retired
        count = tracker.get_current_lessons_count()
        assert count == 3

    def test_get_retrieved_lessons_filters_domain_and_excludes_retired(self, db_with_lessons: Path):
        tracker = AccuracyTracker(db_path=db_with_lessons)

        dp_lessons = tracker.get_retrieved_lessons(domain="dynamic_programming", limit=2)
        assert len(dp_lessons) >= 1
        assert "knapsack" in dp_lessons[0].lower()
        # Poisoned "When None" must never be returned
        assert all("When None" not in l for l in dp_lessons)

        phys_lessons = tracker.get_retrieved_lessons(domain="numerical_physics", limit=2)
        assert len(phys_lessons) >= 1
        assert "hamiltonian" in phys_lessons[0].lower()

    def test_get_retrieved_lessons_fallback_when_empty(self, tmp_path: Path):
        empty_db = tmp_path / "empty.sqlite"
        tracker = AccuracyTracker(db_path=empty_db)

        for domain in ["dynamic_programming", "graph_algorithms", "concurrency", "numerical_physics"]:
            lessons = tracker.get_retrieved_lessons(domain=domain, limit=2)
            assert len(lessons) >= 1
            assert lessons[0].startswith("When ")
            assert "When None" not in lessons[0]


class TestAblationComparison:
    """Verifies compare_ablation executing challenges with lessons vs without lessons."""

    @pytest.fixture
    def tracker(self, tmp_path: Path):
        db_path = tmp_path / "test_ablation.sqlite"
        return AccuracyTracker(db_path=db_path)

    def test_compare_ablation_offline_hermetic(self, tracker: AccuracyTracker):
        generator = SyntheticChallengeGenerator()
        ablation = tracker.compare_ablation(
            generator=generator,
            num_samples=4,
            use_live_model=False,
            record_to_db=True,
            cycle=1,
        )

        assert ablation["num_samples"] == 4
        with_lessons = ablation["with_lessons"]
        without_lessons = ablation["without_lessons"]

        # With lessons in offline mode uses reference solutions -> Pass@1 = 1.0
        assert with_lessons["pass_at_1"] == 1.0
        assert with_lessons["invariant_compliance"] == 1.0

        # Without lessons in offline mode uses starter code (incomplete) -> Pass@1 = 0.0
        assert without_lessons["pass_at_1"] == 0.0

        # Positive delta in Pass@1
        assert ablation["deltas"]["pass_at_1"] == 1.0
        assert ablation["lesson_advantage_demonstrated"] is True

        # Verified recorded in DB
        latest = tracker.get_latest_metrics()
        assert latest is not None
        assert latest.cycle_iteration == 1
        assert latest.pass_at_1 == 1.0

    def test_compare_ablation_with_custom_solver(self, tracker: AccuracyTracker):
        generator = SyntheticChallengeGenerator()

        # Custom solver: returns reference solution only when lessons_enabled is True
        def mock_solver(challenge, lessons_enabled, retrieved_lessons):
            if lessons_enabled:
                return challenge.reference_solution
            return challenge.starter_code

        ablation = tracker.compare_ablation(
            generator=generator,
            num_samples=2,
            solver_fn=mock_solver,
            record_to_db=False,
        )

        assert ablation["deltas"]["pass_at_1"] > 0.0
        assert ablation["lesson_advantage_demonstrated"] is True
