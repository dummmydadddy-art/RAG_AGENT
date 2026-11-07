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


# ============================================================================
# 6. AUTONOMOUS SELF-LEARNING SCHEMAS
# ============================================================================

class LearningStatusResponse(BaseModel):
    """Status report for the autonomous self-learning daemon."""
    status: str = Field(..., description="'Running', 'Stopped', or 'Idle'")
    pid: Optional[int] = Field(default=None, description="Operating system PID of learning daemon")
    uptime_seconds: float = Field(default=0.0, description="Process uptime in seconds")
    cycle_count: int = Field(default=0, description="Completed self-play cycles")
    total_lessons: int = Field(default=0, description="Total harvested lessons in vectors.sqlite")
    last_cycle_timestamp: Optional[str] = Field(default=None, description="ISO timestamp of last activity")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Diagnostic telemetry")


class LearningStartRequest(BaseModel):
    """Payload to start the autonomous self-learning loop."""
    interval_seconds: float = Field(default=15.0, ge=1.0, le=3600.0, description="Sleep interval between cycles")
    max_iterations: int = Field(default=0, ge=0, description="Maximum iterations (0 for infinite loop)")


class LearningActionResponse(BaseModel):
    """Response payload for start/stop lifecycle commands."""
    status: str = Field(
        ...,
        description="Action outcome: 'started', 'already_running', 'stopped', 'not_running', or 'error'"
    )
    pid: Optional[int] = Field(default=None, description="Process ID")
    message: str = Field(..., description="Human-readable status summary")


class AccuracyMetricPoint(BaseModel):
    """Data model representing an accuracy evaluation point in the web API."""
    id: str = Field(..., description="Unique record identifier")
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp")
    cycle_iteration: int = Field(..., description="Self-play cycle index")
    pass_at_1: float = Field(..., description="Pass@1 accuracy rate (0.0 - 1.0)")
    test_pass_rate: float = Field(..., description="Average unit test pass rate (0.0 - 1.0)")
    avg_patch_iterations: float = Field(..., description="Average repair iterations needed")
    invariant_violation_rate: float = Field(..., description="Rate of physical/AST invariant violations")
    invariant_compliance: Optional[float] = Field(default=None, description="Invariant compliance rate (1 - violations)")
    lessons_count: int = Field(..., description="Count of active RAG lessons during evaluation")
    lessons_enabled: bool = Field(default=True, description="Whether lessons were supplied to solver")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Supplementary evaluation details")


class AblationComparison(BaseModel):
    """Ablation benchmark comparison between with_lessons and without_lessons conditions."""
    num_samples: int = Field(default=0, description="Number of evaluation samples per condition")
    with_lessons: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics when RAG lessons are active")
    without_lessons: Dict[str, Any] = Field(default_factory=dict, description="Baseline performance metrics without RAG lessons")
    deltas: Dict[str, float] = Field(default_factory=dict, description="Metric differentials (with_lessons - without_lessons)")
    lesson_advantage_demonstrated: bool = Field(default=True, description="True if lessons improve or maintain Pass@1")


class AccuracyHistoryResponse(BaseModel):
    """Longitudinal accuracy history and ablation evaluation response."""
    current_pass_at_1: float = Field(default=1.0, description="Current Pass@1 benchmark score")
    history: List[AccuracyMetricPoint] = Field(default_factory=list, description="Historical accuracy benchmark points")
    ablation: Optional[AblationComparison] = Field(default=None, description="Ablation comparison metrics")
    summary: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Summary statistics across historical benchmarks")


class HarvesterStatusResponse(BaseModel):
    """Status report for the Autonomous Web Harvester and SQ8 ingestion pipeline."""
    status: str = Field(default="healthy", description="Operational status: 'healthy', 'degraded', or 'idle'")
    total_sources_scraped: int = Field(default=0, description="Total raw sources or documents harvested")
    ingested_chunks: int = Field(default=0, description="Total chunks ingested into material_chunks")
    shannon_entropy_score: float = Field(default=4.5, description="Shannon character entropy score of harvested corpus (expected 3.0 <= H <= 6.0)")
    fifo_queue_utilization: float = Field(default=0.0, description="FIFO queue utilization percentage out of max ceiling")
    max_chunks: int = Field(default=500, description="Maximum ceiling of material chunks before FIFO eviction")
    material_chunks_count: int = Field(default=0, description="Current row count in material_chunks table")
    stem_knowledge_docs_count: int = Field(default=0, description="Current document count in stem_knowledge collection")
    last_run: Optional[str] = Field(default=None, description="ISO timestamp of last harvester execution")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Supplementary pipeline statistics")

