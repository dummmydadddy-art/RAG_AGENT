"""
scripts/learning/ebbinghaus.py

Ebbinghaus Memory Consolidation Engine & Database Hook.
Implements spaced repetition retention decay: R(t) = exp(-delta_t / S),
reinforces utility upon retrieval, and consolidates lessons stored in SQLite (vectors.sqlite).
Fully backward-compatible re-export of memory_consolidation.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import math
import re
import sqlite3
import time

# Re-export core classes for backward compatibility
from scripts.learning.memory_consolidation import (
    EbbinghausConsolidator as BaseEbbinghausConsolidator,
    LessonConsolidationRecord,
)

logger = logging.getLogger("EbbinghausConsolidator")


class EbbinghausConsolidator(BaseEbbinghausConsolidator):
    """
    Consolidator with long-term retention decay modeling, lifecycle transitions,
    and semantic contradiction detection.
    """
    pass


def _parse_timestamp_to_epoch(val: Any) -> float:
    """Safely parses float, int, or ISO timestamp strings into UNIX epoch seconds."""
    if val is None:
        return time.time()
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            pass
        try:
            clean = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            return dt.timestamp()
        except Exception:
            pass
    return time.time()


def consolidate_database_lessons(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Evaluates all lessons in backend/storage/vectors.sqlite, computes Ebbinghaus
    retention decay R(t) = exp(-delta_t / S), and applies promotion and retirement transitions.

    Thresholds:
    - Retire: R(t) < 0.20 AND usage_count == 0 (unreinforced stale knowledge)
    - Promote: R(t) >= 0.70 AND usage_count >= 5 AND status == 'candidate' (verified high utility)
    - Quarantine: legacy 'When None...' entries are retired immediately
    - Keep: all other active healthy lessons
    """
    target_path = db_path or (Path("backend") / "storage" / "vectors.sqlite")
    if not target_path.exists():
        logger.warning(f"Database {target_path} not found. Skipping consolidation.")
        return {
            "evaluated_count": 0,
            "retired_count": 0,
            "promoted_count": 0,
            "kept_count": 0,
            "retired_ids": [],
            "promoted_ids": [],
            "kept_ids": [],
        }

    consolidator = EbbinghausConsolidator()
    now_epoch = time.time()

    with sqlite3.connect(target_path, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if rag_documents exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
        if not cursor.fetchone():
            return {
                "evaluated_count": 0,
                "retired_count": 0,
                "promoted_count": 0,
                "kept_count": 0,
                "retired_ids": [],
                "promoted_ids": [],
                "kept_ids": [],
            }

        # Query all documents in the lessons collection
        cursor.execute("SELECT id, text, metadata, created_at FROM rag_documents WHERE collection = 'lessons'")
        rows = cursor.fetchall()

        records: List[LessonConsolidationRecord] = []
        meta_by_id: Dict[str, Dict[str, Any]] = {}
        quarantined_ids: List[str] = []

        for r in rows:
            doc_id = str(r["id"])
            text = str(r["text"])
            meta = json.loads(r["metadata"]) if r["metadata"] else {}

            # Handle legacy "When None..." entries by immediate quarantine retirement
            if "When None" in text:
                meta["status"] = "retired"
                meta["status_reason"] = "Quarantined: legacy malformed lesson"
                meta["retired_at"] = now_epoch
                cursor.execute(
                    "UPDATE rag_documents SET metadata = ? WHERE collection = 'lessons' AND id = ?",
                    (json.dumps(meta), doc_id),
                )
                quarantined_ids.append(doc_id)
                continue

            ref_epoch = _parse_timestamp_to_epoch(meta.get("last_used_at") or meta.get("created_at") or r["created_at"])
            elapsed_days = max(0.0, (now_epoch - ref_epoch) / 86400.0)
            strength = float(meta.get("strength", 10.0))
            usage = int(meta.get("usage_count", meta.get("use_count", 0)))
            status = str(meta.get("status", "candidate"))

            rec = LessonConsolidationRecord(
                lesson_id=doc_id,
                content=text,
                elapsed_days=elapsed_days,
                strength=strength,
                usage_count=usage,
                status=status,
            )
            records.append(rec)
            meta_by_id[doc_id] = meta

        # Evaluate transitions
        actions = consolidator.consolidate(records)

        # Apply Retirement
        for doc_id in actions["retire"]:
            m = meta_by_id[doc_id]
            m["status"] = "retired"
            m["status_reason"] = "Auto-retired by Ebbinghaus consolidation (retention < 0.20 with 0 usages)"
            m["retired_at"] = now_epoch
            cursor.execute(
                "UPDATE rag_documents SET metadata = ? WHERE collection = 'lessons' AND id = ?",
                (json.dumps(m), doc_id),
            )

        # Apply Promotion
        for doc_id in actions["promote"]:
            m = meta_by_id[doc_id]
            m["status"] = "verified"
            m["status_reason"] = "Auto-promoted by Ebbinghaus consolidation (retention >= 0.70 with >= 5 usages)"
            m["promoted_at"] = now_epoch
            m["strength"] = max(float(m.get("strength", 10.0)), 30.0)
            cursor.execute(
                "UPDATE rag_documents SET metadata = ? WHERE collection = 'lessons' AND id = ?",
                (json.dumps(m), doc_id),
            )

        conn.commit()

    all_retired = actions["retire"] + quarantined_ids
    return {
        "evaluated_count": len(records) + len(quarantined_ids),
        "retired_count": len(all_retired),
        "promoted_count": len(actions["promote"]),
        "kept_count": len(actions["keep"]),
        "retired_ids": all_retired,
        "promoted_ids": actions["promote"],
        "kept_ids": actions["keep"],
    }


def reinforce_lesson_usage(
    lesson_id: str,
    success: bool = True,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Reinforces lesson utility upon retrieval:
    - Increments usage_count.
    - If success=True: increments success_count and boosts strength S += 5.0.
    - If success=False: increments fail_count. Auto-retires if >= 2 failures and success < 50%.
    - Updates last_used_at timestamp.
    """
    target_path = db_path or (Path("backend") / "storage" / "vectors.sqlite")
    if not target_path.exists():
        return {"success": False, "error": f"Database {target_path} not found"}

    now_epoch = time.time()
    with sqlite3.connect(target_path, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata FROM rag_documents WHERE collection = 'lessons' AND id = ?",
            (lesson_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": f"Lesson {lesson_id} not found"}

        meta = json.loads(row["metadata"]) if row["metadata"] else {}

        # Increment counters
        usage = int(meta.get("usage_count", meta.get("use_count", 0))) + 1
        meta["usage_count"] = usage
        meta["use_count"] = usage
        meta["last_used_at"] = now_epoch

        success_count = int(meta.get("success_count", 0))
        fail_count = int(meta.get("fail_count", 0))

        if success:
            success_count += 1
            meta["success_count"] = success_count
            meta["strength"] = float(meta.get("strength", 10.0)) + 5.0
        else:
            fail_count += 1
            meta["fail_count"] = fail_count

        # Invariant: 2 failures with < 50% success triggers retirement
        total_uses = success_count + fail_count
        if fail_count >= 2 and (success_count / total_uses) < 0.5:
            meta["status"] = "retired"
            meta["status_reason"] = f"Auto-retired: {fail_count} failures out of {total_uses} uses (<50% success)"
            meta["retired_at"] = now_epoch

        cursor.execute(
            "UPDATE rag_documents SET metadata = ? WHERE collection = 'lessons' AND id = ?",
            (json.dumps(meta), lesson_id),
        )
        conn.commit()

    return {
        "success": True,
        "lesson_id": lesson_id,
        "usage_count": usage,
        "strength": meta.get("strength"),
        "status": meta.get("status"),
    }
