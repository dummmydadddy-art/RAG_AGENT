# Physics & Mathematics Conduct Rule

This rule enforces rigorous verification for all tasks involving mathematical equations, physical laws, or numerical algorithms.

## 1. Execution, Not Recall
- Parametric recall from language models produces fluent, subtle mathematical errors.
- Never assert a derivation, identity, or convergence order based solely on model memory.
- Every mathematical equivalence, unit consistency check, and numerical boundary condition must be verified by executing `physmath-mcp` tools in a sandbox.

## 2. Mandatory Dimensional Consistency
- Every physical quantity must be declared with its explicit units (e.g. Pint-compatible unit strings: `meter / second`, `pascal`, `kilogram * meter**2 / second**2`).
- Operations combining physical variables must pass `units_check` before code is accepted.

## 3. Invariants & Limiting Cases
- Simulations and numerical solvers must define conserved invariants (e.g. energy, momentum, total probability, mass).
- Solutions must be evaluated at limiting cases (e.g. $t \to 0$, $t \to \infty$, $x \to 0$, symmetric boundary conditions) to ensure asymptotic stability.

## 4. PhysMath Verifier Authority
- The PhysMath Verifier role exercises absolute veto power over pull requests containing mathematical or physical code.
- A feature cannot merge until all PhysMath acceptance tests pass with documented tolerances.
