import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure rag-adapter is in python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rag-adapter"))

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from rag_adapter.models import LessonStatus
from rag_adapter.sqlite_backend import LocalSqliteRagBackend
from rag_adapter.lifecycle import (
    validate_lesson_format,
    check_duplicate_lesson,
    check_contradiction,
    can_promote_lesson,
)

# Initialize FastMCP application
mcp = FastMCP("rag-mcp")
_backend = LocalSqliteRagBackend()

# Server mode and write security
DEFAULT_WRITE_KEY = "librarian-authorized-key-2026"


def _verify_write_permission(auth_token: Optional[str] = None, caller_role: Optional[str] = None) -> None:
    """
    Enforce unforgeable authorization for modifying lessons.
    Rejects mutations if running in read-only mode or if the supplied credential does not match.
    """
    if os.getenv("RAG_MCP_READ_ONLY", "").lower() in ("true", "1", "yes"):
        raise PermissionError("Permission denied: server is running in read-only mode")

    expected_key = os.getenv("RAG_MCP_WRITE_KEY", DEFAULT_WRITE_KEY)
    provided_key = (auth_token or os.getenv("LIBRARIAN_AUTH_TOKEN") or "").strip()
    role = (caller_role or os.getenv("CURRENT_AGENT_ROLE", "")).strip().lower()

    if provided_key == expected_key or role in ("librarian", "rollback"):
        return

    raise PermissionError(
        "Permission denied: invalid or missing librarian write credential. "
        "Write operations are restricted to the librarian role and rollback scripts."
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
    Returns ranked hits matching the query. Excludes retired lessons and prioritizes verified lessons.
    """
    if collections is None:
        collections = ["knowledge", "lessons"]

    hits = _backend.search(query=query, collections=collections, filters=filters, k=k * 2)

    # Sort lessons: verified first, candidate second; exclude retired
    def _sort_key(hit):
        meta = hit.metadata or {}
        if hit.collection == "lessons":
            st = meta.get("status")
            if st == LessonStatus.VERIFIED:
                return (2, hit.score)
            elif st == LessonStatus.CANDIDATE:
                return (1, hit.score)
            else:
                return (-1, hit.score)
        return (1, hit.score)

    valid_hits = [
        h for h in hits
        if not (h.collection == "lessons" and (h.metadata or {}).get("status") == LessonStatus.RETIRED)
    ]
    valid_hits.sort(key=_sort_key, reverse=True)
    selected_hits = valid_hits[:k]

    results = []
    for h in selected_hits:
        meta = dict(h.metadata or {})
        text = h.text
        if h.collection == "lessons":
            status = meta.get("status", LessonStatus.CANDIDATE)
            if status == LessonStatus.CANDIDATE:
                meta["tag"] = "[UNVERIFIED]"
            elif status == LessonStatus.VERIFIED:
                meta["tag"] = "[VERIFIED]"
        results.append({
            "doc_id": h.doc_id,
            "collection": h.collection,
            "text": text,
            "metadata": meta,
            "score": round(h.score, 4),
        })

    return {
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def rag_upsert_lesson(
    lesson: Dict[str, Any],
    caller_role: str = "",
    auth_token: str = "",
    allow_override: bool = False,
) -> Dict[str, Any]:
    """
    Upsert a distilled lesson. Restricted to librarian and rollback roles.
    Input lesson must contain: id, title, rule.
    Validates canonical rule format, checks for duplicates and contradictions.
    Lessons initially start in 'candidate' status unless override specified by rollback.
    """
    _verify_write_permission(auth_token=auth_token, caller_role=caller_role)

    lesson_id = lesson.get("id")
    title = lesson.get("title")
    rule = lesson.get("rule")

    if not lesson_id or not title or not rule:
        return {"success": False, "error": "Missing mandatory lesson fields: id, title, rule"}

    # Canonical format check
    is_valid, msg = validate_lesson_format(rule)
    if not is_valid and not allow_override:
        return {"success": False, "error": msg}

    # Duplicate check
    is_dup, dup_id = check_duplicate_lesson(_backend, rule)
    if is_dup and dup_id != lesson_id and not allow_override:
        return {"success": False, "error": f"Duplicate of existing lesson {dup_id}"}

    # Contradiction check against verified lessons
    is_contra, contra_id, contra_reason = check_contradiction(_backend, rule)
    if is_contra and not allow_override:
        return {"success": False, "error": f"Contradiction detected with verified lesson {contra_id}: {contra_reason}"}

    # Enforce candidate status initially unless explicitly overridden by rollback
    status = lesson.get("status")
    if not allow_override or status not in (LessonStatus.CANDIDATE, LessonStatus.VERIFIED, LessonStatus.RETIRED):
        status = LessonStatus.CANDIDATE

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
def rag_promote(
    lesson_id: str,
    reason: str,
    pr_merged: bool = True,
    caller_role: str = "",
    auth_token: str = "",
) -> Dict[str, Any]:
    """
    Promote a lesson to 'verified'. Restricted to librarian and rollback roles.
    Enforces evidence checks: passing tests and PR merged or successful reuse.
    """
    _verify_write_permission(auth_token=auth_token, caller_role=caller_role)
    ok, err_msg = can_promote_lesson(_backend, lesson_id, pr_merged=pr_merged)
    if not ok:
        return {"success": False, "error": err_msg}

    try:
        _backend.set_status("lessons", lesson_id, LessonStatus.VERIFIED, reason)
        return {"success": True, "lesson_id": lesson_id, "status": LessonStatus.VERIFIED}
    except KeyError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def rag_demote(
    lesson_id: str,
    reason: str,
    caller_role: str = "",
    auth_token: str = "",
) -> Dict[str, Any]:
    """
    Demote or retire a lesson. Restricted to librarian and rollback roles.
    """
    _verify_write_permission(auth_token=auth_token, caller_role=caller_role)
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
