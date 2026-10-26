# RAG-GSD Autonomous Workflow (/rag-gsd)

<purpose>
Executes focused, test-first feature delivery through a single lead orchestrator and specialized subagents.
Triggered by `/rag-gsd <feature>` to avoid ambiguity with global gsd-core commands.
Follows the 9-step lifecycle defined in Section 6.4 of ARCHITECTURE.md.
</purpose>

<process>

## Step 1: Intake & Scope Definition
- Restate the user objective and acceptance criteria explicitly.
- Identify all assumptions. If an essential fact blocks progress, ask immediately; otherwise record assumption and proceed.

## Step 2: Retrieve from Knowledge & Lessons
- Invoke skill `rag-retrieval`.
- Call `rag_search(query=$QUERY, collections=["knowledge", "lessons"], k=5)`.
- Extract up to 5 verified or candidate lessons.
- Note retrieved lesson IDs for citation.

## Step 3: Plan Formulation
- Invoke skill `plan-and-tasks`.
- Produce implementation plan artifact `PLAN.md`.
- Explicitly cite retrieved lesson IDs.
- Slice tasks into non-overlapping scopes with automated test pairings.
- Assign Risk Score: Low | Medium | High.
- **Escalation Check**: If 3+ modules are modified, flag escalation trigger: `[ESCALATION TRIGGER: Multi-module feature (>2 modules touched). Recommend /team mode in Phase 3.]`

## Step 4: Domain Specification & PhysMath Verification
- If task touches mathematical equations, physical quantities, or numerical algorithms:
  - The `physmath-verifier` derives acceptance tests in `tests/physmath/` BEFORE implementation code is written.
  - Verifies dimensional consistency using `units_check`.

## Step 5: Test-Driven Implementation (TDD Loop)
- For each task slice in `PLAN.md`:
  - Execute Red-Green-Refactor cycle per skill `tdd-loop`.
  - Cap iterations at 4 per task (from `budgets.yaml`).
  - If a task fails twice with same error, flag escalation trigger: `[ESCALATION TRIGGER: Task failure threshold reached (2 failures).]`

## Step 6: Full Verification Pass
- Run complete test suite (`pytest`).
- Run `physmath-mcp` tools on all symbolic and numerical algorithms.
- Run `scripts/doctor.ps1` to ensure all system health gates pass.

## Step 7: Independent Code Review
- Delegate diff to `reviewer` agent per skill `code-review`.
- Reviewer checks against `PLAN.md`, testing invariants, and safety boundaries (`.agents/**`, `GEMINI.md`, `evals/**`).
- Address or document every finding before proceeding.

## Step 8: Distill Trace & Candidate Lessons
- Write execution trace to `traces/` or log artifact capturing:
  - Task ID, wall time, iterations, retrieved lesson IDs, and retrieval mode.
- If novel reusable knowledge emerged from a passing run:
  - Format candidate lesson: `When <situation>, do <action>, because <reason>`.
  - Store as `status: candidate`.

## Step 9: Final Report Artifact & PR Branch
- Create comprehensive walkthrough and completion report artifact.
- Stage changes and commit cleanly to feature branch with Conventional Commits.
- Never push directly to `main`.
</process>
