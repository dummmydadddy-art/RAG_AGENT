# Traceability Matrix: TASK-07-MULTI-EVENT-BUS

| Test Assertion | Spec Sentence Justification |
|---|---|
| `Event("", "topic", {})` raises `ValueError` | "id: Non-empty string. If not isinstance(id, str) or empty string, raise ValueError(\"Event id must be a non-empty string\")" |
| `EventBus(max_retries=-1)` raises `ValueError` | "If max_retries < 0, raise ValueError(\"max_retries must be non-negative\")" |
| Wildcard subscriber `*` receives event | "Wildcard \"*\" matches all published event topics." |
| Middleware executes in order and can short-circuit | "If middleware does not await next_handler(event), event dispatch is short-circuited." |
| Handler failure retried `max_retries` times before DLQ routing | "If a handler raises an exception, it is immediately retried up to max_retries times... writes to DLQ via dlq.put" |
| Handler failure with `dlq=None` raises `RuntimeError` | "If dlq is None: raises RuntimeError" |
| Unsubscribe returns `True` then `False` | "Returns True if found and removed, False otherwise." |
