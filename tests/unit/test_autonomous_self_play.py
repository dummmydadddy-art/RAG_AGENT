"""
tests/unit/test_autonomous_self_play.py

Unit tests for Feature F11: Autonomous Self-Play Closed-Loop Integration.
Verifies domain rotation across 4 expanded domains, prior lesson retrieval,
Win32 Job Object sandboxed execution, APERL positive & edge-case reflection without 'When None...',
Ebbinghaus periodic consolidation, and accuracy tracking integration.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import pytest

from scripts.learning.autonomous_self_play import (
    DOMAINS,
    run_self_play_cycle,
    query_rag_lessons,
    reinforce_retrieved_lessons,
    _count_active_lessons,
)
from scripts.learning.synthetic_challenge_generator import (
    SyntheticChallenge,
    SyntheticChallengeGenerator,
)
from scripts.learning.aperl import APERLEngine, ExecutionTrace
from scripts.learning.ebbinghaus import (
    EbbinghausConsolidator,
    consolidate_database_lessons,
    reinforce_lesson_usage,
)
from scripts.learning.accuracy_tracker import AccuracyTracker


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_self_play_vectors.sqlite"
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                id TEXT NOT NULL,
                collection TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection, id)
            );
        """)
        conn.commit()
    return db_file


class TestAutonomousSelfPlayClosedLoop:
    """Verifies end-to-end self-play cycle execution and closed-loop components."""

    def test_domain_rotation_across_4_expanded_domains(self, test_db: Path):
        generator = SyntheticChallengeGenerator()
        aperl = APERLEngine(db_path=test_db)
        consolidator = EbbinghausConsolidator()
        tracker = AccuracyTracker(db_path=test_db)

        observed_domains = []
        for i in range(1, 5):
            res = run_self_play_cycle(
                generator=generator,
                aperl=aperl,
                consolidator=consolidator,
                iteration=i,
                tracker=tracker,
                db_path=test_db,
                use_live_model=False,  # Hermetic offline reference solution
            )
            observed_domains.append(res["domain"])

        assert observed_domains == [
            "dynamic_programming",
            "graph_algorithms",
            "systems_concurrency",
            "numerical_physics",
        ]

    def test_run_self_play_cycle_success_positive_aperl(self, test_db: Path):
        generator = SyntheticChallengeGenerator()
        aperl = APERLEngine(db_path=test_db)
        consolidator = EbbinghausConsolidator()
        tracker = AccuracyTracker(db_path=test_db)

        res = run_self_play_cycle(
            generator=generator,
            aperl=aperl,
            consolidator=consolidator,
            iteration=1,
            tracker=tracker,
            db_path=test_db,
            use_live_model=False,
            domain_override="dynamic_programming",
        )

        assert res["success"] is True
        assert res["lesson_id"].startswith("lesson_")
        assert res["benchmark_id"].startswith("bench_")

        # Verify lesson in database
        with sqlite3.connect(test_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT text, metadata FROM rag_documents WHERE id = ?", (res["lesson_id"],))
            row = cur.fetchone()
            assert row is not None
            text, meta_raw = row
            # CRITICAL: No "When None" flaw
            assert "When None" not in text
            assert text.startswith("When ")
            assert ", do " in text
            assert ", because " in text
            assert "knapsack" in text.lower() or "dp" in text.lower() or "reverse" in text.lower()

            meta = json.loads(meta_raw)
            assert meta["status"] == "candidate"
            assert meta["domain"] == "dynamic_programming"

        # Verify accuracy benchmark
        latest = tracker.get_latest_metrics()
        assert latest is not None
        assert latest.pass_at_1 == 1.0
        assert latest.test_pass_rate == 1.0
        assert latest.invariant_violation_rate == 0.0

    def test_run_self_play_cycle_retrieves_and_reinforces_lessons(self, test_db: Path):
        aperl = APERLEngine(db_path=test_db)
        # Pre-seed a verified lesson in the database
        seed_trace = ExecutionTrace(
            task_id="task_seed_dp",
            language="python",
            error_type="None",
            error_message="All unit tests and physical constraints passed",
            failed_code="def knapsack(): pass",
            fixed_code="def multi_constrained_knapsack(weights, volumes, values, max_weight, max_volume): pass",
            test_output="PASSED",
            domain="dynamic_programming",
        )
        lesson_id = aperl.process_and_save(seed_trace)

        generator = SyntheticChallengeGenerator()
        consolidator = EbbinghausConsolidator()
        tracker = AccuracyTracker(db_path=test_db)

        # Run cycle which retrieves the lesson
        run_self_play_cycle(
            generator=generator,
            aperl=aperl,
            consolidator=consolidator,
            iteration=1,
            tracker=tracker,
            db_path=test_db,
            use_live_model=False,
            domain_override="dynamic_programming",
        )

        # Verify usage count reinforced
        with sqlite3.connect(test_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT metadata FROM rag_documents WHERE id = ?", (lesson_id,))
            meta = json.loads(cur.fetchone()[0])
            assert meta["usage_count"] >= 1
            assert meta["strength"] >= 10.0

    def test_periodic_ebbinghaus_consolidation_every_5_cycles(self, test_db: Path):
        generator = SyntheticChallengeGenerator()
        aperl = APERLEngine(db_path=test_db)
        consolidator = EbbinghausConsolidator()
        tracker = AccuracyTracker(db_path=test_db)

        # Iteration 4: No consolidation
        res4 = run_self_play_cycle(
            generator=generator,
            aperl=aperl,
            consolidator=consolidator,
            iteration=4,
            tracker=tracker,
            db_path=test_db,
            use_live_model=False,
        )
        assert res4["consolidation_report"] is None

        # Iteration 5: Consolidation triggers
        res5 = run_self_play_cycle(
            generator=generator,
            aperl=aperl,
            consolidator=consolidator,
            iteration=5,
            tracker=tracker,
            db_path=test_db,
            use_live_model=False,
        )
        assert res5["consolidation_report"] is not None
        assert "evaluated_count" in res5["consolidation_report"]
        assert "retired_count" in res5["consolidation_report"]
        assert "promoted_count" in res5["consolidation_report"]


class TestEbbinghausConsolidationHooks:
    """Verifies Ebbinghaus memory consolidation database operations and spaced repetition."""

    def test_ebbinghaus_promotes_verified_and_retires_stale(self, test_db: Path):
        with sqlite3.connect(test_db) as conn:
            # 1. High utility lesson (usage=6, delta_t=1.0 day -> R >= 0.70)
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l_promote",
                    "When solving DP, do reverse iteration, because it prevents reuse.",
                    json.dumps({
                        "status": "candidate",
                        "strength": 10.0,
                        "usage_count": 6,
                        "last_used_at": None,  # parsed as current time -> delta_t ~ 0
                    }),
                ),
            )
            # 2. Stale unreinforced lesson (usage=0, delta_t=50 days -> R < 0.20)
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l_retire",
                    "When old problem, do something, because reason.",
                    json.dumps({
                        "status": "candidate",
                        "strength": 10.0,
                        "usage_count": 0,
                        "created_at": 1000.0,  # 50+ years ago
                    }),
                ),
            )
            # 3. Legacy "When None" poisoned lesson
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l_quarantine",
                    "When None in python, do refactor, because it prevents None.",
                    json.dumps({"status": "candidate", "usage_count": 0}),
                ),
            )
            conn.commit()

        report = consolidate_database_lessons(db_path=test_db)
        assert "l_promote" in report["promoted_ids"]
        assert "l_retire" in report["retired_ids"]
        assert "l_quarantine" in report["retired_ids"]

        # Check DB states
        with sqlite3.connect(test_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT metadata FROM rag_documents WHERE id = 'l_promote'")
            m_prom = json.loads(cur.fetchone()[0])
            assert m_prom["status"] == "verified"
            assert m_prom["strength"] >= 30.0

            cur.execute("SELECT metadata FROM rag_documents WHERE id = 'l_retire'")
            m_ret = json.loads(cur.fetchone()[0])
            assert m_ret["status"] == "retired"

            cur.execute("SELECT metadata FROM rag_documents WHERE id = 'l_quarantine'")
            m_quar = json.loads(cur.fetchone()[0])
            assert m_quar["status"] == "retired"
            assert "Quarantined" in m_quar["status_reason"]

    def test_reinforce_lesson_usage_auto_retire_on_failures(self, test_db: Path):
        with sqlite3.connect(test_db) as conn:
            conn.execute(
                "INSERT INTO rag_documents VALUES (?, 'lessons', ?, ?, CURRENT_TIMESTAMP)",
                (
                    "l_fail_test",
                    "When test fail, do fix, because broken.",
                    json.dumps({
                        "status": "candidate",
                        "strength": 10.0,
                        "usage_count": 1,
                        "success_count": 0,
                        "fail_count": 1,
                    }),
                ),
            )
            conn.commit()

        # Second failure -> fail_count=2, success=0/2 (0%) -> auto-retire
        res = reinforce_lesson_usage("l_fail_test", success=False, db_path=test_db)
        assert res["success"] is True
        assert res["status"] == "retired"


class TestAPERLReflectionUnitTaxonomy:
    """Verifies all failure and positive reflection branches in APERL."""

    def test_aperl_positive_reflection_taxonomies(self):
        aperl = APERLEngine()

        # 1. DP Knapsack
        t_dp = ExecutionTrace(
            task_id="dp_knapsack",
            language="python",
            error_type="None",
            error_message="All unit tests and physical constraints passed",
            failed_code="def multi_constrained_knapsack(): pass",
            fixed_code="def multi_constrained_knapsack(weights, volumes, values, max_weight, max_volume): pass",
            test_output="PASSED",
            domain="dynamic_programming",
        )
        l_dp = aperl.distill_lesson(t_dp)
        assert "knapsack" in l_dp.situation.lower()
        assert "reverse" in l_dp.action.lower()
        assert "When None" not in l_dp.to_canonical_format()

        # 2. Graph Edmonds-Karp
        t_graph = ExecutionTrace(
            task_id="graph_flow",
            language="python",
            error_type="None",
            error_message="All unit tests and physical constraints passed",
            failed_code="def max_flow_edmonds_karp(): pass",
            fixed_code="def max_flow_edmonds_karp(capacity, source, sink): pass",
            test_output="PASSED",
            domain="graph_algorithms",
        )
        l_graph = aperl.distill_lesson(t_graph)
        assert "flow" in l_graph.situation.lower()
        assert "edmonds-karp" in l_graph.action.lower()

        # 3. Concurrency Ring Buffer
        t_conc = ExecutionTrace(
            task_id="conc_ring",
            language="python",
            error_type="None",
            error_message="All unit tests and physical constraints passed",
            failed_code="class BoundedRingBuffer: pass",
            fixed_code="class BoundedRingBuffer: def push(): pass",
            test_output="PASSED",
            domain="concurrency",
        )
        l_conc = aperl.distill_lesson(t_conc)
        assert "ring" in l_conc.situation.lower() or "fifo" in l_conc.situation.lower()
        assert "lock" in l_conc.action.lower() and "condition" in l_conc.action.lower()

        # 4. Numerical Physics Verlet
        t_phys = ExecutionTrace(
            task_id="phys_verlet",
            language="python",
            error_type="None",
            error_message="All unit tests and physical constraints passed",
            failed_code="def symplectic_velocity_verlet(): pass",
            fixed_code="def symplectic_velocity_verlet(q0, p0, dt, steps, grad_v): pass",
            test_output="PASSED",
            domain="numerical_physics",
        )
        l_phys = aperl.distill_lesson(t_phys)
        assert "hamiltonian" in l_phys.situation.lower() or "kepler" in l_phys.situation.lower()
        assert "velocity-verlet" in l_phys.action.lower() or "symplectic" in l_phys.action.lower()

    def test_aperl_failure_reflection_taxonomies(self):
        aperl = APERLEngine()

        # AST Violation
        t_ast = ExecutionTrace(
            task_id="ast_fail",
            language="python",
            error_type="ASTViolation",
            error_message="Forbidden module 'os' imported",
            failed_code="import os",
            fixed_code="import math",
            test_output="FAILED",
        )
        l_ast = aperl.distill_lesson(t_ast)
        assert "security-sandboxed" in l_ast.situation
        assert "restrict imports" in l_ast.action
        assert "ast security guard" in l_ast.reason.lower()

        # Timeout
        t_to = ExecutionTrace(
            task_id="to_fail",
            language="python",
            error_type="TimeoutError",
            error_message="Execution timed out after 5.0s",
            failed_code="def slow(): while True: pass",
            fixed_code="def fast(): pass",
            test_output="FAILED",
        )
        l_to = aperl.distill_lesson(t_to)
        assert "state spaces" in l_to.situation or "graphs" in l_to.situation
        assert "memoization" in l_to.action or "tables" in l_to.action

        # Symplectic Invariant AssertionError
        t_inv = ExecutionTrace(
            task_id="inv_fail",
            language="python",
            error_type="AssertionError",
            error_message="Symplectic energy drift exceeded tolerance",
            failed_code="euler_step()",
            fixed_code="verlet_step()",
            test_output="FAILED",
        )
        l_inv = aperl.distill_lesson(t_inv)
        assert "hamiltonian" in l_inv.situation or "physics" in l_inv.situation
        assert "velocity-verlet" in l_inv.action or "symplectic" in l_inv.action
