from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RaftLogEntry(BaseModel):
    index: int
    term: int
    command: Dict[str, Any]


class RaftLog:
    """
    Raft replicated append-only log.
    """

    def __init__(self) -> None:
        self.entries: List[RaftLogEntry] = []

    def append(self, term: int, command: Dict[str, Any]) -> int:
        idx = len(self.entries) + 1
        entry = RaftLogEntry(index=idx, term=term, command=command)
        self.entries.append(entry)
        return idx

    def get(self, index: int) -> Optional[RaftLogEntry]:
        if 1 <= index <= len(self.entries):
            return self.entries[index - 1]
        return None

    def last_index(self) -> int:
        return len(self.entries)

    def last_term(self) -> int:
        return self.entries[-1].term if self.entries else 0
