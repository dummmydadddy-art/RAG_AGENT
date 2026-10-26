import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Doc, Hit, LessonStatus


class LocalSqliteRagBackend(RagAdapter):
    """
    SQLite-backed RAG adapter supporting knowledge, lessons, and traces collections,
    compatible with the local SQLite vector database architecture.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            # Default to backend/storage/vectors.sqlite
            db_path = str(Path(__file__).resolve().parents[2] / "backend" / "storage" / "vectors.sqlite")

        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, id)
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rag_docs_coll ON rag_documents(collection);
            """)
            conn.commit()

    def search(
        self,
        query: str,
        collections: List[str],
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Hit]:
        hits: List[Hit] = []
        tokens = [t.lower() for t in query.split() if t.strip()]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in collections)
            sql = f"SELECT id, collection, text, metadata FROM rag_documents WHERE collection IN ({placeholders})"
            cursor.execute(sql, collections)
            rows = cursor.fetchall()

            for row in rows:
                doc_id = row["id"]
                coll = row["collection"]
                text = row["text"]
                meta = json.loads(row["metadata"]) if row["metadata"] else {}

                # Check filters
                if filters:
                    match = True
                    for fk, fv in filters.items():
                        if meta.get(fk) != fv:
                            match = False
                            break
                    if not match:
                        continue

                # Exclude retired lessons by default
                if coll == "lessons" and meta.get("status") == LessonStatus.RETIRED:
                    continue

                text_lower = text.lower()
                score = sum(1.0 for t in tokens if t in text_lower)
                if query.lower() in text_lower:
                    score += 2.0

                if score > 0 or not tokens:
                    hits.append(
                        Hit(
                            doc_id=doc_id,
                            collection=coll,
                            text=text,
                            metadata=meta,
                            score=float(score),
                        )
                    )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        meta_str = json.dumps(metadata or {})
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rag_documents (id, collection, text, metadata)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(collection, id) DO UPDATE SET
                    text = excluded.text,
                    metadata = excluded.metadata
            """, (doc_id, collection, text, meta_str))
            conn.commit()

    def get(self, collection: str, doc_id: str) -> Optional[Doc]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, collection, text, metadata
                FROM rag_documents
                WHERE collection = ? AND id = ?
            """, (collection, doc_id))
            row = cursor.fetchone()
            if not row:
                return None
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            return Doc(
                doc_id=row["id"],
                collection=row["collection"],
                text=row["text"],
                metadata=meta,
            )

    def set_status(
        self,
        collection: str,
        doc_id: str,
        status: LessonStatus,
        reason: str = "",
    ) -> None:
        doc = self.get(collection, doc_id)
        if not doc:
            raise KeyError(f"Document {doc_id} not found in collection {collection}")

        doc.metadata["status"] = status
        if reason:
            doc.metadata["status_reason"] = reason

        self.upsert(collection, doc_id, doc.text, doc.metadata)

    def delete(self, collection: str, doc_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rag_documents WHERE collection = ? AND id = ?", (collection, doc_id))
            conn.commit()

    def upsert_lesson(self, lesson: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper method to store a lesson dictionary with standardized schema.
        """
        lesson_id = lesson.get("id")
        title = lesson.get("title", "")
        rule = lesson.get("rule", "")
        status = lesson.get("status", LessonStatus.CANDIDATE)

        meta = {
            "title": title,
            "rule": rule,
            "domain": lesson.get("domain", []),
            "evidence": lesson.get("evidence", {}),
            "status": status,
            "created_at": lesson.get("created_at") or "",
            "last_used_at": lesson.get("last_used_at"),
            "use_count": int(lesson.get("use_count", 0)),
            "success_count": int(lesson.get("success_count", 0)),
            "fail_count": int(lesson.get("fail_count", 0)),
            "supersedes": lesson.get("supersedes", []),
        }

        self.upsert(
            collection="lessons",
            doc_id=lesson_id,
            text=f"{title}\n{rule}",
            metadata=meta,
        )
        return {"success": True, "lesson_id": lesson_id, "status": status}

    def record_lesson_use(self, lesson_id: str, success: bool, task_id: str = "") -> Dict[str, Any]:
        """
        Record outcome of lesson application and enforce auto-retirement invariants.
        """
        from datetime import datetime
        doc = self.get("lessons", lesson_id)
        if not doc:
            return {"success": False, "error": f"Lesson {lesson_id} not found"}

        meta = doc.metadata or {}
        meta["use_count"] = int(meta.get("use_count", 0)) + 1
        if success:
            meta["success_count"] = int(meta.get("success_count", 0)) + 1
        else:
            meta["fail_count"] = int(meta.get("fail_count", 0)) + 1

        meta["last_used_at"] = datetime.utcnow().isoformat()
        if task_id:
            meta.setdefault("used_in_tasks", []).append(task_id)

        # Automatic retirement check: 2 failures with < 50% success
        retired = False
        fail_count = meta["fail_count"]
        total = meta["success_count"] + fail_count
        if fail_count >= 2 and (meta["success_count"] / total) < 0.5:
            meta["status"] = LessonStatus.RETIRED
            meta["status_reason"] = f"Auto-retired: {fail_count} failures out of {total} uses (<50% success)"
            retired = True

        self.upsert("lessons", lesson_id, doc.text, meta)
        return {
            "success": True,
            "lesson_id": lesson_id,
            "use_count": meta["use_count"],
            "success_count": meta["success_count"],
            "fail_count": meta["fail_count"],
            "retired": retired,
            "status": meta["status"],
        }

    def search_lessons(self, query: str, k: int = 5) -> List[Hit]:
        """
        Search lessons collection with prioritization:
        - Excludes retired lessons.
        - Prioritizes verified lessons over candidate lessons.
        - Capped at k.
        """
        all_hits = self.search(query=query, collections=["lessons"], k=100)
        # Filter out retired and sort verified first, then by match score
        filtered = [h for h in all_hits if h.metadata.get("status") != LessonStatus.RETIRED]
        filtered.sort(
            key=lambda h: (
                1 if h.metadata.get("status") == LessonStatus.VERIFIED else 0,
                h.score,
            ),
            reverse=True,
        )
        return filtered[:k]

