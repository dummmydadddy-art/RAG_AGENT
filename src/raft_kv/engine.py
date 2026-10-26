from typing import Any, Dict, List, Optional
from src.raft_kv.log import RaftLog
from src.raft_kv.state_machine import KVStateMachine


class RaftKVEngine:
    """
    Raft consensus coordinator combining RaftLog replication with KVStateMachine commits.
    """

    def __init__(self, node_id: str, peers: List[str]) -> None:
        self.node_id = node_id
        self.peers = list(peers)
        self.log = RaftLog()
        self.state_machine = KVStateMachine()
        self.current_term = 0
        self.commit_index = 0
        self.last_applied = 0
        self._is_leader = False

    def become_leader(self, term: int) -> None:
        self.current_term = term
        self._is_leader = True

    def is_leader(self) -> bool:
        return self._is_leader

    def append_command(self, term: int, command: Dict[str, Any]) -> int:
        return self.log.append(term, command)

    def commit_up_to(self, commit_index: int) -> int:
        self.commit_index = min(commit_index, self.log.last_index())
        applied_count = 0
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log.get(self.last_applied)
            if entry:
                self.state_machine.apply(entry.command)
                applied_count += 1
        return applied_count

    def get(self, key: str) -> Optional[Any]:
        return self.state_machine.get(key)
