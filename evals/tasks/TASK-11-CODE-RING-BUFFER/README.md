# Task Specification: Circular Ring Buffer with Overwrite Policy

## 1. Class Contract
Implement `RingBuffer`, `BufferFullError`, and `BufferEmptyError` in `src/ring_buffer.py`.

### Constructor Signature
```python
def __init__(self, capacity: int, overwrite: bool = False) -> None:
```
- `capacity`: Maximum elements in buffer. Must be integer > 0. If `<= 0`, raise `ValueError("Capacity must be positive")`.
- `overwrite`: If `True`, pushing to a full buffer drops the oldest element. If `False`, pushing to a full buffer raises `BufferFullError`.

### Methods
1. `push(self, item: Any) -> None`: Inserts `item` at the tail.
2. `pop(self) -> Any`: Removes and returns item from head. If empty, raises `BufferEmptyError`.
3. `peek(self) -> Any`: Returns item from head without removing. If empty, raises `BufferEmptyError`.
4. `is_empty(self) -> bool` and `is_full(self) -> bool`.
5. `__len__(self) -> int` and `__iter__(self)` yielding elements in FIFO order.
