"""
scripts/learning/autonomous_self_play.py

Active Background Self-Play and Lesson Harvesting Daemon (Milestone 3 / Feature F11).
Continuously synthesizes challenges across 4 expanded domains, retrieves RAG lessons,
autonomously solves with CoT reasoning, executes inside Win32 Job Object sandbox,
distills lessons via APERL, records accuracy benchmarks, and periodically consolidates
memory via Ebbinghaus spaced repetition.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.learning.synthetic_challenge_generator import (
    SyntheticChallenge,
    SyntheticChallengeGenerator,
    solve_challenge,
)
from scripts.learning.aperl import APERLEngine, ExecutionTrace
from scripts.learning.ebbinghaus import (
    EbbinghausConsolidator,
    consolidate_database_lessons,
    reinforce_lesson_usage,
)
from scripts.learning.accuracy_tracker import AccuracyTracker
from src.sandbox.win32_job import execute_sandboxed_code, ExecutionResult

LOG_DIR = ROOT / "evals" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "autonomous_self_play.log"
STATE_FILE = LOG_DIR / "autonomous_self_play_state.json"
STOP_FILE = LOG_DIR / "autonomous_self_play.stop"
PID_FILE = LOG_DIR / "autonomous_self_play.pid"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("autonomous_self_play")

DOMAINS = [
    "dynamic_programming",
    "graph_algorithms",
    "systems_concurrency",
    "numerical_physics",
]


def query_rag_lessons(
    domain: str,
    db_path: Optional[Path] = None,
    limit: int = 3,
) -> List[str]:
    """
    Retrieves the top-k most relevant active lessons from the SQLite RAG store.
    Excludes retired lessons and prioritizes domain-relevant keywords.
    """
    target_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
    if not target_path.exists():
        return []

    domain_keywords = {
        "dynamic_programming": ["knapsack", "dp", "tsp", "substructure", "capacity"],
        "graph_algorithms": ["flow", "cut", "bellman", "edmonds", "cycle", "graph"],
        "systems_concurrency": ["concurrency", "thread", "lock", "ring", "pool", "race"],
        "concurrency": ["concurrency", "thread", "lock", "ring", "pool", "race"],
        "numerical_physics": ["symplectic", "energy", "orbit", "verlet", "oscillator", "physics"],
    }
    keywords = domain_keywords.get(domain, [domain.lower()])

    try:
        with sqlite3.connect(target_path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
            if not cursor.fetchone():
                return []
            cursor.execute(
                "SELECT id, text, metadata FROM rag_documents WHERE collection = 'lessons' ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()

        matched: List[Tuple[float, str]] = []
        for doc_id, text, meta_raw in rows:
            text_str = str(text)
            if "When None" in text_str:
                continue
            meta = json.loads(meta_raw) if meta_raw else {}
            if meta.get("status") == "retired":
                continue

            text_lower = text_str.lower()
            score = sum(2.0 for kw in keywords if kw in text_lower)
            usage = int(meta.get("usage_count", 0))
            score += min(3.0, usage * 0.5)

            if score > 0:
                matched.append((score, text_str))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in matched[:limit]]
    except Exception as e:
        logger.warning(f"Error querying RAG lessons from {target_path}: {e}")
        return []


def reinforce_retrieved_lessons(
    lessons: List[str],
    db_path: Optional[Path] = None,
) -> None:
    """Reinforces utility count and strength of retrieved lessons in vectors.sqlite."""
    if not lessons:
        return
    target_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
    if not target_path.exists():
        return

    try:
        with sqlite3.connect(target_path, timeout=5.0) as conn:
            cursor = conn.cursor()
            for text in lessons:
                cursor.execute(
                    "SELECT id FROM rag_documents WHERE collection = 'lessons' AND text = ?",
                    (text,),
                )
                row = cursor.fetchone()
                if row:
                    doc_id = row[0]
                    reinforce_lesson_usage(doc_id, success=True, db_path=target_path)
    except Exception as e:
        logger.warning(f"Failed to reinforce lessons in {target_path}: {e}")


def _count_active_lessons(db_path: Optional[Path] = None) -> int:
    """Returns total active non-retired lessons in vectors.sqlite."""
    target_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
    if not target_path.exists():
        return 0
    try:
        with sqlite3.connect(target_path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
            if not cursor.fetchone():
                return 0
            cursor.execute("SELECT metadata FROM rag_documents WHERE collection = 'lessons'")
            rows = cursor.fetchall()
            count = 0
            for r in rows:
                meta = json.loads(r[0]) if r[0] else {}
                if meta.get("status") != "retired":
                    count += 1
            return count
    except Exception:
        return 0


def run_self_play_cycle(
    generator: SyntheticChallengeGenerator,
    aperl: APERLEngine,
    consolidator: EbbinghausConsolidator,
    iteration: int,
    tracker: Optional[AccuracyTracker] = None,
    db_path: Optional[Path] = None,
    use_live_model: bool = True,
    model_tag: str = "stem-coder-expert:latest",
    domain_override: Optional[str] = None,
    language: str = "python",
) -> Dict[str, Any]:
    """
    Executes a single cycle of challenge generation across 4 expanded domains,
    lesson retrieval, model solving with CoT, Win32 Job Object sandboxed execution,
    APERL reflection, accuracy tracking, and periodic Ebbinghaus consolidation.
    """
    # 1. Domain selection & normalization
    selected_domain = domain_override or DOMAINS[(iteration - 1) % len(DOMAINS)]
    generator_domain = "concurrency" if selected_domain == "systems_concurrency" else selected_domain

    logger.info(f"--- Cycle #{iteration}: Generating {selected_domain} challenge in {language} ---")
    challenge = generator.generate_challenge(domain=generator_domain, language=language)
    logger.info(f"Challenge ID: {challenge.challenge_id} | Prompt: {challenge.prompt[:60]}...")

    # 2. Retrieve relevant prior engineering lessons
    effective_db = db_path or aperl.db_path
    if tracker is not None:
        retrieved_lessons = tracker.get_retrieved_lessons(domain=selected_domain, limit=3)
    else:
        retrieved_lessons = query_rag_lessons(domain=selected_domain, db_path=effective_db, limit=3)
    logger.info(f"Retrieved {len(retrieved_lessons)} prior lesson(s) for context augmentation.")

    # 3. Model solving with CoT and offline fallback
    sol = solve_challenge(
        challenge=challenge,
        model_tag=model_tag,
        use_live_model=use_live_model,
        retrieved_lessons=retrieved_lessons,
    )

    # 4. Sandboxed execution in Win32 Job Object sandbox
    t0 = time.time()
    exec_res: ExecutionResult = execute_sandboxed_code(
        source_code=sol,
        test_suite=challenge.test_suite,
        language=language,
        timeout=5.0,
        max_memory_mb=256,
    )
    elapsed = time.time() - t0
    logger.info(
        f"Sandbox Execution: success={exec_res.success}, ast_violation={exec_res.ast_violation}, "
        f"timeout={exec_res.timeout}, elapsed={elapsed:.2f}s, peak_mem={exec_res.peak_memory_bytes}B"
    )

    # 5. Categorize execution result & distill lesson via APERL
    if exec_res.success:
        err_type = "None"
        err_msg = "All unit tests and physical constraints passed"
    elif exec_res.ast_violation:
        err_type = "ASTViolation"
        err_msg = exec_res.error_message or "Forbidden module or syntax in sandbox"
    elif exec_res.timeout:
        err_type = "TimeoutError"
        err_msg = "Execution timed out after 5.0s"
    else:
        err_type = "AssertionError"
        err_msg = exec_res.stderr or exec_res.error_message or "Test assertion failed"

    trace = ExecutionTrace(
        task_id=challenge.challenge_id,
        language=language,
        error_type=err_type,
        error_message=err_msg,
        failed_code=challenge.starter_code,
        fixed_code=sol,
        test_output=exec_res.stdout,
        domain=selected_domain,
        invariants=challenge.invariants,
    )
    lesson_id = aperl.process_and_save(trace, challenge=challenge)
    logger.info(f"APERL distilled lesson {lesson_id} (error_type={err_type})")

    # 6. Reinforce retrieved lessons if execution was successful
    if exec_res.success and retrieved_lessons:
        reinforce_retrieved_lessons(retrieved_lessons, db_path=effective_db)

    # 7. Record cycle benchmark in AccuracyTracker
    if tracker is None:
        tracker = AccuracyTracker(db_path=effective_db)

    pass_at_1 = 1.0 if exec_res.success else 0.0
    test_pass_rate = 1.0 if exec_res.success else 0.0
    avg_patches = 0.0 if exec_res.success else 1.0
    inv_violations = 0.0 if exec_res.success else (
        1.0 if exec_res.ast_violation or exec_res.timeout or "invariant" in (exec_res.stderr or "").lower() or "assertion" in (exec_res.stderr or "").lower() else 0.0
    )
    total_lessons = tracker.get_current_lessons_count()

    details = {
        "challenge_id": challenge.challenge_id,
        "domain": selected_domain,
        "difficulty": challenge.difficulty,
        "duration_s": round(exec_res.duration_s, 4),
        "peak_memory_bytes": exec_res.peak_memory_bytes,
        "retrieved_lessons_count": len(retrieved_lessons),
        "ast_violation": exec_res.ast_violation,
        "timeout": exec_res.timeout,
    }

    benchmark_id = tracker.record_benchmark(
        cycle=iteration,
        pass_at_1=pass_at_1,
        test_pass_rate=test_pass_rate,
        avg_patches=avg_patches,
        invariant_violations=inv_violations,
        lessons_count=total_lessons,
        lessons_enabled=True,
        details=details,
    )
    logger.info(f"Recorded accuracy benchmark {benchmark_id}: Pass@1={pass_at_1}")

    # 8. Periodic Ebbinghaus consolidation every 5 cycles
    consolidation_report = None
    if iteration % 5 == 0:
        logger.info(f"--- Cycle #{iteration}: Triggering Ebbinghaus Memory Consolidation ---")
        consolidation_report = consolidate_database_lessons(db_path=effective_db)
        logger.info(f"Ebbinghaus consolidation completed: {consolidation_report}")

    # 9. Update state file for Web UI telemetry
    try:
        state_data = {
            "pid": os.getpid(),
            "status": "Running",
            "cycle_count": iteration,
            "iteration": iteration,
            "current_domain": selected_domain,
            "current_language": language,
            "last_cycle_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "last_challenge_id": challenge.challenge_id,
            "last_success": exec_res.success,
            "last_lesson_id": lesson_id,
            "last_benchmark_id": benchmark_id,
        }
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not update {STATE_FILE}: {e}")

    return {
        "iteration": iteration,
        "domain": selected_domain,
        "challenge_id": challenge.challenge_id,
        "success": exec_res.success,
        "lesson_id": lesson_id,
        "benchmark_id": benchmark_id,
        "consolidation_report": consolidation_report,
        "duration_s": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Autonomous Self-Play Daemon")
    parser.add_argument("--max-iterations", type=int, default=0, help="0 for infinite daemon loop")
    parser.add_argument("--interval-seconds", type=float, default=15.0, help="Sleep between cycles")
    parser.add_argument("--use-live-model", action="store_true", default=False, help="Enable live Ollama query")
    parser.add_argument("--model-tag", type=str, default="stem-coder-expert:latest")
    parser.add_argument("--db-path", type=str, default=None)
    args = parser.parse_args()

    custom_db = Path(args.db_path) if args.db_path else None

    logger.info("Initializing Autonomous Self-Play Daemon...")
    generator = SyntheticChallengeGenerator()
    aperl = APERLEngine(db_path=custom_db)
    consolidator = EbbinghausConsolidator()
    tracker = AccuracyTracker(db_path=custom_db)

    # Persist PID file
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    iteration = 0
    try:
        while True:
            # Check for stop signal before cycle
            if STOP_FILE.exists():
                logger.info("Graceful shutdown signal detected (STOP_FILE exists). Exiting loop.")
                try:
                    STOP_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
                break

            iteration += 1
            run_self_play_cycle(
                generator=generator,
                aperl=aperl,
                consolidator=consolidator,
                iteration=iteration,
                tracker=tracker,
                db_path=custom_db,
                use_live_model=args.use_live_model,
                model_tag=args.model_tag,
            )

            if args.max_iterations > 0 and iteration >= args.max_iterations:
                logger.info(f"Reached max iterations ({args.max_iterations}). Exiting cleanly.")
                break

            # Sleep in 1-second slices to respond promptly to stop signal
            sleep_remaining = args.interval_seconds
            while sleep_remaining > 0:
                if STOP_FILE.exists():
                    break
                time.sleep(min(1.0, sleep_remaining))
                sleep_remaining -= 1.0

    except KeyboardInterrupt:
        logger.info("Autonomous Self-Play Daemon stopped by keyboard interrupt.")
    finally:
        # Mark status as Stopped
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                data["status"] = "Stopped"
                STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass


if __name__ == "__main__":
    main()
