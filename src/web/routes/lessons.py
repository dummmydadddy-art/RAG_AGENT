"""
src/web/routes/lessons.py

Endpoints for querying and searching RAG lessons, knowledge items, and curriculum documents
stored in vectors.sqlite.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from src.web.database import get_lessons
from src.web.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    LessonItem,
    LessonListResponse,
    LessonSearchRequest,
)

logger = logging.getLogger("web.routes.lessons")
router = APIRouter(tags=["Lessons & Knowledge"])


@router.get("/lessons", response_model=LessonListResponse)
def list_lessons(
    q: Optional[str] = Query(default=None, description="Keyword search query"),
    collection: Optional[str] = Query(default=None, description="Collection name filter (e.g. lessons, knowledge, polyglot_coding, stem_curriculum)"),
    status: Optional[str] = Query(default=None, description="Status filter (e.g. verified, candidate)"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
) -> LessonListResponse:
    """
    Retrieves filtered lessons and documents from vectors.sqlite.
    """
    raw_results = get_lessons(query=q, collection=collection, status=status, limit=limit)
    lessons = [
        LessonItem(
            id=r["id"],
            collection=r["collection"],
            text=r["text"],
            status=r["status"],
            metadata=r["metadata"],
            score=r["score"],
            created_at=r["created_at"],
        )
        for r in raw_results
    ]
    return LessonListResponse(total=len(lessons), lessons=lessons)


@router.post("/lessons/search", response_model=LessonListResponse)
def search_lessons(req: LessonSearchRequest) -> LessonListResponse:
    """
    Searches lessons using structured POST payload with keyword scoring and filters.
    """
    raw_results = get_lessons(
        query=req.query,
        collection=req.collection,
        status=req.status,
        limit=req.limit,
    )
    lessons = [
        LessonItem(
            id=r["id"],
            collection=r["collection"],
            text=r["text"],
            status=r["status"],
            metadata=r["metadata"],
            score=r["score"],
            created_at=r["created_at"],
        )
        for r in raw_results
    ]
    return LessonListResponse(total=len(lessons), lessons=lessons)


@router.post("/lessons/{lesson_id}/feedback", response_model=FeedbackResponse)
def record_lesson_feedback(lesson_id: str, payload: FeedbackRequest) -> FeedbackResponse:
    """
    Records user feedback (helpful or unhelpful) for a retrieved RAG lesson.
    """
    logger.info(f"Feedback received for lesson '{lesson_id}': helpful={payload.helpful}")
    return FeedbackResponse(
        status="recorded",
        lesson_id=lesson_id,
        helpful=payload.helpful,
        comment=payload.comment,
    )

