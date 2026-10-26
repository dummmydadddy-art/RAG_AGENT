import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "evals" / "tasks"
REPORTS_DIR = ROOT / "evals" / "reports"
HIDDEN_CHECKS_DIR = Path("C:/Users/Mukul/.gemini/antigravity/hidden_evals")
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Self-Learning Coding Agent Evaluation Harness")
    parser.add_argument("--mode", choices=["single", "team"], default="single", help="Execution mode (single or team)")
    parser.add_argument("--lessons", choices=["on", "off"], default="off", help="Whether lesson retrieval is active")
    parser.add_argument("--task", type=str, default=None, help="Run specific task ID (default runs all)")
    parser.add_argument("--auto", action="store_true", help="Non-interactive / automated grade mode")
    parser.add_argument("--retrieval-mode", type=str, default="hybrid_sqlite_pinned", help="Pinned retrieval configuration")
    return parser.parse_args()


def load_tasks(filter_task_id=None):
    tasks = []
    for t_dir in sorted(TASKS_DIR.iterdir()):
        if not t_dir.is_dir():
            continue
        meta_file = t_dir / "task.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if filter_task_id and meta["id"] != filter_task_id:
            continue
        tasks.append((t_dir, meta))
    return tasks


def grade_task(task_dir: Path, meta: dict, retrieval_mode: str, lessons_mode: str, auto_mode: bool = False):
    task_id = meta["id"]
    title = meta["title"]
    held_out = meta.get("held_out", False)

    print(f"\n========================================================")
    print(f" EVAL RUN: {task_id} — {title}")
    print(f" Category: {meta.get('category')} | Held-Out: {held_out}")
    print(f" Mode: single | Lessons: {lessons_mode} | Retrieval: {retrieval_mode}")
    print(f"========================================================")

    target_file = ROOT / meta["target_file"]
    start_time = time.perf_counter()

    # Step 1: Prompt presentation
    prompt = (
        f"/gsd {task_id}: {title}\n\n"
        f"Specification:\n{meta['description']}\n\n"
        f"Target Implementation File: {meta['target_file']}\n"
    )

    if not auto_mode:
        print("\n--- AGENT INVOCATION PROMPT ---")
        print(prompt)
        print("--------------------------------\n")
        print("Action required: Execute the above prompt in Antigravity.")
        print(f"Target file: {target_file}")
        input("Press ENTER after the agent has completed the task and left PLAN.md, traces, and code...")

    elapsed_time = time.perf_counter() - start_time

    # Step 2: Verify code file was created
    if not target_file.exists():
        print(f"[FAIL] Target implementation file {target_file} was not found.")
        return {
            "task_id": task_id,
            "title": title,
            "category": meta.get("category"),
            "held_out": held_out,
            "status": "FAIL",
            "iterations": 0,
            "wall_time_seconds": round(elapsed_time, 2),
            "retrieval_mode": retrieval_mode,
            "lessons_used": [],
            "error": f"Target file {meta['target_file']} not created",
        }

    # Step 3: Mount hidden check
    hidden_check_src = HIDDEN_CHECKS_DIR / task_id / "test_hidden.py"
    if not hidden_check_src.exists():
        print(f"[ERROR] Hidden check not found at {hidden_check_src}")
        return {
            "task_id": task_id,
            "status": "ERROR",
            "error": "Hidden check file missing from secure store",
        }

    temp_test_dst = ROOT / f"test_grading_{task_id}.py"
    shutil.copyfile(hidden_check_src, temp_test_dst)

    # Step 4: Run hidden checks with pytest
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pytest", "-q", str(temp_test_dst)],
            capture_output=True,
            text=True,
            timeout=30.0,
            cwd=str(ROOT),
            env=env,
        )
        passed = (result.returncode == 0)
        output = result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        passed = False
        output = "Hidden test execution timed out after 30s"
    except Exception as e:
        passed = False
        output = f"Runner exception: {str(e)}"
    finally:
        if temp_test_dst.exists():
            temp_test_dst.unlink()

    # Step 5: Check artifact presence (PLAN.md, trace)
    plan_exists = (ROOT / "PLAN.md").exists() or (ROOT / "docs" / "PLAN.md").exists()
    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] Hidden tests result: {output[:120]}")

    return {
        "task_id": task_id,
        "title": title,
        "category": meta.get("category"),
        "held_out": held_out,
        "status": status_str,
        "iterations": 1,
        "wall_time_seconds": round(elapsed_time, 2),
        "retrieval_mode": retrieval_mode,
        "lessons_used": [],
        "plan_present": plan_exists,
        "details": output,
    }


def main():
    args = parse_args()
    tasks = load_tasks(args.task)

    print(f"Starting Evaluation Harness: {len(tasks)} task(s) queued.")
    results = []

    for task_dir, meta in tasks:
        res = grade_task(
            task_dir=task_dir,
            meta=meta,
            retrieval_mode=args.retrieval_mode,
            lessons_mode=args.lessons,
            auto_mode=args.auto,
        )
        results.append(res)

    # Generate Markdown Report
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100.0) if total_count else 0.0

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"eval_report_{timestamp}.md"

    lines = [
        f"# Evaluation Harness Report — {timestamp}",
        f"\n- **Mode**: `{args.mode}`",
        f"- **Lessons Mode**: `{args.lessons}`",
        f"- **Retrieval Mode (Pinned)**: `{args.retrieval_mode}`",
        f"- **Pass Rate**: **{passed_count}/{total_count} ({pass_rate:.1f}%)**\n",
        "## Summary Results",
        "| Task ID | Title | Category | Held-Out | Status | Wall Time (s) | Plan |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in results:
        ho_str = "Yes" if r.get("held_out") else "No"
        plan_str = "Yes" if r.get("plan_present") else "No"
        lines.append(f"| `{r['task_id']}` | {r['title']} | `{r['category']}` | {ho_str} | **{r['status']}** | {r.get('wall_time_seconds', 0)}s | {plan_str} |")

    lines.append("\n## Detailed Breakdown")
    for r in results:
        lines.append(f"\n### {r['task_id']}: {r['title']}")
        lines.append(f"- **Status**: {r['status']}")
        lines.append(f"- **Details**: `{r.get('details', 'N/A')}`")
        if r.get("error"):
            lines.append(f"- **Error**: {r['error']}")

    report_content = "\n".join(lines)
    report_file.write_text(report_content, encoding="utf-8")
    print(f"\n========================================================")
    print(f" Evaluation Complete: {passed_count}/{total_count} passed ({pass_rate:.1f}%)")
    print(f" Report written to: {report_file}")
    print(f"========================================================\n")


if __name__ == "__main__":
    main()
