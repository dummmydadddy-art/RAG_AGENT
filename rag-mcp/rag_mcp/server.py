import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

# Ensure rag-adapter is in python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rag-adapter"))

from rag_adapter.models import LessonStatus
from rag_adapter.sqlite_backend import LocalSqliteRagBackend

# Initialize FastMCP application
mcp = FastMCP("rag-mcp")
_backend = LocalSqliteRagBackend()

# Roles permitted to modify lessons
ALLOWED_WRITE_ROLES = {"librarian", "rollback", "admin"}


def _check_permission(caller_role: str) -> None:
    role = (caller_role or os.getenv("CURRENT_AGENT_ROLE", "")).strip().lower()
    if role not in ALLOWED_WRITE_ROLES:
        raise PermissionError(
            f"Permission denied: role '{role}' is not authorized to write or modify lessons. "
            f"Allowed roles: {sorted(list(ALLOWED_WRITE_ROLES))}"
        )


@mcp.tool()
def rag_search(
    query: str,
    collections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 5,
) -> Dict[str, Any]:
    """
    Search across knowledge and lessons collections.
    Returns ranked hits matching the query. Excludes retired lessons by default.
    """
    if collections is None:
        collections = ["knowledge", "lessons"]

    hits = _backend.search(query=query, collections=collections, filters=filters, k=k)
    return {
        "count": len(hits),
        "results": [
            {
                "doc_id": h.doc_id,
                "collection": h.collection,
                "text": h.text,
                "metadata": h.metadata,
                "score": round(h.score, 4),
            }
            for h in hits
        ],
    }


@mcp.tool()
def rag_upsert_lesson(lesson: Dict[str, Any], caller_role: str = "") -> Dict[str, Any]:
    """
    Upsert a distilled lesson. Restricted to librarian and rollback roles.
    Input lesson must contain: id, title, rule.
    """
    _check_permission(caller_role)

    lesson_id = lesson.get("id")
    title = lesson.get("title")
    rule = lesson.get("rule")

    if not lesson_id or not title or not rule:
        return {"success": False, "error": "Missing mandatory lesson fields: id, title, rule"}

    status = lesson.get("status", LessonStatus.CANDIDATE)
    metadata = {
        "title": title,
        "rule": rule,
        "domain": lesson.get("domain", []),
        "evidence": lesson.get("evidence", {}),
        "status": status,
        "created_at": lesson.get("created_at") or datetime.utcnow().isoformat(),
        "last_used_at": None,
        "use_count": int(lesson.get("use_count", 0)),
        "success_count": int(lesson.get("success_count", 0)),
        "fail_count": int(lesson.get("fail_count", 0)),
        "supersedes": lesson.get("supersedes", []),
    }

    _backend.upsert(
        collection="lessons",
        doc_id=lesson_id,
        text=f"{title}\n{rule}",
        metadata=metadata,
    )
    return {"success": True, "lesson_id": lesson_id, "status": status}


@mcp.tool()
def rag_record_use(lesson_id: str, success: bool, task_id: str = "") -> Dict[str, Any]:
    """
    Record an execution outcome for a retrieved lesson.
    Automatically retires lessons that fail repeatedly.
    """
    doc = _backend.get("lessons", lesson_id)
    if not doc:
        return {"success": False, "error": f"Lesson {lesson_id} not found"}

    meta = doc.metadata
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

    _backend.upsert("lessons", lesson_id, doc.text, meta)
    return {
        "success": True,
        "lesson_id": lesson_id,
        "use_count": meta["use_count"],
        "success_count": meta["success_count"],
        "fail_count": meta["fail_count"],
        "retired": retired,
        "status": meta["status"],
    }


@mcp.tool()
def rag_promote(lesson_id: str, reason: str, caller_role: str = "") -> Dict[str, Any]:
    """
    Promote a lesson to 'verified'. Restricted to librarian and rollback roles.
    """
    _check_permission(caller_role)
    try:
        _backend.set_status("lessons", lesson_id, LessonStatus.VERIFIED, reason)
        return {"success": True, "lesson_id": lesson_id, "status": LessonStatus.VERIFIED}
    except KeyError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def rag_demote(lesson_id: str, reason: str, caller_role: str = "") -> Dict[str, Any]:
    """
    Demote or retire a lesson. Restricted to librarian and rollback roles.
    """
    _check_permission(caller_role)
    try:
        _backend.set_status("lessons", lesson_id, LessonStatus.RETIRED, reason)
        return {"success": True, "lesson_id": lesson_id, "status": LessonStatus.RETIRED}
    except KeyError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def rag_stats() -> Dict[str, Any]:
    """
    Return statistics across collections and lesson statuses.
    """
    stats: Dict[str, Any] = {
        "knowledge_count": 0,
        "lessons_total": 0,
        "lessons_candidate": 0,
        "lessons_verified": 0,
        "lessons_retired": 0,
        "traces_count": 0,
    }

    with _backend._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT collection, metadata FROM rag_documents")
        for row in cursor.fetchall():
            coll = row["collection"]
            if coll == "knowledge":
                stats["knowledge_count"] += 1
            elif coll == "traces":
                stats["traces_count"] += 1
            elif coll == "lessons":
                stats["lessons_total"] += 1
                meta = row["metadata"]
                if meta:
                    import json
                    m = json.loads(meta)
                    st = m.get("status")
                    if st == LessonStatus.CANDIDATE:
                        stats["lessons_candidate"] += 1
                    elif st == LessonStatus.VERIFIED:
                        stats["lessons_verified"] += 1
                    elif st == LessonStatus.RETIRED:
                        stats["lessons_retired"] += 1

    return stats


if __name__ == "__main__":
    mcp.run()
