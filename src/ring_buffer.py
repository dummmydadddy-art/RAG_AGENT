from typing import Any, Iterator, List


class BufferFullError(Exception):
    """Raised when pushing to a full buffer with overwrite=False."""
    pass


class BufferEmptyError(Exception):
    """Raised when popping or peeking from an empty buffer."""
    pass


class RingBuffer:
    """
    Fixed-capacity circular ring buffer supporting FIFO order and optional overwrite.
    """

    def __init__(self, capacity: int, overwrite: bool = False) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = int(capacity)
        self.overwrite = bool(overwrite)
        self.buffer: List[Any] = [None] * self.capacity
        self.head = 0
        self.tail = 0
        self.size = 0

    def push(self, item: Any) -> None:
        if self.is_full():
            if not self.overwrite:
                raise BufferFullError("Buffer is full")
            # Overwrite oldest element at head
            self.buffer[self.tail] = item
            self.tail = (self.tail + 1) % self.capacity
            self.head = (self.head + 1) % self.capacity
        else:
            self.buffer[self.tail] = item
            self.tail = (self.tail + 1) % self.capacity
            self.size += 1

    def pop(self) -> Any:
        if self.is_empty():
            raise BufferEmptyError("Buffer is empty")
        item = self.buffer[self.head]
        self.buffer[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.size -= 1
        return item

    def peek(self) -> Any:
        if self.is_empty():
            raise BufferEmptyError("Buffer is empty")
        return self.buffer[self.head]

    def is_empty(self) -> bool:
        return self.size == 0

    def is_full(self) -> bool:
        return self.size == self.capacity

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[Any]:
        curr = self.head
        for _ in range(self.size):
            yield self.buffer[curr]
            curr = (curr + 1) % self.capacity
