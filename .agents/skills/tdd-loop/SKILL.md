---
name: tdd-loop
description: "Use when implementing any task. Enforces Red-Green-Refactor cycles, iteration caps, and definition of done."
---

# TDD Loop Skill

## When to Use
Invoke this skill during task execution when writing or modifying code.

## Execution Cycle
1. **Red Phase (Test First)**:
   - Author a new test file in `tests/unit/`, `tests/integration/`, or `tests/contract/`.
   - Assert the expected interface, return types, or mathematical behavior.
   - Run `pytest` to confirm the test fails for the expected reason (red).
2. **Green Phase (Minimal Implementation)**:
   - Write the simplest production code that satisfies the test assertion.
   - Run `pytest` to confirm the test passes cleanly (green).
3. **Refactor Phase**:
   - Clean up code structure, enforce PEP 8 and type hints.
   - Re-run all tests to guarantee zero regressions.

## Rules & Invariants
- Never skip, disable, or comment out failing tests.
- Maximum 4 retry iterations per task. If a task fails twice with the same root cause, stop and document the blocker.
- Code is not "Done" until all tests pass and linting is clean.
