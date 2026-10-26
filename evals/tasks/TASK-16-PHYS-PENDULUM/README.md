# Task Specification: Double Pendulum Chaotic Dynamics via Runge-Kutta RK4

## 1. Class & Method Contract
Implement `DoublePendulum` in `src/double_pendulum.py`.

### Constructor Signature
```python
def __init__(
    self,
    l1: float = 1.0,
    l2: float = 1.0,
    m1: float = 1.0,
    m2: float = 1.0,
    g: float = 9.81
) -> None:
```
Parameters must be strictly positive floats. If any `<= 0`, raise `ValueError("Lengths, masses and gravity must be positive")`.

### Method: `simulate(self, theta1: float, omega1: float, theta2: float, omega2: float, dt: float, steps: int) -> Dict[str, Any]`
- Solves coupled nonlinear Lagrangian equations of motion using 4th-order Runge-Kutta (RK4).
- Returns dictionary containing:
  - `"t"`: NumPy array of time points `[0, dt, 2*dt, ..., steps*dt]`.
  - `"theta1"`, `"omega1"`, `"theta2"`, `"omega2"`: NumPy arrays of trajectories.
  - `"energy"`: NumPy array of total mechanical energy $E(t) = T(t) + V(t)$.
  - Energy drift $|E(t) - E(0)| / |E(0)|$ must remain $\le 10^{-3}$ over small amplitudes.
