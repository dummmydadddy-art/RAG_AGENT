# Task Specification: 2D Kepler Orbit Symplectic Integrator

## 1. Function Contract
Implement `solve_kepler_orbit` in `src/kepler_solver.py`.

### Function Signature
```python
def solve_kepler_orbit(
    r0: tuple[float, float],
    v0: tuple[float, float],
    gm: float,
    dt: float,
    steps: int
) -> dict[str, Any]:
```

### Parameter Validations
- `r0`: 2D initial position tuple `(x0, y0)`. Must be a tuple/list of length 2. If not, raise `ValueError("Initial conditions must be 2D vectors")`.
- `v0`: 2D initial velocity tuple `(vx0, vy0)`. Must be a tuple/list of length 2. If not, raise `ValueError("Initial conditions must be 2D vectors")`.
- Initial radius magnitude $\|r_0\| = \sqrt{x_0^2 + y_0^2}$: If $\|r_0\| < 10^{-12}$, raise `ValueError("Initial radius cannot be zero")`.
- `gm`: Standard gravitational parameter $G \cdot M$. Must be a float > 0.0. If `gm <= 0.0`, raise `ValueError("GM parameter must be positive")`.
- `dt`: Simulation timestep in seconds. Must be a float > 0.0. If `dt <= 0.0`, raise `ValueError("Time step dt must be positive")`.
- `steps`: Total integration steps. Must be an integer >= 1. If `steps < 1`, raise `ValueError("Steps must be at least 1")`.

### Symplectic Integration Scheme
The solver must integrate the Newtonian 2D two-body gravitational dynamics:
$$\mathbf{a}(\mathbf{r}) = -rac{GM}{\|\mathbf{r}\|^3} \mathbf{r}$$
using the **Velocity Verlet (symplectic)** numerical integration scheme:
1. $\mathbf{a}_n = \mathbf{a}(\mathbf{r}_n)$
2. $\mathbf{r}_{n+1} = \mathbf{r}_n + \mathbf{v}_n dt + rac{1}{2} \mathbf{a}_n dt^2$
3. $\mathbf{a}_{n+1} = \mathbf{a}(\mathbf{r}_{n+1})$
4. $\mathbf{v}_{n+1} = \mathbf{v}_n + rac{1}{2} (\mathbf{a}_n + \mathbf{a}_{n+1}) dt$

### Physical Invariants & Diagnostics
At every step $n \in \{0, 1, \dots, steps\}$:
1. **Specific Mechanical Energy**:
   $$E_n = rac{1}{2} \|\mathbf{v}_n\|^2 - rac{GM}{\|\mathbf{r}_n\|}$$
2. **Specific Angular Momentum** (z-component):
   $$L_{z, n} = x_n v_{y, n} - y_n v_{x, n}$$
3. For bound Keplerian orbits, the relative variations $rac{|E_n - E_0|}{|E_0|}$ and $rac{|L_{z, n} - L_{z, 0}|}{|L_{z, 0}|}$ must remain bounded within $10^{-4}$ over 10 complete orbits.

### Return Dictionary Specification
Returns a dictionary containing exactly:
- `"position"`: `list[tuple[float, float]]` of length `steps + 1`.
- `"velocity"`: `list[tuple[float, float]]` of length `steps + 1`.
- `"energy"`: `list[float]` of length `steps + 1`.
- `"angular_momentum"`: `list[float]` of length `steps + 1`.
- `"time"`: `list[float]` of length `steps + 1` where $t_n = n \cdot dt$.
