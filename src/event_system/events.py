from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class Event:
    id: str
    topic: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or len(self.id.strip()) == 0:
            raise ValueError("Event id must be a non-empty string")
        if not isinstance(self.topic, str) or len(self.topic.strip()) == 0:
            raise ValueError("Event topic must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise TypeError("Payload must be a dict")
