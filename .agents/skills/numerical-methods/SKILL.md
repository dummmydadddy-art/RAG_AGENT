---
name: numerical-methods
description: "Use when implementing discretisation, solvers, or numerical integration. Covers stability, order of accuracy, tolerances, and floating point pitfalls."
---

# Numerical Methods Skill

## When to Use
Invoke this skill when implementing numerical solvers (ODEs, PDEs, linear algebra solvers, root finders, quadrature).

## Invariants & Principles
1. **Numerical Stability**:
   - Check CFL condition ($\Delta t \le C \Delta x / u$) for hyperbolic equations.
   - For stiff systems, prefer implicit or A-stable solvers.
   - For Hamiltonian systems, use symplectic integrators (Verlet, leapfrog).
2. **Order of Accuracy & Convergence**:
   - Verify observed order of accuracy under grid/timestep refinement:
     $$p \approx \frac{\log(E_{2h} / E_h)}{\log(2)}$$
3. **Floating Point Safety**:
   - Guard against catastrophic cancellation ($x - y$ when $x \approx y$).
   - Avoid division by zero with safe clamping $\max(|x|, \epsilon)$.
   - Use `numeric_compare(func1, func2, domain, tol_rel, tol_abs)` to benchmark against analytical or high-precision references.
