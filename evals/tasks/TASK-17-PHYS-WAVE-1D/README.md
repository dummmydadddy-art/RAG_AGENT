# Task Specification: 1D Acoustic Wave PDE Solver with Absorbing Boundaries

## 1. Function Contract
Implement `solve_wave_1d` in `src/wave_solver.py`.

### Function Signature
```python
def solve_wave_1d(
    c: float,
    length: float,
    t_max: float,
    nx: int,
    cfl: float = 0.5,
    initial_u: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    initial_v: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    absorbing: bool = True
) -> Dict[str, np.ndarray]:
```
- Discretizes 1D wave equation $\frac{\partial^2 u}{\partial t^2} = c^2 \frac{\partial^2 u}{\partial x^2}$ using 2nd-order leapfrog finite difference.
- Grid spacing $\Delta x = \text{length} / (nx - 1)$, time step $\Delta t = \text{cfl} \cdot \Delta x / c$.
- When `absorbing=True`, applies 1st-order Mur absorbing boundary condition: $\frac{\partial u}{\partial t} \pm c \frac{\partial u}{\partial x} = 0$.
- Returns `{"x": x_grid, "t": t_grid, "u": u_grid}` where `u_grid` has shape `(nt, nx)`.
