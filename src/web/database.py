"""
src/web/database.py

Thread-safe SQLite connection managers and queries for:
1. `chat_history.sqlite`: Dedicated store for conversation sessions and messages.
2. `vectors.sqlite`: Read-only queries over RAG documents and curriculum material chunks.
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.web.config import get_config

logger = logging.getLogger("web.database")


def _get_utc_now() -> str:
    """Returns current UTC timestamp in ISO format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ============================================================================
# 1. CHAT HISTORY STORE (chat_history.sqlite)
# ============================================================================

def get_chat_connection() -> sqlite3.Connection:
    """
    Opens a thread-safe connection to chat_history.sqlite with WAL mode
    and busy timeout = 10.0 seconds.
    """
    cfg = get_config()
    db_path = cfg.chat_history_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path),
        timeout=10.0,
        isolation_level=None,  # Autocommit mode for SQLite concurrency
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    # Enforce WAL mode and concurrency pragmas
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn


def init_chat_db() -> None:
    """Initializes tables and indexes in chat_history.sqlite if not already present."""
    with get_chat_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                telemetry TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
        """)
    logger.info("Chat history SQLite store initialized.")


def list_conversations() -> List[Dict[str, Any]]:
    """Lists all conversations ordered by updated_at descending with message counts."""
    with get_chat_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                c.id, 
                c.title, 
                c.created_at, 
                c.updated_at,
                COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
            ORDER BY c.updated_at DESC;
        """)
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
            }
            for row in rows
        ]


def create_conversation(
    conv_id: Optional[str] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Creates a new conversation record."""
    cid = conv_id or str(uuid.uuid4())
    ctitle = title.strip() if title and title.strip() else "New Conversation"
    now = _get_utc_now()

    with get_chat_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?);
            """,
            (cid, ctitle, now, now),
        )

    return {
        "id": cid,
        "title": ctitle,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "messages": [],
    }


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves conversation detail including all messages ordered chronologically."""
    with get_chat_connection() as conn:
        c_cursor = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?;",
            (conv_id,),
        )
        c_row = c_cursor.fetchone()
        if not c_row:
            return None

        m_cursor = conn.execute(
            """
            SELECT id, role, content, citations, telemetry, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC;
            """,
            (conv_id,),
        )
        m_rows = m_cursor.fetchall()

        messages = []
        for mr in m_rows:
            citations = json.loads(mr["citations"]) if mr["citations"] else []
            telemetry = json.loads(mr["telemetry"]) if mr["telemetry"] else {}
            messages.append({
                "id": mr["id"],
                "role": mr["role"],
                "content": mr["content"],
                "citations": citations,
                "telemetry": telemetry,
                "created_at": mr["created_at"],
            })

        return {
            "id": c_row["id"],
            "title": c_row["title"],
            "created_at": c_row["created_at"],
            "updated_at": c_row["updated_at"],
            "messages": messages,
        }


def update_conversation_title(conv_id: str, title: str) -> bool:
    """Updates the title of a conversation."""
    now = _get_utc_now()
    with get_chat_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?;
            """,
            (title.strip(), now, conv_id),
        )
        return cursor.rowcount > 0


def delete_conversation(conv_id: str) -> bool:
    """Deletes a conversation and its cascaded messages."""
    with get_chat_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE id = ?;",
            (conv_id,),
        )
        return cursor.rowcount > 0


def save_message(
    conv_id: str,
    role: str,
    content: str,
    citations: Optional[List[Dict[str, Any]]] = None,
    telemetry: Optional[Dict[str, Any]] = None,
    msg_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Persists a new message in the conversation and touches updated_at."""
    mid = msg_id or str(uuid.uuid4())
    now = _get_utc_now()
    citations_json = json.dumps(citations) if citations else None
    telemetry_json = json.dumps(telemetry) if telemetry else None

    with get_chat_connection() as conn:
        # Check if conversation exists; if not, create it
        c_check = conn.execute("SELECT id FROM conversations WHERE id = ?;", (conv_id,)).fetchone()
        if not c_check:
            # Auto-title from message content
            snippet = content.strip().split("\n")[0][:40]
            title = snippet if snippet else "New Conversation"
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?);",
                (conv_id, title, now, now),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?;",
                (now, conv_id),
            )

        conn.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, citations, telemetry, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (mid, conv_id, role, content, citations_json, telemetry_json, now),
        )

    return {
        "id": mid,
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "citations": citations or [],
        "telemetry": telemetry or {},
        "created_at": now,
    }


# ============================================================================
# 2. VECTOR DATABASE STORE (vectors.sqlite) - Read-Only Access
# ============================================================================

def get_vectors_connection() -> sqlite3.Connection:
    """
    Opens a strictly read-only connection to vectors.sqlite with busy timeout=10.0s.
    Protects against background task-3360 lock contention.
    """
    cfg = get_config()
    db_path = cfg.vectors_db_path

    if not db_path.exists():
        # Fallback to local in-memory if file missing
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # SQLite URI syntax for read-only mode
    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10.0, check_same_thread=False)
    except sqlite3.OperationalError:
        # If URI fails, fallback to standard connect
        conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)

    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
    except sqlite3.OperationalError:
        pass
    return conn


def get_vectors_stats() -> Dict[str, Any]:
    """Returns document and chunk counts from vectors.sqlite."""
    cfg = get_config()
    if not cfg.vectors_db_path.exists():
        return {"status": "missing", "rag_documents": 0, "material_chunks": 0}

    try:
        with get_vectors_connection() as conn:
            docs_count = conn.execute("SELECT COUNT(*) FROM rag_documents;").fetchone()[0]
            chunks_count = conn.execute("SELECT COUNT(*) FROM material_chunks;").fetchone()[0]
            return {
                "status": "online",
                "rag_documents": docs_count,
                "material_chunks": chunks_count,
            }
    except Exception as e:
        logger.warning(f"Error querying vectors.sqlite stats: {e}")
        return {"status": "error", "error": str(e), "rag_documents": 0, "material_chunks": 0}


def get_lessons(
    query: Optional[str] = None,
    collection: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Retrieves and filters lessons/documents from rag_documents in vectors.sqlite.
    """
    cfg = get_config()
    if not cfg.vectors_db_path.exists():
        return []

    try:
        with get_vectors_connection() as conn:
            conditions = []
            params: List[Any] = []

            if collection:
                conditions.append("collection = ?")
                params.append(collection)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT id, collection, text, metadata, created_at FROM rag_documents {where_clause} ORDER BY created_at DESC;"
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            tokens = [t.lower() for t in query.split() if t.strip()] if query else []

            for r in rows:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                doc_status = meta.get("status")

                if status and doc_status and doc_status.lower() != status.lower():
                    continue

                text = r["text"]
                doc_id = r["id"]

                # Keyword scoring if query provided
                score = 0.0
                if tokens:
                    haystack = f"{doc_id} {r['collection']} {text} {json.dumps(meta)}".lower()
                    matched_tokens = sum(1 for tok in tokens if tok in haystack)
                    if matched_tokens == 0:
                        continue
                    score = round(matched_tokens / len(tokens), 3)

                results.append({
                    "id": doc_id,
                    "collection": r["collection"],
                    "text": text,
                    "status": doc_status,
                    "metadata": meta,
                    "score": score,
                    "created_at": r["created_at"],
                })

            if tokens:
                results.sort(key=lambda x: x["score"], reverse=True)

            return results[:limit]
    except Exception as e:
        logger.warning(f"Error reading lessons from vectors.sqlite: {e}")
        return []


def retrieve_relevant_context(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves top relevant RAG documents / curriculum material chunks for prompt augmentation.
    Scores by token overlap and prioritizes verified lessons and curriculum chunks.
    """
    tokens = [t.lower() for t in query.split() if len(t.strip()) > 2]
    if not tokens:
        return []

    candidates: List[Dict[str, Any]] = []

    try:
        with get_vectors_connection() as conn:
            # 1. Search rag_documents
            cursor = conn.execute("SELECT id, collection, text, metadata FROM rag_documents;")
            for r in cursor.fetchall():
                doc_id = r["id"]
                coll = r["collection"]
                text = r["text"]
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                haystack = f"{doc_id} {coll} {text}".lower()

                matches = sum(1 for tok in tokens if tok in haystack)
                if matches > 0:
                    score = matches / len(tokens)
                    # Boost verified lessons
                    if meta.get("status") == "verified":
                        score += 0.2
                    candidates.append({
                        "id": doc_id,
                        "collection": coll,
                        "text": text[:600] + "..." if len(text) > 600 else text,
                        "score": round(score, 3),
                        "source": "rag_documents",
                        "metadata": meta,
                    })

            # 2. Search material_chunks
            c_cursor = conn.execute("SELECT id, title, content, metadata FROM material_chunks;")
            for cr in c_cursor.fetchall():
                chunk_id = cr["id"]
                title = cr["title"] or ""
                content = cr["content"] or ""
                meta = json.loads(cr["metadata"]) if cr["metadata"] else {}
                haystack = f"{chunk_id} {title} {content}".lower()

                matches = sum(1 for tok in tokens if tok in haystack)
                if matches > 0:
                    score = matches / len(tokens)
                    candidates.append({
                        "id": chunk_id,
                        "collection": "material_chunks",
                        "text": f"[{title}] {content[:500]}..." if len(content) > 500 else f"[{title}] {content}",
                        "score": round(score, 3),
                        "source": "material_chunks",
                        "metadata": meta,
                    })

    except Exception as e:
        logger.warning(f"Error retrieving RAG context from vectors.sqlite: {e}")

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]
