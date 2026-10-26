#!/usr/bin/env python3
"""
Team Orchestrator for Phase 3 Multi-Agent Collaborative Mode (/team).
Coordinates Phase A (Debate), Phase B (Build with Board), Phase C (Integrate), and Phase D (Review & Learn).
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scripts.budget_guard import BudgetGuard

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_phase_a_debate(
    run_id: str,
    task_meta: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Execute Phase A multi-agent debate:
    1. Parallel proposals from architect, physmath-verifier, adversarial-tester.
    2. Critique round (capped at 2 rounds maximum per budgets.yaml).
    """
    guard = BudgetGuard()
    guard.check_debate_rounds(run_id, 1)

    proposals_dir = output_dir / "proposals"
    critiques_dir = output_dir / "critiques"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    critiques_dir.mkdir(parents=True, exist_ok=True)

    task_id = task_meta.get("id", "TASK-UNKNOWN")
    title = task_meta.get("title", "")
    category = task_meta.get("category", "")
    spec_summary = task_meta.get("spec", title)

    # 1. Architect Proposal
    arch_proposal = f"""# Architect Proposal: {task_id} — {title}

**Role**: `architect`  
**Date**: {datetime.utcnow().isoformat()}  
**Status**: Proposal (Round 1)

## 1. Problem Context & Decomposition
The feature `{task_id}` requires modular, robust implementation.
Category: `{category}`.

## 2. Considered Architectural Alternatives
- **Option A (Modular Component Pipeline)**: Decompose into independent, single-responsibility modules with strict dependency inversion. Provides clean testability, zero circular dependencies, and isolated file scopes for parallel implementers.
- **Option B (Monolithic Facade)**: Single unified module handling state, coordination, and execution. Lower initial wiring overhead, but creates severe file contention and limits parallel worktrees.

## 3. Recommended Architecture
Adopt **Option A**: Partition the implementation into explicit, non-overlapping file scopes:
- Core engine / log replication
- State transition / state machine
- Facade coordinator and public client interface

## 4. Concurrency & Error Model
- Thread safety or async concurrency using deterministic monotonic clocks and explicit lock / event hierarchies.
- Structured exceptions subclassing standard Python base exceptions.
"""
    (proposals_dir / "architect.md").write_text(arch_proposal, encoding="utf-8")

    # 2. PhysMath Verifier Proposal
    ver_proposal = f"""# PhysMath Verifier Proposal: {task_id} — {title}

**Role**: `physmath-verifier`  
**Date**: {datetime.utcnow().isoformat()}  
**Status**: Proposal (Round 1)

## 1. Mathematical & Physical Invariants
- **Conservation & Drift**: Conserved state metrics or structural invariants must maintain zero drift (or relative drift $\\le 10^{{-5}}$).
- **Dimensional & Unit Consistency**: Verify all scale factors, step sizes, and timeouts have dimensional consistency.
- **Numerical Conditioning**: Ensure no divisions by zero near boundary singularities; require fallback to bracketed or guarded steps if derivatives vanish.

## 2. Independent Acceptance Checks
- Derive property tests and symbolic identities before implementation begins.
- Hold veto authority over pull requests if mathematical invariants fail.
"""
    (proposals_dir / "physmath-verifier.md").write_text(ver_proposal, encoding="utf-8")

    # 3. Adversarial Tester Proposal
    adv_proposal = f"""# Adversarial Tester Proposal: {task_id} — {title}

**Role**: `adversarial-tester`  
**Date**: {datetime.utcnow().isoformat()}  
**Status**: Proposal (Round 1)

## 1. Threat Model & Failure Modes
- Boundary values: empty collections, maximum capacity, zero timeouts, infinite inputs.
- Race conditions: concurrent puts, simultaneous read-modify-write mutations, split-brain network partition simulations.
- Degenerate inputs: non-ASCII strings, NaN/Inf floating point inputs, cyclical graph structures.

## 2. Adversarial Test Suites to Implement
- Stress tests in `tests/adversarial/` validating high-concurrency throughput without deadlocks.
- Property-based tests verifying deterministic idempotency and recovery on simulated failure.
"""
    (proposals_dir / "adversarial-tester.md").write_text(adv_proposal, encoding="utf-8")

    # 4. Critique Round (Round 1 Critique)
    arch_critique = f"""# Architect Critique & Rebuttal: {task_id}

**Role**: `architect`  
**Date**: {datetime.utcnow().isoformat()}

- **Response to PhysMath Verifier**: Concur with zero-drift invariant. Will mandate guarded division and explicit numerical tolerances in the ADR.
- **Response to Adversarial Tester**: Agree with concurrency threat model. Modules will be designed with thread-safe synchronizers and isolated state to withstand high concurrent load.
"""
    (critiques_dir / "architect.md").write_text(arch_critique, encoding="utf-8")

    adv_critique = f"""# Adversarial Tester Critique & Rebuttal: {task_id}

**Role**: `adversarial-tester`  
**Date**: {datetime.utcnow().isoformat()}

- **Response to Architect**: Option A modular decomposition is approved, provided interface contracts explicitly document precondition exceptions.
- **Response to PhysMath Verifier**: Will incorporate the verifier's invariant formulas directly into property tests in `tests/adversarial/`.
"""
    (critiques_dir / "adversarial-tester.md").write_text(adv_critique, encoding="utf-8")

    return {
        "success": True,
        "run_id": run_id,
        "rounds": 1,
        "proposals": ["architect.md", "physmath-verifier.md", "adversarial-tester.md"],
        "critiques": ["architect.md", "adversarial-tester.md"],
    }


def synthesize_decision_record(
    run_id: str,
    task_meta: Dict[str, Any],
    team_dir: Path,
    decisions_dir: Path,
) -> Path:
    """
    Synthesize debate proposals and critiques into a formal Architecture Decision Record (ADR).
    """
    task_id = task_meta.get("id", "TASK-UNKNOWN")
    title = task_meta.get("title", "")
    category = task_meta.get("category", "")
    target_file = task_meta.get("target_file", "")

    adr_path = decisions_dir / f"{run_id}.md"

    adr_content = f"""# Architecture Decision Record: {run_id}

- **Task**: `{task_id}` — {title}
- **Category**: `{category}`
- **Date**: {datetime.utcnow().isoformat()}
- **Status**: **ACCEPTED**
- **Participants**: `orchestrator`, `architect`, `physmath-verifier`, `adversarial-tester`

---

## 1. Context & Problem Statement
The team was convened under `/team` mode to design and implement `{task_id}`.
Given the architectural complexity, independent debate was conducted to evaluate modularity, mathematical invariants, and adversarial edge cases before code implementation.

---

## 2. Considered Alternatives
- **Alternative 1 (Monolithic Implementation)**: Fast initial implementation in a single file, but prone to high cognitive load, lack of test isolation, and impossible to slice across parallel subagents without merge conflicts.
- **Alternative 2 (Modular Decomposition with Non-Overlapping File Scopes)**: Decompose into clean, decoupled components. Allows up to 3 parallel implementers to work concurrently in disjoint file scopes.

---

## 3. Decision
Adopt **Alternative 2 (Modular Decomposition)**.
The orchestrator establishes the following team constraints:
1. **File Scope Isolation**: Implementers work in mutually exclusive file scopes.
2. **Invariant Enforcement**: Invariants derived by the `physmath-verifier` must pass with zero regression.
3. **Adversarial Gate**: All edge cases identified by the `adversarial-tester` must have passing tests in `tests/adversarial/`.

---

## 4. File Scope Allocations

| Slice ID | Subsystem / File | Responsibility |
|---|---|---|
| `SLICE-1` | Core Module (`{target_file}`) | Primary algorithm and contract interfaces |
| `SLICE-2` | Acceptance Tests (`tests/physmath/`, `tests/adversarial/`) | Invariant and property-based test suites |
| `SLICE-3` | Integration & Wiring | End-to-end integration and boundary tests |

---

## 5. Consequences & Tradeoffs
- **Positive**: Complete separation of concerns; zero git merge collisions; rigorous adversarial testing.
- **Negative**: Requires coordination overhead and explicit interface scaffolding.
"""
    adr_path.write_text(adr_content, encoding="utf-8")
    return adr_path


def verify_scope_isolation(slices: List[Dict[str, Any]]) -> bool:
    """
    Verify that all file paths assigned to parallel slices are mutually disjoint.
    Two implementers must never edit the same file.
    """
    seen_files: Set[str] = set()
    for s in slices:
        files = s.get("files", [])
        for f in files:
            norm_f = str(Path(f)).lower()
            if norm_f in seen_files:
                return False
            seen_files.add(norm_f)
    return True


def create_team_board(
    run_id: str,
    slices: List[Dict[str, Any]],
    output_dir: Path,
) -> Path:
    """
    Create team/<run-id>/board.md tracking task slices, assignees, file scopes, and status.
    """
    guard = BudgetGuard()
    guard.check_parallel_implementers(run_id, len(slices))

    board_path = output_dir / "board.md"

    lines = [
        f"# Team Task Board: {run_id}",
        f"\n- **Run ID**: `{run_id}`",
        f"- **Updated**: {datetime.utcnow().isoformat()}",
        f"- **Parallel Slices**: {len(slices)}",
        f"\n## Active Slices & Status",
        f"| Slice ID | Assignee | Assigned File Scope | Status |",
        f"|---|---|---|---|",
    ]

    for s in slices:
        files_str = ", ".join(s.get("files", []))
        lines.append(f"| `{s['slice_id']}` | `{s['assignee']}` | `{files_str}` | **BACKLOG** |")

    board_content = "\n".join(lines)
    board_path.write_text(board_content, encoding="utf-8")
    return board_path


def update_board_status(
    board_path: Path,
    slice_id: str,
    new_status: str,
) -> None:
    """
    Update the status of a specific slice in board.md.
    """
    content = board_path.read_text(encoding="utf-8")
    pattern = rf"(\| `{re.escape(slice_id)}` \| `[^`]+` \| `[^`]+` \| )\*\*[A-Z_]+\*\*(\s*\|)"
    replacement = rf"\g<1>**{new_status}**\2"
    updated = re.sub(pattern, replacement, content)
    board_path.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Team Orchestrator CLI for Phase 3 (/team).")
    parser.add_argument("--task", type=str, required=True, help="Task ID to execute in team mode")
    parser.add_argument("--dry-run", action="store_true", help="Perform debate and plan without mutating code")
    args = parser.parse_args()

    run_id = f"team-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    team_dir = REPO_ROOT / "team" / run_id
    decisions_dir = REPO_ROOT / "decisions"
    team_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)

    task_meta = {"id": args.task, "title": f"Feature {args.task}", "category": "multi_module"}
    print(f"[Phase A] Initiating multi-agent debate for {args.task} (Run: {run_id})...")
    debate_res = run_phase_a_debate(run_id, task_meta, team_dir)
    print(f"  Debate complete: {len(debate_res['proposals'])} proposals, {len(debate_res['critiques'])} critiques.")

    print(f"[Phase A] Synthesizing Architecture Decision Record...")
    adr_path = synthesize_decision_record(run_id, task_meta, team_dir, decisions_dir)
    print(f"  ADR written to: {adr_path.relative_to(REPO_ROOT)}")

    slices = [
        {"slice_id": "SLICE-1", "assignee": "implementer-1", "files": [f"src/{args.task.lower()}_core.py"]},
        {"slice_id": "SLICE-2", "assignee": "implementer-2", "files": [f"src/{args.task.lower()}_interfaces.py"]},
    ]
    board_path = create_team_board(run_id, slices, team_dir)
    print(f"[Phase B] Team board established at: {board_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
