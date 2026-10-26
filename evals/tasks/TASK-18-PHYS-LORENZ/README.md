# Task Specification: Lorenz Attractor Simulation and Lyapunov Exponent Estimation

## 1. Class & Method Contract
Implement `LorenzSystem` in `src/lorenz_system.py`.

### Constructor Signature
```python
def __init__(self, sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0 / 3.0) -> None:
```

### Methods
1. `simulate(self, state0: Tuple[float, float, float], dt: float, steps: int) -> Tuple[np.ndarray, np.ndarray]`:
   - Integrates $\dot{x} = \sigma(y - x), \dot{y} = x(\rho - z) - y, \dot{z} = x y - \beta z$ via RK4.
   - Returns `(t, trajectory)` where `trajectory` has shape `(steps + 1, 3)`.
2. `estimate_maximal_lyapunov(self, state0: Tuple[float, float, float], dt: float = 0.01, steps: int = 5000, d0: float = 1e-8) -> float`:
   - Estimates largest Lyapunov exponent $\lambda$ by tracking divergence of two nearby trajectories with periodic renormalization.
   - At standard parameters, $\lambda \in [0.75, 1.15]$.
