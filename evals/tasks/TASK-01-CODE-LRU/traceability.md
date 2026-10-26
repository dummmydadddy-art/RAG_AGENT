# Traceability Matrix: TASK-01-CODE-LRU

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert LRUCache(capacity=0)` raises `ValueError` | "If capacity <= 0 or not an int, raise ValueError(\"Capacity must be positive\")" |
| `assert LRUCache(capacity=2, default_ttl_seconds=-1)` raises `ValueError` | "If <= 0.0, raise ValueError(\"TTL must be positive\")" |
| `cache.put("a", 1); cache.put("b", 2); cache.get("a"); cache.put("c", 3); assert cache.get("b") is None` | "evicts the least recently used (LRU) non-expired key" and "updates its access order (marks as most recently used)" |
| `clock.advance(10.0); assert cache.get("k") is None` | "If key does not exist or has expired (current_time >= expiration_time), removes the expired key if present and returns None." |
| `assert len(cache) == 0` after expiration | "Returns the current number of non-expired keys stored in the cache." |
| `cache.put(123, "val")` raises `TypeError` | "key: Must be a string. If not an instance of str, raise TypeError(\"Key must be a string\")" |
| `cache.get(123)` raises `TypeError` | "key: Must be a string. If not an instance of str, raise TypeError(\"Key must be a string\")" |
| `assert cache.delete("nonexistent") is False` | "If key does not exist or has already expired: removes expired key if present and returns False." |
| `assert "a" in cache` without updating LRU | "Checking containment MUST NOT alter the LRU access order." |
| Overwriting existing key does not evict other keys | "If key is already present (even if expired): updates value... Does not evict any other key." |
| 10 threads concurrently put and get 100 keys; `assert len(cache) <= capacity` | "All public methods must be thread-safe under concurrent multi-threaded execution using threading.RLock()." |
