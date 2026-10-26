import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, List, Optional
from src.event_system.dead_letter import DeadLetterQueue
from src.event_system.events import Event


class EventBus:
    """Asynchronous Event Bus supporting wildcard subscriptions, FIFO middleware, and DLQ retries."""

    def __init__(self, dlq: Optional[DeadLetterQueue] = None, max_retries: int = 2) -> None:
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        self.dlq: Optional[DeadLetterQueue] = dlq
        self.max_retries: int = max_retries
        self._subscribers: dict[str, list[Callable[[Event], Awaitable[None]]]] = defaultdict(list)
        self._middleware: list[
            Callable[[Event, Callable[[Event], Awaitable[None]]], Awaitable[None]]
        ] = []

    def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        if not isinstance(topic, str) or len(topic.strip()) == 0:
            raise ValueError("Topic must be a non-empty string")
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> bool:
        if topic in self._subscribers and handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)
            return True
        return False

    def add_middleware(
        self,
        middleware_fn: Callable[[Event, Callable[[Event], Awaitable[None]]], Awaitable[None]],
    ) -> None:
        self._middleware.append(middleware_fn)

    async def _dispatch_to_handlers(self, event: Event) -> None:
        # Collect matching handlers deduplicated
        candidate_handlers: list[Callable[[Event], Awaitable[None]]] = []
        seen = set()

        # Specific topic handlers
        for h in self._subscribers.get(event.topic, []):
            if id(h) not in seen:
                candidate_handlers.append(h)
                seen.add(id(h))

        # Wildcard handlers
        for h in self._subscribers.get("*", []):
            if id(h) not in seen:
                candidate_handlers.append(h)
                seen.add(id(h))

        if not candidate_handlers:
            return

        async def invoke_handler_with_retries(
            handler: Callable[[Event], Awaitable[None]]
        ) -> None:
            last_err: Optional[Exception] = None
            total_attempts = 1 + self.max_retries

            for attempt in range(total_attempts):
                try:
                    await handler(event)
                    return
                except Exception as e:
                    last_err = e

            # All retries failed
            if self.dlq is not None:
                self.dlq.put(event, str(last_err), self.max_retries)
            else:
                raise RuntimeError(
                    f"Handler failed after {self.max_retries} retries with no DLQ configured: {str(last_err)}"
                )

        await asyncio.gather(*(invoke_handler_with_retries(h) for h in candidate_handlers))

    async def publish(self, event: Event) -> None:
        if not isinstance(event, Event):
            raise TypeError("Event must be an instance of Event")

        # Compose middleware pipeline
        async def run_pipeline(idx: int, ev: Event) -> None:
            if idx < len(self._middleware):
                mw = self._middleware[idx]

                async def next_handler(e: Event) -> None:
                    await run_pipeline(idx + 1, e)

                await mw(ev, next_handler)
            else:
                await self._dispatch_to_handlers(ev)

        await run_pipeline(0, event)
