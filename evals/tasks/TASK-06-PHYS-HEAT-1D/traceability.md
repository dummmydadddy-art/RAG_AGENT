# Traceability Matrix: TASK-06-PHYS-HEAT-1D

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert solve_heat_1d_crank_nicolson(alpha=-1.0, ...)` raises `ValueError` | "If alpha <= 0.0, raise ValueError(\"alpha must be positive\")" |
| `assert solve_heat_1d_crank_nicolson(alpha=1.0, length=0.0, ...)` raises `ValueError` | "If length <= 0.0, raise ValueError(\"length must be positive\")" |
| `assert solve_heat_1d_crank_nicolson(..., nx=2)` raises `ValueError` | "If nx < 3, raise ValueError(\"nx must be at least 3\")" |
| `assert solve_heat_1d_crank_nicolson(..., dt=0.0)` raises `ValueError` | "If dt <= 0.0, raise ValueError(\"dt must be positive\")" |
| Boundary nodes $u[0] == 0.0$ and $u[-1] == 0.0$ | "Homogeneous Dirichlet boundaries u(0, t) = 0.0 and u(length, t) = 0.0 are enforced for all time steps." |
| Analytical fundamental mode decay $e^{-\alpha (\pi / L)^2 t}$ matches within $10^{-3}$ | "Solves du/dt = alpha d2u/dx2 using the unconditionally stable second-order Crank-Nicolson scheme." |
| Thermal energy non-negative and maximum temperature decays monotonically | "Maximum principle for the heat equation" |
