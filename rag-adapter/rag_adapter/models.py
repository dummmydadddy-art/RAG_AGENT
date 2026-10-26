from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LessonStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    RETIRED = "retired"


class Evidence(BaseModel):
    task_id: str = ""
    commit: str = ""
    tests: List[str] = Field(default_factory=list)
    review: str = "passed"


class Lesson(BaseModel):
    id: str
    title: str
    rule: str
    domain: List[str] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    status: LessonStatus = LessonStatus.CANDIDATE
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: Optional[str] = None
    use_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    supersedes: List[str] = Field(default_factory=list)


class Hit(BaseModel):
    doc_id: str
    collection: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class Doc(BaseModel):
    doc_id: str
    collection: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
