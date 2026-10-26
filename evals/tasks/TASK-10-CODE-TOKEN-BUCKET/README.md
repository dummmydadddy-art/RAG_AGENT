# Task Specification: Thread-safe Token Bucket Rate Limiter

## 1. Class Contract
Implement `TokenBucket` in `src/token_bucket.py`.

### Constructor Signature
```python
def __init__(
    self,
    capacity: float,
    refill_rate: float,
    time_fn: Optional[Callable[[], float]] = None
) -> None:
```
- `capacity`: Maximum bucket capacity (tokens). Must be float/int > 0. If `<= 0`, raise `ValueError("Capacity must be positive")`.
- `refill_rate`: Refill rate in tokens per second. Must be float/int > 0. If `<= 0`, raise `ValueError("Refill rate must be positive")`.
- `time_fn`: Monotonic clock callable returning current time in float seconds. Defaults to `time.monotonic`.

### Methods
1. `consume(self, tokens: float = 1.0) -> bool`:
   - Refills available tokens based on elapsed time since last call up to `capacity`.
   - If `tokens <= 0`, raise `ValueError("Tokens to consume must be positive")`.
   - If `available_tokens >= tokens`: deducts `tokens` and returns `True`.
   - If `available_tokens < tokens`: deducts zero tokens and returns `False`.
   - Thread-safe across concurrent threads.

2. `available_tokens(self) -> float`:
   - Returns current tokens available after applying fractional refill up to the query time.
