"""
src/web/schemas.py

Pydantic v2 data models and interface contracts for the ChatGPT Web Gateway:
- Chat request/streaming schemas
- Code execution request/response schemas
- RAG lesson query and summary schemas
- Conversation session history schemas
- Health and hardware telemetry schemas
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 1. CHAT & STREAMING SCHEMAS
# ============================================================================

class ChatRequest(BaseModel):
    """Payload for initiating a chat completion."""
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional existing conversation ID. If omitted, a new conversation is created."
    )
    message: str = Field(
        ...,
        min_length=1,
        description="User prompt / question text."
    )
    model: str = Field(
        default="stem-coder-expert:latest",
        description="Ollama model identifier."
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM."
    )
    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability."
    )
    enable_rag: bool = Field(
        default=True,
        description="Whether to retrieve lessons and context from vectors.sqlite."
    )
    enable_physmath: bool = Field(
        default=True,
        description="Whether to run PhysMath MCP verification when math/units are present."
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt override."
    )


class CitationItem(BaseModel):
    """Reference citation attached to assistant response."""
    id: str
    collection: str
    text: str
    score: float = 0.0
    source: str = "vectors.sqlite"
    metadata: Optional[Dict[str, Any]] = None


class TelemetryItem(BaseModel):
    """Runtime telemetry attached to assistant response or health check."""
    elapsed_seconds: float = 0.0
    physmath: Optional[Dict[str, Any]] = None
    citations_count: int = 0
    token_count: Optional[int] = None
    model: str = "stem-coder-expert:latest"


# ============================================================================
# 2. CODE EXECUTION SCHEMAS
# ============================================================================

class ExecuteRequest(BaseModel):
    """Payload for sandboxed polyglot code execution."""
    language: str = Field(
        ...,
        description="Target language: python, typescript, php, sql, cpp, rust, java, or go."
    )
    code: str = Field(
        ...,
        description="Source code to execute."
    )
    test_suite: str = Field(
        default="",
        description="Optional unit test suite or verification code."
    )
    timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=30.0,
        description="Execution timeout in seconds."
    )
    memory_limit_mb: int = Field(
        default=256,
        ge=32,
        le=1024,
        description="Win32 Job Object memory ceiling in megabytes."
    )


class ExecuteResponse(BaseModel):
    """Consolidated result of a sandboxed execution."""
    success: bool
    language: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0
    sandboxed: bool = True
    security_status: str = "clean"  # "clean" | "blocked"
    violations: List[str] = Field(default_factory=list)
    timed_out: bool = False
    memory_breached: bool = False
    runtime: str = ""
    error_message: Optional[str] = None


# ============================================================================
# 3. LESSON & RAG SCHEMAS
# ============================================================================

class LessonItem(BaseModel):
    """Summary of a retrieved RAG document or lesson."""
    id: str
    collection: str
    text: str
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    score: float = 0.0
    created_at: Optional[str] = None


class LessonListResponse(BaseModel):
    """Paginated or listed response for lessons."""
    total: int
    lessons: List[LessonItem]


class LessonSearchRequest(BaseModel):
    """Payload for searching lessons."""
    query: str
    collection: Optional[str] = None
    status: Optional[str] = None
    limit: int = 20


class FeedbackRequest(BaseModel):
    """Payload for submitting feedback on a retrieved RAG lesson."""
    helpful: bool = Field(
        ...,
        description="Whether the cited lesson was helpful or unhelpful."
    )
    comment: Optional[str] = Field(
        default=None,
        description="Optional user comment or feedback text."
    )


class FeedbackResponse(BaseModel):
    """Response confirming feedback recording."""
    status: str = Field(
        default="recorded",
        description="Status confirmation string."
    )
    lesson_id: str = Field(
        ...,
        description="Identifier of the rated lesson."
    )
    helpful: bool = Field(
        ...,
        description="Recorded helpfulness boolean."
    )
    comment: Optional[str] = Field(
        default=None,
        description="Recorded optional comment."
    )


# ============================================================================
# 4. CONVERSATION SCHEMAS
# ============================================================================

class MessageItem(BaseModel):
    """Single message within a conversation."""
    id: str
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    telemetry: Optional[Dict[str, Any]] = None
    created_at: str


class ConversationSummary(BaseModel):
    """High-level summary of a conversation session for sidebar display."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(BaseModel):
    """Full conversation detail with all messages."""
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageItem] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    """Payload for creating a conversation."""
    title: Optional[str] = None


class ConversationUpdateRequest(BaseModel):
    """Payload for updating a conversation."""
    title: str = Field(..., min_length=1)


# ============================================================================
# 5. HEALTH & SYSTEM TELEMETRY SCHEMAS
# ============================================================================

class ServiceStatus(BaseModel):
    """Status details for an individual subsystem."""
    status: str
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Overall system health and subsystem status."""
    status: str
    timestamp: str
    services: Dict[str, Any]
    hardware_budget: Dict[str, Any]
