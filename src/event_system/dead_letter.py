from typing import Any, Optional
from src.event_system.events import Event


class DeadLetterQueue:
    """In-memory Dead Letter Queue storing failed events and retry metadata."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def put(self, event: Event, failure_reason: str, retry_count: int) -> None:
        self._records.append(
            {
                "event": event,
                "failure_reason": str(failure_reason),
                "retry_count": int(retry_count),
            }
        )

    def get_failed_events(self, topic: Optional[str] = None) -> list[dict[str, Any]]:
        if topic is None:
            return list(self._records)
        return [r for r in self._records if r["event"].topic == topic]

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)
