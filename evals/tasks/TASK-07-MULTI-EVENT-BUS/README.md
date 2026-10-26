# Task Specification: Asynchronous Event Bus with DLQ and Middleware

## 1. Multi-Module Package Contract
Implement the event bus package across three files in `src/event_system/`:
1. `src/event_system/events.py`
2. `src/event_system/dead_letter.py`
3. `src/event_system/bus.py`

### Module 1: `src/event_system/events.py`
```python
from dataclasses import dataclass, field
from typing import Any, Optional
import time

@dataclass
class Event:
    id: str
    topic: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
```
- `id`: Non-empty string. If not `isinstance(id, str)` or empty string, raise `ValueError("Event id must be a non-empty string")`.
- `topic`: Non-empty string. If not `isinstance(topic, str)` or empty string, raise `ValueError("Event topic must be a non-empty string")`.
- `payload`: Must be an instance of `dict`. If not, raise `TypeError("Payload must be a dict")`.

### Module 2: `src/event_system/dead_letter.py`
```python
class DeadLetterQueue:
    def __init__(self) -> None:
        ...
```
1. `put(self, event: Event, failure_reason: str, retry_count: int) -> None`:
   - Records failed event as a dictionary: `{"event": event, "failure_reason": str(failure_reason), "retry_count": int(retry_count)}`.
2. `get_failed_events(self, topic: Optional[str] = None) -> list[dict[str, Any]]`:
   - Returns a shallow copy list of stored failure records.
   - If `topic` is provided, filters for events where `event.topic == topic`.
   - Inspection is non-destructive (does not remove events).
3. `clear(self) -> None`:
   - Clears all records from the DLQ.
4. `__len__(self) -> int`:
   - Returns the total count of failed events in the queue.

### Module 3: `src/event_system/bus.py`
```python
class EventBus:
    def __init__(self, dlq: Optional[DeadLetterQueue] = None, max_retries: int = 2) -> None:
        ...
```
- `dlq`: Optional `DeadLetterQueue` instance.
- `max_retries`: Non-negative integer. If `max_retries < 0`, raise `ValueError("max_retries must be non-negative")`.
- `subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None`:
   - Subscribes an async handler to a topic.
   - Wildcard `"*"` matches all published event topics.
- `unsubscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> bool`:
   - Unregisters handler. Returns `True` if found and removed, `False` otherwise.
- `add_middleware(self, middleware_fn: Callable[[Event, Callable[[Event], Awaitable[None]]], Awaitable[None]]) -> None`:
   - Registers middleware in FIFO execution order. If middleware does not await `next_handler(event)`, event dispatch is short-circuited.
- `async publish(self, event: Event) -> None`:
   - Dispatches `event` through middleware chain.
   - Handlers matching `event.topic` and wildcard `"*"` are deduplicated so that each unique handler is called at most once per event.
   - Matching handlers are executed concurrently via `asyncio.gather`.
   - If a handler raises an exception, it is immediately retried up to `max_retries` times (total attempts = $1 + 	ext{max\_retries}$).
   - If all retries fail:
     - If `dlq` is configured: writes to DLQ via `dlq.put(event, str(error), max_retries)`.
     - If `dlq is None`: raises `RuntimeError(f"Handler failed after {max_retries} retries with no DLQ configured")`.
