# Collaborative Team Workflow (/team)

<purpose>
Executes multi-agent collaborative delivery with an independent debate phase (Architect, PhysMath Verifier, Adversarial Tester), synchronized non-overlapping slice implementation, and adversarial validation.
Triggered by `/team <feature>` or automatically on escalation from `/rag-gsd`.
Follows the 4-phase lifecycle defined in Section 6.4 of ARCHITECTURE.md.
</purpose>

<arguments>
$ARGUMENTS: The complex feature description, architecture objective, or escalated task.
</arguments>

<process>

## Phase A: Independent Multi-Agent Debate
1. **Intake & Run Initialization**:
   - Assign unique run identifier: `<run-id>` (e.g. `team-YYYYMMDD-HHMMSS`).
   - Create directory structure: `team/<run-id>/proposals/`, `team/<run-id>/critiques/`.
   - Call `rag_search` across `knowledge` and `lessons` collections.
2. **Parallel Proposals Generation**:
   - Spawn three independent roles in parallel with disjoint viewpoints:
     - **`architect`**: Proposes modular decomposition, class boundaries, concurrency patterns, and tradeoff analysis in `team/<run-id>/proposals/architect.md`.
     - **`physmath-verifier`**: Derives physical invariants, dimensional bounds, conservation laws, and mathematical acceptance checks in `team/<run-id>/proposals/physmath-verifier.md`.
     - **`adversarial-tester`**: Identifies failure modes, boundary discontinuities, race conditions, and property-based test specifications in `team/<run-id>/proposals/adversarial-tester.md`.
3. **Critique Round (Max 2 Rounds)**:
   - Each role reads the proposals of the other two roles.
   - Each role writes a structured critique and rebuttal into `team/<run-id>/critiques/<role>.md`.
   - Budget guard: Strictly capped at 2 debate rounds per `budgets.yaml`.
4. **Architecture Decision Record (ADR) Synthesis**:
   - The orchestrator synthesizes the proposals and critiques into a binding ADR: `decisions/<run-id>.md`.
   - ADR contains: Context, Considered Alternatives, Decision, Invariants & Acceptance Gates, and Non-Overlapping File Scope Allocations.

## Phase B: Synchronized Slices & Parallel Build
1. **Board Creation**:
   - Create `team/<run-id>/board.md` tracking task slices, assignees, file scopes, and lifecycle status (`BACKLOG`, `IN_PROGRESS`, `IN_REVIEW`, `VERIFIED`).
2. **Disjoint Scope Partitioning**:
   - Partition implementation into up to 3 non-overlapping file scopes (e.g., `src/module_a/`, `src/module_b/`, `src/interfaces/`).
   - Inviolable constraint: Two implementers must never edit the same file.
3. **Parallel Implementer Execution**:
   - Spawn up to 3 implementers concurrently in isolated git worktrees.
   - Each implementer follows strict TDD (Red -> Green -> Refactor) exclusively within its assigned file scope.

## Phase C: Staged Integration & Verification
1. **Sequential Branch Integration**:
   - Merge implementer branches/worktrees one at a time into the team integration branch.
   - Resolve any non-content conflicts immediately; if structural conflict occurs, halt and invoke architect.
2. **Continuous Verification Gates**:
   - After each merge, execute the full test suite (`pytest`).
   - Run executable PhysMath tools (`units_check`, `sym_equiv`, `numeric_compare`, `invariant_check`, `convergence_study`, `limit_check`).
   - Execute adversarial test suite from `tests/adversarial/`.

## Phase D: Adversarial Review & Learning
1. **Adversarial & Verifier Review**:
   - `adversarial-tester` runs full edge-case stress suites. If an invariant breaks, reopen the task on `board.md`.
   - `physmath-verifier` checks that all derived mathematical checks pass with zero residual error.
   - `reviewer` validates diff against safety boundaries and coding standards.
2. **Librarian Distillation**:
   - `librarian` distills passing run insights into candidate lessons formatted as: `When <situation>, do <action>, because <reason>`.
   - Verifies duplicate detection and contradiction checks against existing verified lessons.
   - Writes execution trace to `team/<run-id>/trace.json`.
3. **Synthesis & Commit**:
   - Author final completion report artifact.
   - Commit cleanly with Conventional Commits to feature branch.

</process>

<invariants>
1. **No Direct Peer Messaging**: Antigravity subagents operate in isolated contexts; all coordination is mediated via files (`team/<run-id>/board.md`, `proposals/`, `critiques/`, `decisions/`).
2. **Non-Overlapping File Scopes**: Parallel implementers operate strictly within disjoint file paths.
3. **Strict Debate Cap**: Debate rounds cannot exceed 2 rounds.
4. **PhysMath Veto Authority**: Any failing physical or numerical invariant vetoes merge.
</invariants>
