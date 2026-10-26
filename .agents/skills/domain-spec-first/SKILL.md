---
name: domain-spec-first
description: "Use by the PhysMath Verifier role. Derives acceptance checks and invariants directly from the domain spec before reading any implementation code."
---

# Domain Spec First Skill

## When to Use
Mandatory for the **PhysMath Verifier** role at the beginning of any task involving physics, mathematics, or numerical solvers.

## Core Directives
1. **Spec Independence**:
   - The verifier MUST derive its acceptance tests exclusively from the domain specification and physical principles *before* reading any code or proposed implementation.
   - Author and checker must never share a blind spot.
2. **Acceptance Test Authoring**:
   - Write executable tests under `tests/physmath/`.
   - Include dimensional checks, invariant conservation assertions, and known reference solutions.
3. **Veto Authority**:
   - The verifier exercises absolute veto power.
   - No pull request containing physical or mathematical algorithms can be approved if any `tests/physmath/` test fails.
