"""
tests/unit/test_build_stem_sft_dataset.py

Unit and integration tests for Milestone 1 / Feature F9:
SFT Dataset Ingestion Pipeline & Autonomous Self-Play Bridge
(`scripts/models/build_stem_sft_dataset.py`).

Tests:
1. Harvesting verified self-play cycles and APERL lessons from mock and live SQLite databases.
2. Strict exclusion of failed cycles, retired lessons, and legacy 'When None' malformed entries.
3. Alpaca & ShareGPT formatting with canonical lesson conditioning in input/human fields.
4. Sequence length bounding (<= 1024 tokens / <= 4096 chars) & code-block-aware cascade_truncate.
5. Multi-tier deduplication retaining genuinely distinct problems while removing duplicates.
6. Modular LoRA domain routing (`stem-physics-math`, `systems-lowlevel`, `web-data`) compatible with adapter_manager.py.
7. End-to-end ingestion, error handling (missing/corrupt files), and CLI execution.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIVE_DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"

from scripts.models.adapter_manager import AdapterDomain, LoRAAdapterManager
from scripts.models.build_stem_sft_dataset import (
    build_alpaca_records,
    build_sharegpt_records,
    cascade_truncate,
    export_modular_domain_datasets,
    harvest_verified_self_play_samples,
    ingest_self_play_samples,
    main as sft_cli_main,
    route_samples_to_modular_domains,
)


def _create_mock_vectors_db(db_path: Path) -> Path:
    """Creates a realistic mock vectors.sqlite with benchmarks and lessons."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE rag_documents (
                id TEXT NOT NULL,
                collection TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection, id)
            );
        """)
        conn.execute("""
            CREATE TABLE accuracy_benchmarks (
                id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cycle_iteration INTEGER NOT NULL,
                pass_at_1 REAL NOT NULL,
                test_pass_rate REAL NOT NULL,
                avg_patch_iterations REAL NOT NULL,
                invariant_violation_rate REAL NOT NULL,
                lessons_count INTEGER NOT NULL,
                lessons_enabled INTEGER NOT NULL DEFAULT 1,
                details TEXT
            );
        """)

        # Active verified lesson matched by lesson_id
        conn.execute(
            "INSERT INTO rag_documents (id, collection, text, metadata) VALUES (?, 'lessons', ?, ?)",
            (
                "lesson_verlet_01",
                "When integrating Hamiltonian orbital dynamics, do use symplectic Velocity-Verlet, because phase volume and energy remain bounded.",
                json.dumps({
                    "source_task": "syn_phys_01",
                    "domain": "numerical_physics",
                    "language": "python",
                    "status": "verified",
                    "usage_count": 6,
                    "strength": 35.0,
                }),
            ),
        )
        # Candidate lesson matched by source_task
        conn.execute(
            "INSERT INTO rag_documents (id, collection, text, metadata) VALUES (?, 'lessons', ?, ?)",
            (
                "lesson_conc_01",
                "When implementing bounded ring buffers across threads, do use threading.Lock and separate Condition variables, because atomic synchronization prevents race conditions.",
                json.dumps({
                    "source_task": "syn_conc_01",
                    "domain": "systems_concurrency",
                    "language": "python",
                    "status": "candidate",
                    "usage_count": 2,
                    "strength": 15.0,
                }),
            ),
        )
        # Retired lesson - MUST BE EXCLUDED
        conn.execute(
            "INSERT INTO rag_documents (id, collection, text, metadata) VALUES (?, 'lessons', ?, ?)",
            (
                "lesson_retired_01",
                "When solving DP, do use bad heuristic, because stale.",
                json.dumps({
                    "source_task": "syn_dp_retired",
                    "domain": "dynamic_programming",
                    "status": "retired",
                }),
            ),
        )
        # Legacy malformed "When None" lesson - MUST BE EXCLUDED
        conn.execute(
            "INSERT INTO rag_documents (id, collection, text, metadata) VALUES (?, 'lessons', ?, ?)",
            (
                "lesson_malformed_01",
                "When None in python (All unit tests passed), do apply refactoring, because it resolves None.",
                json.dumps({
                    "source_task": "syn_dp_bad_lesson",
                    "domain": "dynamic_programming",
                    "status": "candidate",
                }),
            ),
        )

        # Benchmark 1: Passing Physics sample with prompt + solution + lesson_id
        conn.execute(
            """
            INSERT INTO accuracy_benchmarks (
                id, cycle_iteration, pass_at_1, test_pass_rate,
                avg_patch_iterations, invariant_violation_rate, lessons_count, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bench_phys_pass",
                1,
                1.0,
                1.0,
                0.0,
                0.0,
                2,
                json.dumps({
                    "challenge_id": "syn_phys_01",
                    "domain": "numerical_physics",
                    "language": "python",
                    "difficulty": "expert",
                    "prompt": "Implement symplectic_verlet_orbit(r0, v0, mu, dt, steps).",
                    "solution": "def symplectic_verlet_orbit(r0, v0, mu, dt, steps):\n    return {'positions': [r0]}",
                    "lesson_id": "lesson_verlet_01",
                }),
            ),
        )
        # Benchmark 2: Passing Concurrency sample without lesson_id (matches source_task)
        conn.execute(
            """
            INSERT INTO accuracy_benchmarks (
                id, cycle_iteration, pass_at_1, test_pass_rate,
                avg_patch_iterations, invariant_violation_rate, lessons_count, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bench_conc_pass",
                2,
                1.0,
                1.0,
                0.0,
                0.0,
                2,
                json.dumps({
                    "challenge_id": "syn_conc_01",
                    "domain": "systems_concurrency",
                    "language": "python",
                    "difficulty": "advanced",
                    "prompt": "Implement ThreadSafeRingBuffer with push and pop.",
                    "solution": "class ThreadSafeRingBuffer:\n    pass",
                }),
            ),
        )
        # Benchmark 3: Failed cycle (pass_at_1 = 0.0) - excluded at min_pass_rate=1.0
        conn.execute(
            """
            INSERT INTO accuracy_benchmarks (
                id, cycle_iteration, pass_at_1, test_pass_rate,
                avg_patch_iterations, invariant_violation_rate, lessons_count, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bench_fail_01",
                3,
                0.0,
                0.25,
                1.0,
                1.0,
                2,
                json.dumps({
                    "challenge_id": "syn_fail_01",
                    "domain": "graph_algorithms",
                    "language": "python",
                    "prompt": "Implement max_flow_edmonds_karp.",
                    "solution": "def max_flow_edmonds_karp(): return 0",
                }),
            ),
        )
        # Benchmark 4: Passing DP cycle linked ONLY to retired/malformed lessons -> lesson must stay empty
        conn.execute(
            """
            INSERT INTO accuracy_benchmarks (
                id, cycle_iteration, pass_at_1, test_pass_rate,
                avg_patch_iterations, invariant_violation_rate, lessons_count, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bench_dp_retired_lesson",
                4,
                1.0,
                1.0,
                0.0,
                0.0,
                2,
                json.dumps({
                    "challenge_id": "syn_dp_bad_lesson",
                    "domain": "dynamic_programming",
                    "language": "python",
                    "prompt": "Implement 0/1 knapsack DP solver.",
                    "solution": "def knapsack(w, v, cap): return 0",
                    "lesson_id": "lesson_malformed_01",
                    "lesson": "When None in python, do bad, because bad.",
                }),
            ),
        )
        # Benchmark 5: Corrupt JSON details - gracefully skipped
        conn.execute(
            """
            INSERT INTO accuracy_benchmarks (
                id, cycle_iteration, pass_at_1, test_pass_rate,
                avg_patch_iterations, invariant_violation_rate, lessons_count, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("bench_corrupt", 5, 1.0, 1.0, 0.0, 0.0, 2, "{bad json"),
        )
        conn.commit()
    return db_path


class TestHarvestVerifiedSelfPlaySamples:
    """Verifies harvesting verified self-play records and matching active lessons."""

    def test_harvest_extracts_verified_and_excludes_failed_and_bad_lessons(self, tmp_path: Path) -> None:
        db_path = _create_mock_vectors_db(tmp_path / "mock_vectors.sqlite")
        samples = harvest_verified_self_play_samples(db_path, min_pass_rate=1.0)

        assert len(samples) == 3
        by_id = {s["challenge_id"]: s for s in samples}
        assert "syn_fail_01" not in by_id

        # Physics sample matched verified lesson by lesson_id
        phys = by_id["syn_phys_01"]
        assert phys["domain"] == "numerical_physics"
        assert "symplectic_verlet_orbit" in phys["prompt"]
        assert "def symplectic_verlet_orbit" in phys["solution"]
        assert "Velocity-Verlet" in phys["lesson"]
        assert phys["lesson_id"] == "lesson_verlet_01"

        # Concurrency sample matched candidate lesson by source_task
        conc = by_id["syn_conc_01"]
        assert conc["domain"] == "systems_concurrency"
        assert "threading.Lock" in conc["lesson"]

        # Malformed / retired lesson strictly excluded
        dp = by_id["syn_dp_bad_lesson"]
        assert dp["lesson"] == ""
        assert "When None" not in dp["lesson"]

    def test_harvest_min_pass_rate_threshold(self, tmp_path: Path) -> None:
        db_path = _create_mock_vectors_db(tmp_path / "mock_vectors.sqlite")
        # Include pass_at_1 >= 0.0
        all_samples = harvest_verified_self_play_samples(db_path, min_pass_rate=0.0)
        ids = {s["challenge_id"] for s in all_samples}
        assert "syn_fail_01" in ids
        assert len(all_samples) == 4

    def test_harvest_missing_or_empty_database_returns_empty_list(self, tmp_path: Path) -> None:
        missing_db = tmp_path / "does_not_exist.sqlite"
        assert harvest_verified_self_play_samples(missing_db) == []

        empty_db = tmp_path / "empty.sqlite"
        sqlite3.connect(empty_db).close()
        assert harvest_verified_self_play_samples(empty_db) == []

    def test_harvest_legacy_row_without_prompt_resolves_via_generator(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE accuracy_benchmarks (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cycle_iteration INTEGER NOT NULL,
                    pass_at_1 REAL NOT NULL,
                    test_pass_rate REAL NOT NULL,
                    avg_patch_iterations REAL NOT NULL,
                    invariant_violation_rate REAL NOT NULL,
                    lessons_count INTEGER NOT NULL,
                    lessons_enabled INTEGER NOT NULL DEFAULT 1,
                    details TEXT
                );
            """)
            conn.execute(
                """
                INSERT INTO accuracy_benchmarks (
                    id, cycle_iteration, pass_at_1, test_pass_rate,
                    avg_patch_iterations, invariant_violation_rate, lessons_count, details
                ) VALUES ('bench_leg', 1, 1.0, 1.0, 0.0, 0.0, 0, ?)
                """,
                (json.dumps({"challenge_id": "syn_legacy_1", "domain": "dynamic_programming"}),),
            )
            conn.commit()

        samples = harvest_verified_self_play_samples(db_path)
        assert len(samples) == 1
        assert "knapsack" in samples[0]["prompt"].lower() or len(samples[0]["prompt"]) > 20
        assert len(samples[0]["solution"]) > 20

    def test_harvest_live_vectors_sqlite_if_present(self) -> None:
        if not LIVE_DB_PATH.exists():
            pytest.skip("backend/storage/vectors.sqlite not present")
        samples = harvest_verified_self_play_samples(LIVE_DB_PATH, min_pass_rate=1.0)
        assert isinstance(samples, list)
        for s in samples:
            assert "When None" not in s.get("lesson", "")
            assert s["pass_at_1"] >= 1.0


class TestFormattingAndLessonConditioning:
    """Verifies Alpaca & ShareGPT conversion and lesson conditioning."""

    def test_build_alpaca_records_with_and_without_lessons(self) -> None:
        samples = [
            {
                "challenge_id": "syn_1",
                "domain": "numerical_physics",
                "language": "python",
                "difficulty": "expert",
                "prompt": "Integrate Kepler orbit.",
                "solution": "def integrate():\n    return True",
                "lesson": "When integrating Hamiltonian systems, do use Velocity-Verlet, because phase volume is preserved.",
            }
        ]
        conditioned = build_alpaca_records(samples, condition_with_lessons=True)
        assert len(conditioned) == 1
        rec = conditioned[0]
        assert set(["instruction", "input", "output", "domain", "lesson"]).issubset(rec.keys())
        assert "Integrate Kepler orbit." in rec["instruction"]
        assert "Velocity-Verlet" in rec["input"]
        assert "def integrate()" in rec["output"]
        assert rec["domain"] == "numerical_physics"

        unconditioned = build_alpaca_records(samples, condition_with_lessons=False)
        assert len(unconditioned) == 1
        assert unconditioned[0]["input"] == ""
        assert unconditioned[0]["lesson"] == ""

    def test_build_sharegpt_records_schema_and_lesson_injection(self) -> None:
        samples = [
            {
                "challenge_id": "syn_2",
                "domain": "graph_algorithms",
                "language": "python",
                "difficulty": "advanced",
                "prompt": "Compute max flow with Edmonds-Karp.",
                "solution": "def max_flow():\n    return 23",
                "lesson": "When computing max flow, do use BFS augmenting paths, because O(V*E^2) is guaranteed.",
            }
        ]
        sg = build_sharegpt_records(samples, condition_with_lessons=True)
        assert len(sg) == 1
        convs = sg[0]["conversations"]
        assert len(convs) == 2
        assert convs[0]["from"] == "human"
        assert convs[1]["from"] == "gpt"
        assert "Edmonds-Karp" in convs[0]["value"]
        assert "BFS augmenting paths" in convs[0]["value"]
        assert "return 23" in convs[1]["value"]

        sg_no_lesson = build_sharegpt_records(samples, condition_with_lessons=False)
        assert "BFS augmenting paths" not in sg_no_lesson[0]["conversations"][0]["value"]


class TestSequenceCutoffAndCascadeTruncate:
    """Verifies <= 1024 token / <= 4096 char sequence bounding and code fence preservation."""

    def test_cascade_truncate_preserves_short_text_and_bounds_long_text(self) -> None:
        short = "def ok(): return 1"
        assert cascade_truncate(short, max_chars=4096) == short

        oversized_code = "```python\n" + ("x = 1 + 2\n" * 600) + "```"
        truncated = cascade_truncate(oversized_code, max_chars=4096)
        assert len(truncated) <= 4096
        assert "[truncated]" in truncated
        # Balanced markdown code fences after truncation
        assert truncated.count("```") % 2 == 0

    def test_alpaca_and_sharegpt_strictly_enforce_1024_token_cutoff(self) -> None:
        huge_samples = [
            {
                "challenge_id": "syn_huge",
                "domain": "dynamic_programming",
                "language": "python",
                "difficulty": "expert",
                "prompt": "P " * 1500,
                "solution": "```python\n" + ("dp[i] = i\n" * 800) + "```",
                "lesson": "When DP, " + ("remember state " * 200) + ", because fast.",
            }
        ]
        alpaca = build_alpaca_records(huge_samples, condition_with_lessons=True, max_tokens=1024)
        assert len(alpaca) == 1
        r = alpaca[0]
        total_chars = len(r["instruction"]) + len(r["input"]) + len(r["output"])
        assert total_chars <= 4096

        sg = build_sharegpt_records(huge_samples, condition_with_lessons=True, max_tokens=1024)
        assert len(sg) == 1
        sg_chars = sum(len(turn["value"]) for turn in sg[0]["conversations"])
        assert sg_chars <= 4096


class TestModularDomainRouting:
    """Verifies sample routing to modular LoRA domains from adapter_manager.py."""

    def test_route_samples_to_modular_domains(self) -> None:
        samples = [
            {
                "challenge_id": "c_phys",
                "domain": "numerical_physics",
                "language": "python",
                "instruction": "Integrate Kepler orbit via Velocity-Verlet.",
                "output": "def symplectic_verlet_orbit(): pass",
            },
            {
                "challenge_id": "c_dp",
                "domain": "dynamic_programming",
                "language": "python",
                "instruction": "Solve 0/1 multi-constrained knapsack.",
                "output": "def multi_constrained_knapsack(): pass",
            },
            {
                "challenge_id": "c_graph",
                "domain": "graph_algorithms",
                "language": "python",
                "instruction": "Compute Edmonds-Karp max flow.",
                "output": "def max_flow_edmonds_karp(): pass",
            },
            {
                "challenge_id": "c_conc",
                "domain": "systems_concurrency",
                "language": "python",
                "instruction": "Implement ThreadSafeRingBuffer with threading.Lock.",
                "output": "class ThreadSafeRingBuffer: pass",
            },
            {
                "challenge_id": "c_rust",
                "domain": "systems",
                "language": "rust",
                "instruction": "Implement atomic spinlock.",
                "output": "pub fn lock() {}",
            },
            {
                "challenge_id": "c_web",
                "domain": "web_api",
                "language": "php",
                "instruction": "Build REST endpoint querying SQLite FTS5.",
                "output": "<?php echo json_encode([]);",
            },
            {
                "challenge_id": "c_ts",
                "domain": "",
                "language": "typescript",
                "instruction": "Parse JSON SSE stream.",
                "output": "export function parseSSE() {}",
            },
        ]

        routed = route_samples_to_modular_domains(samples)
        expected_domains = {d.value for d in LoRAAdapterManager().list_registered_domains()}
        assert set(routed.keys()) == expected_domains

        stem_ids = {s["challenge_id"] for s in routed[AdapterDomain.STEM_PHYSICS_MATH.value]}
        sys_ids = {s["challenge_id"] for s in routed[AdapterDomain.SYSTEMS_LOWLEVEL.value]}
        web_ids = {s["challenge_id"] for s in routed[AdapterDomain.WEB_DATA.value]}

        assert {"c_phys", "c_dp", "c_graph"}.issubset(stem_ids)
        assert {"c_conc", "c_rust"}.issubset(sys_ids)
        assert {"c_web", "c_ts"}.issubset(web_ids)

    def test_route_samples_returns_all_keys_on_empty_input(self) -> None:
        routed = route_samples_to_modular_domains([])
        assert set(routed.keys()) == {"stem-physics-math", "systems-lowlevel", "web-data"}
        assert all(v == [] for v in routed.values())


class TestIngestSelfPlaySamplesAndCli:
    """Verifies full ingestion, deduplication, file error handling, and CLI."""

    def test_ingest_json_deduplicates_and_exports_alpaca_and_sharegpt(self, tmp_path: Path) -> None:
        raw_samples = [
            {
                "challenge_id": "syn_a",
                "domain": "dynamic_programming",
                "language": "python",
                "prompt": "Solve multi-constrained 0/1 knapsack with weight and volume bounds.",
                "solution": "def multi_constrained_knapsack(w, v, val, mw, mv):\n    return 0, []",
                "lesson": "When solving 0/1 knapsack, do reverse iteration, because O(W*V) space.",
            },
            # Exact duplicate of syn_a
            {
                "challenge_id": "syn_a_dup",
                "domain": "dynamic_programming",
                "language": "python",
                "prompt": "Solve multi-constrained 0/1 knapsack with weight and volume bounds.",
                "solution": "def multi_constrained_knapsack(w, v, val, mw, mv):\n    return 0, []",
                "lesson": "When solving 0/1 knapsack, do reverse iteration, because O(W*V) space.",
            },
            # Distinct problem in same domain -> MUST BE RETAINED
            {
                "challenge_id": "syn_b",
                "domain": "dynamic_programming",
                "language": "python",
                "prompt": "Solve exact Traveling Salesperson Problem using Held-Karp bitmask DP.",
                "solution": "def solve_tsp_bitmask(dist_matrix):\n    return 0, [0]",
                "lesson": "When solving TSP on small graphs, do use Held-Karp bitmask DP, because O(N^2 2^N).",
            },
        ]
        in_path = tmp_path / "verified_samples.json"
        in_path.write_text(json.dumps(raw_samples, indent=2), encoding="utf-8")

        out_alpaca = tmp_path / "out_alpaca.json"
        count_alpaca = ingest_self_play_samples(
            verified_samples_path=in_path,
            output_dataset_path=out_alpaca,
            format_type="alpaca",
            max_tokens=1024,
        )
        assert count_alpaca == 2
        exported = json.loads(out_alpaca.read_text(encoding="utf-8"))
        assert len(exported) == 2
        assert all("instruction" in r and "input" in r and "output" in r for r in exported)

        out_sharegpt = tmp_path / "out_sharegpt.json"
        count_sg = ingest_self_play_samples(
            verified_samples_path=in_path,
            output_dataset_path=out_sharegpt,
            format_type="sharegpt",
            max_tokens=1024,
        )
        assert count_sg == 2
        exported_sg = json.loads(out_sharegpt.read_text(encoding="utf-8"))
        assert all("conversations" in r for r in exported_sg)

    def test_ingest_supports_sqlite_input_and_domain_splits(self, tmp_path: Path) -> None:
        db_path = _create_mock_vectors_db(tmp_path / "vectors.sqlite")
        out_path = tmp_path / "sft_from_db.json"
        count = ingest_self_play_samples(db_path, out_path, format_type="alpaca", max_tokens=1024)
        assert count == 3

        samples = harvest_verified_self_play_samples(db_path)
        split_counts = export_modular_domain_datasets(samples, tmp_path / "modular_splits", format_type="alpaca")
        assert split_counts["stem-physics-math"] == 2
        assert split_counts["systems-lowlevel"] == 1
        assert split_counts["web-data"] == 0
        assert (tmp_path / "modular_splits" / "stem-physics-math.json").exists()

    def test_ingest_error_handling_missing_and_corrupt_files(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ingest_self_play_samples(tmp_path / "nonexistent.json", tmp_path / "out.json")

        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            ingest_self_play_samples(corrupt, tmp_path / "out.json")

        wrong_type = tmp_path / "wrong_type.json"
        wrong_type.write_text(json.dumps({"unexpected": 123}), encoding="utf-8")
        with pytest.raises(ValueError):
            ingest_self_play_samples(wrong_type, tmp_path / "out.json")

        good = tmp_path / "good.json"
        good.write_text(json.dumps([]), encoding="utf-8")
        with pytest.raises(ValueError):
            ingest_self_play_samples(good, tmp_path / "out.json", format_type="unknown_fmt")

    def test_cli_entrypoint_execution(self, tmp_path: Path) -> None:
        db_path = _create_mock_vectors_db(tmp_path / "cli_vectors.sqlite")
        out_path = tmp_path / "cli_dataset.json"
        split_dir = tmp_path / "cli_splits"

        exit_code = sft_cli_main([
            "--db-path", str(db_path),
            "--output", str(out_path),
            "--format", "alpaca",
            "--min-pass-rate", "1.0",
            "--split-domains-dir", str(split_dir),
        ])
        assert exit_code == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(data) == 3
        assert (split_dir / "stem-physics-math.json").exists()
        assert (split_dir / "systems-lowlevel.json").exists()

    def test_end_to_end_self_play_cycle_to_sft_bridge(self, tmp_path: Path) -> None:
        from scripts.learning.accuracy_tracker import AccuracyTracker
        from scripts.learning.aperl import APERLEngine
        from scripts.learning.autonomous_self_play import run_self_play_cycle
        from scripts.learning.ebbinghaus import EbbinghausConsolidator
        from scripts.learning.synthetic_challenge_generator import SyntheticChallengeGenerator

        db_path = tmp_path / "bridge_vectors.sqlite"
        gen = SyntheticChallengeGenerator()
        aperl = APERLEngine(db_path=db_path)
        cons = EbbinghausConsolidator()
        tracker = AccuracyTracker(db_path=db_path)

        # Run 2 cycles in different domains
        for i in (1, 2):
            res = run_self_play_cycle(
                generator=gen,
                aperl=aperl,
                consolidator=cons,
                iteration=i,
                tracker=tracker,
                db_path=db_path,
                use_live_model=False,
            )
            assert res["success"] is True

        harvested = harvest_verified_self_play_samples(db_path, min_pass_rate=1.0)
        assert len(harvested) == 2
        assert all(s["prompt"] and s["solution"] and s["lesson"] for s in harvested)
        assert all("When None" not in s["lesson"] for s in harvested)

        out_file = tmp_path / "bridge_sft.json"
        count = ingest_self_play_samples(db_path, out_file, format_type="alpaca", max_tokens=1024)
        assert count == 2
        records = json.loads(out_file.read_text(encoding="utf-8"))
        assert all("Engineering Lesson:" in r["input"] for r in records)

    def test_harvest_rejects_partial_test_pass_and_ast_violation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "guard.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE accuracy_benchmarks (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cycle_iteration INTEGER NOT NULL,
                    pass_at_1 REAL NOT NULL,
                    test_pass_rate REAL NOT NULL,
                    avg_patch_iterations REAL NOT NULL,
                    invariant_violation_rate REAL NOT NULL,
                    lessons_count INTEGER NOT NULL,
                    lessons_enabled INTEGER NOT NULL DEFAULT 1,
                    details TEXT
                );
            """)
            # High pass_at_1 but low test_pass_rate
            conn.execute(
                "INSERT INTO accuracy_benchmarks VALUES ('b1', CURRENT_TIMESTAMP, 1, 1.0, 0.5, 0.0, 0.0, 0, 1, ?)",
                (json.dumps({"challenge_id": "c1", "domain": "physics", "prompt": "P", "solution": "S"}),),
            )
            # Marked ast_violation=True
            conn.execute(
                "INSERT INTO accuracy_benchmarks VALUES ('b2', CURRENT_TIMESTAMP, 2, 1.0, 1.0, 0.0, 1.0, 0, 1, ?)",
                (json.dumps({"challenge_id": "c2", "domain": "physics", "prompt": "P2", "solution": "S2", "ast_violation": True}),),
            )
            conn.commit()

        assert harvest_verified_self_play_samples(db_path, min_pass_rate=1.0) == []
        # Even at min_pass_rate=0.5, ast_violation=True must stay excluded
        samples = harvest_verified_self_play_samples(db_path, min_pass_rate=0.5)
        assert [s["challenge_id"] for s in samples] == ["c1"]

    def test_truncate_alpaca_fields_strictly_clamps_small_limits_and_preserves_fences(self) -> None:
        from scripts.models.build_stem_sft_dataset import truncate_alpaca_fields

        inst, inp, out = truncate_alpaca_fields("A" * 40, "B" * 40, "C" * 250, max_char_limit=64)
        assert len(inst) + len(inp) + len(out) <= 64

        inst2, inp2, out2 = truncate_alpaca_fields("A" * 40, "B" * 40, "C" * 40, max_char_limit=64)
        assert len(inst2) + len(inp2) + len(out2) <= 64

        code = "```python\n" + ("x = 1\n" * 80) + "```"
        i3, p3, o3 = truncate_alpaca_fields("P" * 50, "L" * 100, code, max_char_limit=300)
        assert len(i3) + len(p3) + len(o3) <= 300
        assert o3.count("```") % 2 == 0

    def test_ingest_supports_question_answer_tuples_jsonl_and_filters_unverified_json(self, tmp_path: Path) -> None:
        jsonl_path = tmp_path / "qa_tuples.jsonl"
        rows = [
            {
                "question": "Implement binary search on sorted list.",
                "answer": "def bsearch(a, x): return -1",
                "lesson": "When searching sorted arrays, do narrow midpoint bounds, because O(log N).",
                "domain": "dynamic_programming",
                "language": "python",
                "pass_at_1": 1.0,
                "test_pass_rate": 1.0,
            },
            {
                "question": "Implement lock-free counter.",
                "answer": "def inc(): return 1",
                "lesson": "When retired advice, do bad, because stale.",
                "lesson_status": "retired",
                "domain": "systems_concurrency",
                "language": "python",
                "pass_at_1": 1.0,
                "test_pass_rate": 1.0,
            },
            {
                "question": "Failing question should be filtered out.",
                "answer": "def fail(): pass",
                "domain": "graph_algorithms",
                "language": "python",
                "pass_at_1": 0.0,
                "test_pass_rate": 0.0,
            },
            {
                "question": "AST violation should be filtered out.",
                "answer": "import os",
                "domain": "numerical_physics",
                "language": "python",
                "pass_at_1": 1.0,
                "test_pass_rate": 1.0,
                "ast_violation": True,
            },
        ]
        jsonl_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

        out_path = tmp_path / "qa_out.json"
        count = ingest_self_play_samples(jsonl_path, out_path, format_type="alpaca", min_pass_rate=1.0)
        assert count == 2
        exported = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(exported) == 2
        assert "binary search" in exported[0]["instruction"].lower()
        assert "def bsearch" in exported[0]["output"]
        assert "Engineering Lesson:" in exported[0]["input"]
        # Retired lesson stripped on second record
        assert exported[1]["lesson"] == ""
        assert exported[1]["input"] == ""

    def test_harvest_excludes_inline_lesson_matching_retired_db_text(self, tmp_path: Path) -> None:
        db_path = _create_mock_vectors_db(tmp_path / "retired_inline.sqlite")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO accuracy_benchmarks (
                    id, cycle_iteration, pass_at_1, test_pass_rate,
                    avg_patch_iterations, invariant_violation_rate, lessons_count, details
                ) VALUES ('bench_ret_txt', 6, 1.0, 1.0, 0.0, 0.0, 1, ?)
                """,
                (json.dumps({
                    "challenge_id": "syn_ret_txt",
                    "domain": "dynamic_programming",
                    "prompt": "Solve DP problem X.",
                    "solution": "def solve_dp(): return 1",
                    "lesson": "When solving DP, do use bad heuristic, because stale.",
                }),),
            )
            conn.commit()

        samples = harvest_verified_self_play_samples(db_path, min_pass_rate=1.0)
        by_id = {s["challenge_id"]: s for s in samples}
        assert by_id["syn_ret_txt"]["lesson"] == ""


