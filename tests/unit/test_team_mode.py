import os
import pytest
from pathlib import Path
from scripts.team_orchestrator import (
    run_phase_a_debate,
    synthesize_decision_record,
    create_team_board,
    update_board_status,
    verify_scope_isolation,
)


@pytest.fixture
def run_env(tmp_path):
    run_id = "test-team-20261026"
    team_dir = tmp_path / "team" / run_id
    decisions_dir = tmp_path / "decisions"
    team_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    return run_id, team_dir, decisions_dir


def test_phase_a_debate_generation(run_env):
    run_id, team_dir, _ = run_env
    task_meta = {
        "id": "TASK-19-MULTI-RAFT-KV",
        "title": "Distributed In-Memory Raft Consensus KV Store",
        "category": "multi_module",
        "spec": "Implement Raft consensus with log replication and state machine."
    }

    debate_res = run_phase_a_debate(run_id=run_id, task_meta=task_meta, output_dir=team_dir)
    assert debate_res["success"] is True
    assert debate_res["rounds"] <= 2  # Capped at 2 debate rounds

    # Verify proposal files created for all 3 debate roles
    proposals_dir = team_dir / "proposals"
    assert (proposals_dir / "architect.md").exists()
    assert (proposals_dir / "physmath-verifier.md").exists()
    assert (proposals_dir / "adversarial-tester.md").exists()

    # Verify critique round files created
    critiques_dir = team_dir / "critiques"
    assert (critiques_dir / "architect.md").exists()
    assert (critiques_dir / "adversarial-tester.md").exists()


def test_adr_synthesis(run_env):
    run_id, team_dir, decisions_dir = run_env
    task_meta = {
        "id": "TASK-19-MULTI-RAFT-KV",
        "title": "Distributed In-Memory Raft Consensus KV Store",
        "category": "multi_module",
    }
    # Create mock proposal files
    p_dir = team_dir / "proposals"
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "architect.md").write_text("# Architect Proposal\nOption A: Modular Log Engine", encoding="utf-8")
    (p_dir / "physmath-verifier.md").write_text("# Verifier Proposal\nState invariants", encoding="utf-8")
    (p_dir / "adversarial-tester.md").write_text("# Adversarial Proposal\nSplit-brain stress", encoding="utf-8")

    adr_path = synthesize_decision_record(
        run_id=run_id,
        task_meta=task_meta,
        team_dir=team_dir,
        decisions_dir=decisions_dir,
    )
    assert adr_path.exists()
    content = adr_path.read_text(encoding="utf-8")
    assert "Architecture Decision Record" in content
    assert "TASK-19-MULTI-RAFT-KV" in content
    assert "Considered Alternatives" in content
    assert "Decision" in content
    assert "File Scope Allocations" in content


def test_board_management_and_scope_isolation(run_env):
    run_id, team_dir, _ = run_env
    slices = [
        {"slice_id": "SLICE-1", "assignee": "implementer-1", "files": ["src/raft_kv/log.py"]},
        {"slice_id": "SLICE-2", "assignee": "implementer-2", "files": ["src/raft_kv/state_machine.py"]},
        {"slice_id": "SLICE-3", "assignee": "implementer-3", "files": ["src/raft_kv/engine.py"]},
    ]

    # Verify disjoint scopes
    assert verify_scope_isolation(slices) is True

    # Overlapping scopes must fail
    bad_slices = [
        {"slice_id": "SLICE-1", "assignee": "implementer-1", "files": ["src/raft_kv/engine.py"]},
        {"slice_id": "SLICE-2", "assignee": "implementer-2", "files": ["src/raft_kv/engine.py"]},
    ]
    assert verify_scope_isolation(bad_slices) is False

    # Create board
    board_path = create_team_board(run_id=run_id, slices=slices, output_dir=team_dir)
    assert board_path.exists()
    content = board_path.read_text(encoding="utf-8")
    assert "SLICE-1" in content
    assert "BACKLOG" in content

    # Update board status
    update_board_status(board_path, slice_id="SLICE-1", new_status="VERIFIED")
    updated_content = board_path.read_text(encoding="utf-8")
    assert "| `SLICE-1` | `implementer-1` | `src/raft_kv/log.py` | **VERIFIED** |" in updated_content
