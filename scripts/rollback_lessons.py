#!/usr/bin/env python3
"""
Rollback mechanism for self-learning coding agent lessons.
Inspects and demotes/retires lessons created, modified, or associated with a regression.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure rag-adapter is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag-adapter"))

from rag_adapter.models import LessonStatus


def _get_commit_timestamp(commit_hash: str) -> Optional[datetime]:
    try:
        out = subprocess.check_output(
            ["git", "show", "-s", "--format=%cI", commit_hash],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return datetime.fromisoformat(out.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


def rollback_lessons(
    db_path: Optional[str] = None,
    lesson_id: Optional[str] = None,
    failed_task: Optional[str] = None,
    since_timestamp: Optional[str] = None,
    since_commit: Optional[str] = None,
    reason: str = "Rollback due to benchmark failure or regression",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Demote or retire lessons matching specified criteria.
    Restricted to authorized rollback role or script execution.
    """
    if db_path is None:
        db_path = str(REPO_ROOT / "backend" / "storage" / "vectors.sqlite")

    if not Path(db_path).exists():
        return {
            "success": False,
            "error": f"Database not found: {db_path}",
            "rolled_back_count": 0,
            "rolled_back_ids": [],
        }

    # If since_commit is provided, convert to commit timestamp cutoff
    cutoff_dt = None
    if since_timestamp:
        cutoff_dt = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
    elif since_commit:
        cutoff_dt = _get_commit_timestamp(since_commit)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rolled_back_ids: List[str] = []

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, metadata FROM rag_documents WHERE collection = 'lessons'")
        rows = cursor.fetchall()

        for row in rows:
            doc_id = row["id"]
            meta = json.loads(row["metadata"]) if row["metadata"] else {}

            # Skip if already retired
            if meta.get("status") == LessonStatus.RETIRED:
                continue

            matched = False

            # 1. Match by explicit lesson ID
            if lesson_id and doc_id == lesson_id:
                matched = True

            # 2. Match by failed task ID (either created for it or used in it)
            if failed_task:
                ev = meta.get("evidence", {})
                task_in_ev = ev.get("task_id") == failed_task
                task_in_used = failed_task in meta.get("used_in_tasks", [])
                if task_in_ev or task_in_used:
                    matched = True

            # 3. Match by timestamp cutoff
            if cutoff_dt:
                created_str = meta.get("created_at")
                if created_str:
                    try:
                        c_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if c_dt >= cutoff_dt:
                            matched = True
                    except Exception:
                        pass

            if matched:
                rolled_back_ids.append(doc_id)
                if not dry_run:
                    meta["status"] = LessonStatus.RETIRED
                    meta["status_reason"] = reason
                    meta["retired_at"] = datetime.utcnow().isoformat()
                    meta["retired_by"] = "rollback_lessons.py"

                    cursor.execute(
                        "UPDATE rag_documents SET metadata = ? WHERE collection = 'lessons' AND id = ?",
                        (json.dumps(meta), doc_id),
                    )

        if not dry_run:
            conn.commit()

    finally:
        conn.close()

    return {
        "success": True,
        "rolled_back_count": len(rolled_back_ids),
        "rolled_back_ids": rolled_back_ids,
        "dry_run": dry_run,
        "reason": reason,
    }


def main():
    parser = argparse.ArgumentParser(description="Rollback lessons from RAG database.")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite database")
    parser.add_argument("--lesson-id", type=str, default=None, help="Specific lesson ID to rollback")
    parser.add_argument("--failed-task", type=str, default=None, help="Failed task ID triggering rollback")
    parser.add_argument("--since-timestamp", type=str, default=None, help="ISO timestamp cutoff")
    parser.add_argument("--since-commit", type=str, default=None, help="Git commit hash cutoff")
    parser.add_argument("--reason", type=str, default="Rollback due to benchmark failure or regression")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without mutating database")

    args = parser.parse_args()

    res = rollback_lessons(
        db_path=args.db_path,
        lesson_id=args.lesson_id,
        failed_task=args.failed_task,
        since_timestamp=args.since_timestamp,
        since_commit=args.since_commit,
        reason=args.reason,
        dry_run=args.dry_run,
    )

    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("success") else 1)


if __name__ == "__main__":
    main()
