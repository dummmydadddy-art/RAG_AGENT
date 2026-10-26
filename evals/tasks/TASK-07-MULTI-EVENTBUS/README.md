# Asynchronous Event Bus with Middleware & Dead Letter Queue

**Category**: multi_module
**Held Out**: False

## Specification
Implement a modular event system in `src/event_system/`:
- `src/event_system/events.py`: `Event(topic: str, payload: dict, id: Optional[str] = None)`
- `src/event_system/bus.py`: `EventBus` with `subscribe(topic: str, handler: Callable)`, `publish(event: Event)`, and middleware registration `use(middleware)`.
- `src/event_system/dead_letter.py`: `DeadLetterQueue` recording failed events after max retries (default 3 retries).
Middleware can inspect, mutate, or abort event delivery.
