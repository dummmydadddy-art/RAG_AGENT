# Traceability Matrix: TASK-05-PHYS-KEPLER

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert solve_kepler_orbit((0, 0), (1, 0), gm=1.0, dt=0.01, steps=10)` raises `ValueError` | "If ||r0|| < 1e-12, raise ValueError(\"Initial radius cannot be zero\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=-1.0, dt=0.01, steps=10)` raises `ValueError` | "If gm <= 0.0, raise ValueError(\"GM parameter must be positive\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=1.0, dt=-0.1, steps=10)` raises `ValueError` | "If dt <= 0.0, raise ValueError(\"Time step dt must be positive\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=1.0, dt=0.01, steps=0)` raises `ValueError` | "If steps < 1, raise ValueError(\"Steps must be at least 1\")" |
| Circular orbit circularity $\|r_n\| pprox 1.0$ | "using the Velocity Verlet (symplectic) numerical integration scheme" |
| Angular momentum conservation $\Delta L / L_0 < 1e-7$ | "the relative variations ... must remain bounded within 1e-4" |
| Specific energy conservation $\Delta E / E_0 < 1e-4$ | "the relative variations |E_n - E_0| / |E_0| ... must remain bounded within 1e-4" |
| All output list lengths equal `steps + 1` | "Returns a dictionary containing exactly: position ... of length steps + 1" |
