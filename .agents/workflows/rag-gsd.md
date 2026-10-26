# RAG-GSD Autonomous Workflow (/rag-gsd)

<purpose>
Executes focused, test-first feature delivery through a single lead orchestrator and specialized subagents.
Triggered by `/rag-gsd <feature>` to avoid ambiguity with global gsd-core commands.
Follows the 9-step lifecycle defined in Section 6.4 of ARCHITECTURE.md.
</purpose>

<arguments>
$ARGUMENTS: The feature description, task ID, or implementation objective.
</arguments>

<process>

## Step 1: Intake & Scope Definition
- Restate the user objective and acceptance criteria explicitly.
- Identify all assumptions. If an essential fact blocks progress, ask immediately; otherwise record assumption and proceed.
- Determine task category: `pure_coding`, `pure_maths`, `physics_numerics`, `multi_module`, `retrieval_dependent`.
- Record task start time for trace.

## Step 2: Retrieve from Knowledge & Lessons
- Invoke skill `rag-retrieval`.
- Call `rag_search` on the `knowledge` collection with a query derived from the task description.
- Call `rag_search` on the `lessons` collection for prior experience.
- Extract up to 5 verified or candidate lessons.
- Note retrieved lesson IDs for citation in the plan.
- If retrieval returns zero results, state explicitly: "No prior lessons or knowledge found for this task."

## Step 3: Plan Formulation
- Invoke skill `plan-and-tasks`.
- Produce implementation plan artifact `PLAN.md` in the project root.
- Explicitly cite all retrieved lesson IDs from Step 2.
- Slice tasks into non-overlapping scopes with automated test pairings.
- Assign Risk Score: Low | Medium | High per task slice.
- **Escalation Triggers** (report only; /team does not exist yet):
  - Multi-module: if 3+ modules are modified.
  - Spec ambiguity: if 2+ interpretation choices remain unresolvable from the spec alone.
  - Physics invariant: if dimensional analysis or conservation law check fails during planning.

## Step 4: Domain Specification & PhysMath Verification
- If task category is `pure_maths`, `physics_numerics`, or `retrieval_dependent`:
  - Invoke skill `domain-spec-first`: write the domain specification with exact equations, conventions, boundary conditions, and units.
  - Invoke skill `physics-conduct`: verify dimensional consistency via `units_check`.
  - The `physmath-verifier` role derives acceptance checks from the spec BEFORE seeing any implementation code.
  - These checks are written to `tests/physmath/` or embedded in the hidden evaluation contract.
- If task category is `pure_coding` or `multi_module`:
  - Skip physmath verification but still write domain spec if the task involves non-trivial algorithms.

## Step 5: Test-Driven Implementation (TDD Loop)
- Invoke skill `tdd-loop` for each task slice in `PLAN.md`.
- For each slice:
  1. **Red**: Write a failing pytest test capturing the spec requirement.
  2. **Green**: Write minimal production code in `src/` to make the test pass.
  3. **Refactor**: Clean up code while keeping tests green.
- Cap iterations at 5 per task slice (from `budgets.yaml`).
- **Escalation Trigger**: If a task fails 3 consecutive TDD cycles with the same root cause, halt and report:
  `[ESCALATION TRIGGER: Task failure threshold reached (3 consecutive failures on same error).]`

## Step 6: Full Verification Pass
- Run the complete test suite: `python -m pytest -v`.
- For physics/numerics tasks:
  - Run `units_check` on all physical equations.
  - Run `numeric_compare` on analytical vs numerical solutions.
  - Run `sym_equiv` on any symbolic identities.
- Verify no regressions: all pre-existing tests must still pass.
- Verify target implementation file exists and contains expected exports.

## Step 7: Independent Code Review
- Delegate to the `reviewer` role per skill `code-review`.
- Pass the following in the reviewer's prompt context:
  - The git diff (`git diff HEAD~1`).
  - The pytest output from Step 6.
  - The task spec from `evals/tasks/<id>/README.md`.
- Reviewer checks:
  - Correctness against spec contract.
  - Edge case and error handling coverage.
  - Protected path violations (`.agents/**`, `GEMINI.md`, `evals/**`).
  - Thread safety (for concurrent code).
  - Naming conventions and docstrings.
- Address every MUST-FIX finding before proceeding. Document SHOULD-FIX items.

## Step 8: Distill Trace & Candidate Lessons
- Write execution trace as a structured record:
  ```json
  {
    "task_id": "<id>",
    "timestamp": "<ISO 8601>",
    "wall_time_seconds": <float>,
    "tdd_iterations": <int>,
    "retrieved_lesson_ids": ["<id1>", "<id2>"],
    "retrieval_mode": "<mode>",
    "status": "PASS | FAIL",
    "escalation_triggers": [],
    "category": "<category>",
    "held_out": <bool>
  }
  ```
- If novel reusable knowledge emerged from a passing run:
  - Format candidate lesson: `When <situation>, do <action>, because <reason>`.
  - Report to orchestrator for Phase 2 librarian storage (do NOT write lessons directly in Phase 1).

## Step 9: Final Report & Commit
- Create a concise completion report summarizing:
  - Task objective, approach taken, files changed, test results, review findings.
  - Any escalation triggers encountered and their resolution.
- Stage all changes and commit to the feature branch with Conventional Commits format:
  - `feat: <description>` for new features.
  - `fix: <description>` for bug fixes.
  - `test: <description>` for test additions.
- Never push directly to `main`.
- Never modify `.agents/**`, `GEMINI.md`, `AGENTS.md`, or `evals/**` without explicit human authorization.

</process>

<escalation_summary>
The following triggers are detected and reported but NOT acted upon (the /team mode does not exist yet):
1. **Multi-module threshold**: 3+ source modules touched in one task.
2. **Consecutive TDD failure**: 3 failures on the same root cause.
3. **Physics invariant violation**: Dimensional analysis or conservation law check failure.
4. **Spec ambiguity**: 2+ unresolvable interpretation choices.
</escalation_summary>
