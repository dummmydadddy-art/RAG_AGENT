# Task Specification: 2D Reaction-Diffusion Gray-Scott Pattern Simulator

## 1. Function Contract
Implement `simulate_gray_scott_2d` in `src/gray_scott.py`.

### Function Signature
```python
def simulate_gray_scott_2d(
    width: int,
    height: int,
    Du: float = 0.16,
    Dv: float = 0.08,
    feed: float = 0.035,
    kill: float = 0.060,
    dt: float = 1.0,
    steps: int = 100,
    initial_u: Optional[np.ndarray] = None,
    initial_v: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray]:
```
- Discretizes coupled reaction-diffusion equations:
  $\partial u / \partial t = D_u \nabla^2 u - u v^2 + F(1 - u)$
  $\partial v / \partial t = D_v \nabla^2 v + u v^2 - (F + k) v$
  using 5-point discrete Laplacian with periodic toroidal boundary conditions.
- Returns final state concentration grids `(U, V)` where each array has shape `(height, width)`.
- Enforces concentration boundedness: $U, V \in [0.0, 1.0]$.
