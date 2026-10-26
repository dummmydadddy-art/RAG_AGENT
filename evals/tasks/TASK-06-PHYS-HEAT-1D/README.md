# Task Specification: 1D Transient Heat Conduction via Crank-Nicolson

## 1. Function Contract
Implement `solve_heat_1d_crank_nicolson` in `src/heat_solver.py`.

### Function Signature
```python
def solve_heat_1d_crank_nicolson(
    alpha: float,
    length: float,
    nx: int,
    t_final: float,
    dt: float,
    u0_fn: Callable[[float], float]
) -> dict[str, Any]:
```

### Parameter Validations
- `alpha`: Thermal diffusivity coefficient. Must be float > 0.0. If `alpha <= 0.0`, raise `ValueError("alpha must be positive")`.
- `length`: Domain length $L$ in meters. Must be float > 0.0. If `length <= 0.0`, raise `ValueError("length must be positive")`.
- `nx`: Number of spatial grid points. Must be integer >= 3. If `nx < 3`, raise `ValueError("nx must be at least 3")`.
- `t_final`: Simulation duration in seconds. Must be float > 0.0. If `t_final <= 0.0`, raise `ValueError("t_final must be positive")`.
- `dt`: Time step in seconds. Must be float > 0.0. If `dt <= 0.0`, raise `ValueError("dt must be positive")`.

### Spatial & Temporal Discretization
1. Spatial grid spacing: $\Delta x = rac{length}{nx - 1}$.
   Grid points: $x_i = i \cdot \Delta x$ for $i \in \{0, 1, \dots, nx - 1\}$.
2. Number of time steps: $N_t = \max(1, 	ext{round}(t_{final} / dt))$.
   Actual reached simulated time: $t_{reached} = N_t \cdot dt$.
3. Initial condition: $u^0(x_i) = u0\_fn(x_i)$.
4. Boundary condition enforcement: Homogeneous Dirichlet boundaries $u(0, t) = 0.0$ and $u(length, t) = 0.0$ are enforced for all time steps. Specifically, $u^n_0 = 0.0$ and $u^n_{nx-1} = 0.0$ for all $n \ge 0$.

### Crank-Nicolson Linear System
Solves $\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}$ using the unconditionally stable second-order Crank-Nicolson scheme.
For interior nodes $i \in \{1, \dots, nx - 2\}$:
Let $r = \frac{\alpha \Delta t}{2 (\Delta x)^2}$.
$$-r u^{n+1}_{i-1} + (1 + 2r) u^{n+1}_i - r u^{n+1}_{i+1} = r u^n_{i-1} + (1 - 2r) u^n_i + r u^n_{i+1}$$
This tridiagonal system must be solved efficiently at each time step using the Thomas algorithm (tridiagonal matrix algorithm) in $O(nx)$ operations without computing full matrix inverses.

### Return Dictionary Specification
Returns a dictionary containing:
- `"x"`: `list[float]` of spatial grid coordinates of length `nx`.
- `"u"`: `list[float]` of temperature values at $t = t_{reached}$ of length `nx`.
- `"time"`: `float` $t_{reached}$.
- `"max_temp"`: `float` $\max(u)$ at final time.
