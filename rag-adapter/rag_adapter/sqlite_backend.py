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
