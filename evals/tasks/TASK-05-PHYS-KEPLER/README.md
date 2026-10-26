# Symplectic Velocity-Verlet Orbital Kepler Integrator

**Category**: physics_numerics
**Held Out**: False

## Specification
Implement `KeplerOrbitSolver(gm: float, r0: tuple[float, float], v0: tuple[float, float])` in `src/kepler_solver.py`.
Simulates 2-body gravitational dynamics d^2r/dt^2 = -GM r / |r|^3 using symplectic Velocity-Verlet.
Methods:
- `step(dt: float) -> None`: Advances position and velocity by dt.
- `compute_energy() -> float`: Returns specific orbital energy E = 0.5 * |v|^2 - GM / |r|.
- `run(total_time: float, dt: float) -> list[tuple[float, float]]`: Runs simulation and returns list of (x, y) positions.
Conserves energy over 1,000 steps with relative error |(E - E0) / E0| < 1e-4.
