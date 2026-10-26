# Symplectic Stormer-Verlet Integrator citing Knowledge Base

**Category**: retrieval_knowledge
**Held Out**: False

## Specification
Retrieve formulation from knowledge collection (ID: K-2026-PHYS-001).
Implement `StormerVerletIntegrator(force_fn: Callable[[float], float], dt: float, q0: float, v0: float)` in `src/stormer_verlet.py`.
Methods:
- `step() -> float`: Computes next position q_{n+1} and advances state.
- `get_state() -> tuple[float, float]`: Returns current (q, p).
Must cite `K-2026-PHYS-001` in the class docstring.
