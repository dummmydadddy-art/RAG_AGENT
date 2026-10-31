"""
src/web/routes/conversations.py

CRUD endpoints for conversation sessions and message history:
- GET /api/conversations: List all conversation sessions
- POST /api/conversations: Create new conversation session
- GET /api/conversations/{id}: Retrieve conversation detail with messages
- PATCH /api/conversations/{id}: Update conversation title
- DELETE /api/conversations/{id}: Delete conversation and its messages
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from src.web.database import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    update_conversation_title,
)
from src.web.schemas import (
    ConversationCreateRequest,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdateRequest,
)

logger = logging.getLogger("web.routes.conversations")
router = APIRouter(tags=["Conversations"])


@router.get("/conversations", response_model=List[ConversationSummary])
def get_conversations() -> List[ConversationSummary]:
    """
    Returns list of conversation summaries ordered by updated_at descending.
    """
    rows = list_conversations()
    return [ConversationSummary(**r) for r in rows]


@router.post("/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def new_conversation(req: ConversationCreateRequest) -> ConversationDetail:
    """
    Creates a new conversation session.
    """
    conv = create_conversation(title=req.title)
    return ConversationDetail(
        id=conv["id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        messages=[],
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def read_conversation(conversation_id: str) -> ConversationDetail:
    """
    Retrieves full conversation details and all associated messages.
    """
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return ConversationDetail(**conv)


@router.patch("/conversations/{conversation_id}", response_model=Dict[str, Any])
def rename_conversation(conversation_id: str, req: ConversationUpdateRequest) -> Dict[str, Any]:
    """
    Updates the title of a conversation.
    """
    updated = update_conversation_title(conversation_id, req.title)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return {"status": "updated", "id": conversation_id, "title": req.title}


@router.delete("/conversations/{conversation_id}", response_model=Dict[str, Any])
def remove_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Deletes a conversation session and all its messages.
    """
    deleted = delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return {"status": "deleted", "id": conversation_id}
