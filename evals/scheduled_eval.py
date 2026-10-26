#!/usr/bin/env python3
"""
Unattended Weekly Scheduled Benchmark Runner (Phase 4).
Runs autonomous benchmark evaluation, checks held-out regression gates,
automatically triggers lesson rollback upon gate failure, and generates
unattended weekly benchmark reports in evals/reports/.
"""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rag-adapter"))

from evals.crypto_utils import decrypt_evals
from evals.run import HARD_SUBSET_TASKS, TASKS_DIR, execute_agent_headless, run_single_iteration
from scripts.rollback_lessons import rollback_lessons
from scripts.snapshot_store import get_store_hash, reset_store, snapshot_store

DEFAULT_REPORTS_DIR = ROOT / "evals" / "reports"
ENCRYPTED_ARCHIVE = ROOT / "evals" / "hidden_evals.enc"


def evaluate_scheduled_run(
    task_results: List[Dict[str, Any]],
    store_hash: str,
    rollback_fn: Optional[Callable[[], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates pass rates and checks regression gates:
    - Held-out tasks must not drop (100% required).
    - Overall pass rate must be >= 90%.
    If either fails, triggers automated lesson rollback.
    """
    held_out_tasks = [t for t in task_results if t.get("held_out", False)]
    ho_passed = sum(1 for t in held_out_tasks if t.get("status") == "PASS")
    ho_total = len(held_out_tasks)
    ho_pass_rate = (ho_passed / ho_total * 100.0) if ho_total > 0 else 100.0

    overall_passed = sum(1 for t in task_results if t.get("status") == "PASS")
    overall_total = len(task_results)
    overall_pass_rate = (overall_passed / overall_total * 100.0) if overall_total > 0 else 0.0

    regression_detected = (ho_passed < ho_total) or (overall_pass_rate < 90.0)
    rollback_triggered = False
    rollback_details: Dict[str, Any] = {}

    if regression_detected and rollback_fn is not None:
        rollback_details = rollback_fn()
        rollback_triggered = True

    return {
        "timestamp": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
        "store_hash": store_hash,
        "held_out_passed": ho_passed,
        "held_out_total": ho_total,
        "held_out_pass_rate": round(ho_pass_rate, 1),
        "overall_passed": overall_passed,
        "overall_total": overall_total,
        "overall_pass_rate": round(overall_pass_rate, 1),
        "regression_detected": regression_detected,
        "rollback_triggered": rollback_triggered,
        "rollback_details": rollback_details,
        "tasks": task_results,
    }


def generate_weekly_report(run_results: Dict[str, Any], output_dir: Path) -> Path:
    """Writes a formal unattended weekly report in markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = run_results["timestamp"]
    report_file = output_dir / f"weekly_report_{ts}.md"

    gate_status = "FAILED (Rollback Triggered)" if run_results["regression_detected"] else "PASSED"
    ho_str = f"{run_results['held_out_passed']}/{run_results['held_out_total']} ({run_results['held_out_pass_rate']}%)"
    ov_str = f"{run_results['overall_passed']}/{run_results['overall_total']} ({run_results['overall_pass_rate']}%)"

    lines = [
        f"# Weekly Scheduled Benchmark Report — {ts}",
        f"\n- **Execution Mode**: `{run_results.get('mode', 'single')}`",
        f"- **Unattended Run**: True",
        f"- **Lessons Mode**: `{run_results.get('lessons_mode', 'on')}`",
        f"- **Store Baseline SHA-256**: `{run_results['store_hash']}`",
        f"- **Held-Out Regression Gate**: **{gate_status}**",
        f"\n## Summary Metrics",
        f"| Metric | Result | Target Gate | Status |",
        f"|---|---|---|---|",
        f"| **Held-Out Pass Rate** | **{ho_str}** | 100% (No regression) | {'PASS' if not run_results['regression_detected'] else 'FAIL'} |",
        f"| **Overall Benchmark Pass Rate** | **{ov_str}** | $\\ge 90.0\\%$ | {'PASS' if run_results['overall_pass_rate'] >= 90.0 else 'FAIL'} |",
        f"| **Rollback Triggered** | {run_results['rollback_triggered']} | False unless regression | OK |",
    ]

    if run_results["rollback_triggered"]:
        lines.append(f"\n### Automated Rollback Action")
        lines.append(f"Regression detected in held-out benchmark. Automated rollback executed:")
        lines.append(f"```json\n{json.dumps(run_results['rollback_details'], indent=2)}\n```")

    lines.append(f"\n## Task Execution Details")
    lines.append(f"| Task ID | Title | Category | Held-Out | Status |")
    lines.append(f"|---|---|---|---|---|")

    for t in run_results.get("tasks", []):
        ho_label = "Yes" if t.get("held_out", False) else "No"
        title = t.get("title", t.get("task_id", ""))
        cat = t.get("category", "")
        st = t.get("status", "UNKNOWN")
        lines.append(f"| `{t['task_id']}` | {title} | `{cat}` | {ho_label} | **{st}** |")

    report_content = "\n".join(lines)
    report_file.write_text(report_content, encoding="utf-8")
    return report_file


def run_unattended_eval(
    passphrase: str,
    mode: str = "single",
    task_id_filter: Optional[str] = None,
    hard_subset_only: bool = False,
    output_dir: Path = DEFAULT_REPORTS_DIR,
) -> int:
    """Executes the full unattended benchmark cycle."""
    print(f"Starting unattended scheduled benchmark run ({mode} mode)...")

    # Snapshot store
    _, store_hash = snapshot_store(label="scheduled_pre")
    print(f"Store snapshot saved. Hash: {store_hash}")

    # Decrypt hidden checks into memory
    hidden_checks = decrypt_evals(ENCRYPTED_ARCHIVE, passphrase)

    # Load tasks
    tasks = []
    for t_dir in sorted(TASKS_DIR.iterdir()):
        if not t_dir.is_dir():
            continue
        meta_file = t_dir / "task.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if task_id_filter and meta["id"] != task_id_filter:
            continue
        if hard_subset_only and meta["id"] not in HARD_SUBSET_TASKS:
            continue
        tasks.append(meta)

    print(f"Loaded {len(tasks)} tasks for unattended grading.")

    task_results = []
    for meta in tasks:
        t_id = meta["id"]
        hidden_code = hidden_checks.get(t_id)
        if not hidden_code:
            continue

        res = run_single_iteration(
            task_id=t_id,
            meta=meta,
            hidden_code=hidden_code,
            iteration=1,
            auto_mode=True,
            headless_mode=False,
            lessons_mode="on",
            mode=mode,
        )
        task_results.append({
            "task_id": t_id,
            "title": meta.get("title", ""),
            "category": meta.get("category", ""),
            "held_out": meta.get("held_out", False),
            "status": res["status"],
            "wall_time": res["wall_time"],
        })

    def do_rollback():
        print("[WARNING] Regression gate failed! Triggering automated lesson rollback...")
        return rollback_lessons(reason="Automated weekly scheduled evaluation regression rollback", dry_run=False)

    eval_summary = evaluate_scheduled_run(
        task_results=task_results,
        store_hash=store_hash,
        rollback_fn=do_rollback,
    )
    eval_summary["mode"] = mode
    eval_summary["lessons_mode"] = "on"

    report_path = generate_weekly_report(eval_summary, output_dir=output_dir)
    print(f"Unattended weekly report generated at: {report_path}")

    return 1 if eval_summary["regression_detected"] else 0


def main():
    parser = argparse.ArgumentParser(description="Unattended weekly scheduled benchmark runner")
    parser.add_argument("--unattended", action="store_true", default=True, help="Run unattended")
    parser.add_argument("--mode", choices=["single", "team"], default="single", help="Execution mode")
    parser.add_argument("--task", type=str, default=None, help="Specific task ID filter")
    parser.add_argument("--hard-subset", action="store_true", help="Run hard subset only")
    parser.add_argument("--passphrase", type=str, default=None, help="Decryption passphrase")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Report output directory")
    args = parser.parse_args()

    passphrase = args.passphrase or os.environ.get("EVAL_PASSPHRASE") or "antigravity-eval-secret-2026"
    exit_code = run_unattended_eval(
        passphrase=passphrase,
        mode=args.mode,
        task_id_filter=args.task,
        hard_subset_only=args.hard_subset,
        output_dir=args.output_dir,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
