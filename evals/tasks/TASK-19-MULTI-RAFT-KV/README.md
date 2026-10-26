# Task Specification: Distributed In-Memory Raft Consensus KV Store

## 1. Multi-Module Architecture
Implement modules in `src/raft_kv/`:
- `log.py`: `RaftLogEntry`, `RaftLog` with append, term tracking, truncate at index.
- `state_machine.py`: `KVStateMachine` executing `SET(key, value)`, `DELETE(key)`, and `GET(key)`.
- `engine.py`: `RaftKVEngine` coordinating consensus log and state machine replication.

### Engine Contract
```python
class RaftKVEngine:
    def __init__(self, node_id: str, peers: List[str]) -> None:
    def append_command(self, term: int, command: Dict[str, Any]) -> int:
    def commit_up_to(self, commit_index: int) -> int:
    def get(self, key: str) -> Optional[Any]:
    def is_leader(self) -> bool:
    def become_leader(self, term: int) -> None:
```
