# 1D Transient Heat Diffusion with Crank-Nicolson Solver

**Category**: physics_numerics
**Held Out**: True

## Specification
Implement `HeatEquation1D(length: float, alpha: float, nx: int)` in `src/heat_solver.py`.
Solves partial differential equation du/dt = alpha * d^2u/dx^2 on x in [0, length] with zero Dirichlet boundaries.
Uses unconditionally stable Crank-Nicolson implicit finite difference method.
Methods:
- `set_initial_condition(u0: list[float]) -> None`
- `step(dt: float) -> list[float]`: Advances one timestep and returns updated grid values.
- `solve(t_final: float, dt: float) -> list[float]`: Returns solution profile at t_final.
