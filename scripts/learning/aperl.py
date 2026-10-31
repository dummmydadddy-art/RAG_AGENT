"""
scripts/learning/aperl.py

APERL: Automated Post-Execution Reflection Loop.
Automatically distills execution traces, test failures, and passing recovery patches
into canonical lessons formatted as:
When <situation>, do <action>, because <reason>.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json
import sqlite3
import time


@dataclass
class ExecutionTrace:
    task_id: str
    language: str
    error_type: str
    error_message: str
    failed_code: str
    fixed_code: str
    test_output: str


@dataclass
class DistilledLesson:
    situation: str
    action: str
    reason: str

    def to_canonical_format(self) -> str:
        """Formats the lesson in the mandatory project-wide canonical format."""
        sit = self.situation.strip().rstrip(",")
        act = self.action.strip().rstrip(",")
        rea = self.reason.strip().rstrip(".")
        return f"When {sit}, do {act}, because {rea}."


class APERLEngine:
    """
    Automated reflection engine analyzing execution traces and distilling candidate lessons.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path("backend") / "storage" / "vectors.sqlite")
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
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

    def distill_lesson(self, trace: ExecutionTrace) -> DistilledLesson:
        """
        Analyzes the failure pattern, the resolved fix, and test feedback to synthesize
        a structured, non-obvious engineering lesson.
        """
        err_msg_lower = (trace.error_type + " " + trace.error_message).lower()
        fixed_code = trace.fixed_code

        # Pattern 1: Pint temperature offsets
        if "offsetunitcalculuserror" in err_msg_lower or "degc" in err_msg_lower:
            return DistilledLesson(
                situation="performing arithmetic on offset temperature units like degC in Pint",
                action="construct quantities using ureg.Quantity and convert temperature differences to kelvin",
                reason="Pint scalar multiplication with offset units raises OffsetUnitCalculusError on arithmetic subtraction",
            )

        # Pattern 2: Non-commutative SymPy symbols
        if "commutative" in err_msg_lower or ("a*b" in trace.failed_code and "b*a" in trace.failed_code):
            return DistilledLesson(
                situation="verifying non-commutative operator algebras or quantum Lie brackets in SymPy",
                action="explicitly pre-bind symbols with commutative=False in local_dict before expression parsing",
                reason="SymPy default symbols are commutative and automatically collapse commutators like A*B - B*A to zero during AST generation",
            )

        # Pattern 3: Branch cuts and negative intervals
        if "sqrt" in trace.failed_code and "x**2" in trace.failed_code:
            return DistilledLesson(
                situation="verifying symbolic equivalence across branch cuts like sqrt(x^2)",
                action="use stratified numerical sampling across negative reals and declare explicit positive assumptions",
                reason="without explicit positive assumptions, sqrt(x^2) equals |x| which does not equal x for negative reals",
            )

        # Generic intelligent distillation fallback
        sit_summary = f"{trace.error_type} in {trace.language} ({trace.error_message[:70].strip()})"
        act_summary = f"apply verified refactoring: {fixed_code[:70].strip()}"
        rea_summary = f"it prevents {trace.error_type} and guarantees passing verification"

        return DistilledLesson(
            situation=sit_summary,
            action=act_summary,
            reason=rea_summary,
        )

    def process_and_save(self, trace: ExecutionTrace) -> str:
        """
        Distills a canonical lesson from trace and upserts it into the SQLite database.
        Returns unique lesson_id.
        """
        lesson = self.distill_lesson(trace)
        canonical_text = lesson.to_canonical_format()

        # Hash canonical text for deterministic deduplication
        lesson_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()[:8]
        lesson_id = f"lesson_{lesson_hash}"

        meta = {
            "source_task": trace.task_id,
            "language": trace.language,
            "error_type": trace.error_type,
            "status": "candidate",
            "strength": 10.0,
            "usage_count": 0,
            "created_at": time.time(),
        }

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rag_documents (id, collection, text, metadata)
                VALUES (?, 'lessons', ?, ?)
                """,
                (lesson_id, canonical_text, json.dumps(meta)),
            )
            conn.commit()

        return lesson_id
