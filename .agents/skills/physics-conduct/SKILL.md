---
name: physics-conduct
description: "Use on any task touching physical quantities. Enforces explicit Pint units, conservation laws, limiting cases, and sanity ranges."
---

# Physics Conduct Skill

## When to Use
Invoke this skill whenever implementing or verifying algorithms involving physical dimensions, forces, energies, fluids, or kinematics.

## Invariants
1. **Explicit Units Declaration**:
   - Every physical variable must declare its Pint-compatible units.
   - Run `units_check(expression, symbol_units, target_unit)` before accepting calculations.
2. **Conservation Laws**:
   - Quantify conserved invariants (e.g. total mass, mechanical energy $E = T + V$, linear/angular momentum).
   - In numerical simulations, test that conserved quantities drift within expected numerical tolerance $\Delta E \le \epsilon$.
3. **Limiting Cases**:
   - Check asymptotic behavior at boundary limits: $t \to 0$, $t \to \infty$, $m \to 0$, $v \to 0$.
4. **Tool Execution over Recall**:
   - Never derive physical identities from LLM parametric memory. Always verify via `physmath-mcp`.
