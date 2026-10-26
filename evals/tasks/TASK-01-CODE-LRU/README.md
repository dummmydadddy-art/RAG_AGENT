# Thread-safe LRU Cache with Expiration TTL

**Category**: pure_coding
**Held Out**: False

## Specification
Implement `LRUCache(capacity: int, default_ttl_seconds: Optional[float] = None)` in `src/lru_cache.py`.
Methods:
- `put(key: str, value: Any, ttl: Optional[float] = None) -> None`: Stores or updates a key-value pair.
- `get(key: str) -> Optional[Any]`: Returns the value and marks the key as most recently used. Returns None if expired or not found.
- `delete(key: str) -> bool`: Removes key, returns True if existed.
- `__len__() -> int`: Returns current non-expired count.
- Thread-safe using `threading.RLock`.
When capacity is exceeded, evicts the least recently used item.
