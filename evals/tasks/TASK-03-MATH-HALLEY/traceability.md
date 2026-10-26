# Traceability Matrix: TASK-03-MATH-HALLEY

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert find_root_halley(..., tol=0.0)` raises `ValueError` | "If tol <= 0.0, raise ValueError(\"tol must be positive\")" |
| `assert find_root_halley(..., bracket=(2, 1))` raises `ValueError` | "Must satisfy a < b. If not, raise ValueError(\"Invalid bracket: a must be strictly less than b\")" |
| `assert find_root_halley(..., bracket=(0, 2), x0=5.0)` raises `ValueError` | "Initial guess x0 must lie within [a, b]. If x0 < a or x0 > b, raise ValueError(\"Initial guess x0 must lie within bracket [a, b]\")" |
| `assert find_root_halley(..., bracket=(1, 3))` on $f(x)=x^2+1$ raises `ValueError` | "If f(a) * f(b) > 0, raise ValueError(\"Bracket endpoints must have opposite signs\")" |
| Smooth cubic root found in $\le 5$ iterations | "Candidate Halley step: $x_{cand} = x_n - 2 f df / D_n$" (cubic convergence rate) |
| Halley denominator vanishing with bracket triggers bisection step | "If |D_n| < 1e-15 or x_cand outside (a, b): Execute a bisection fallback step: x_next = (a + b) / 2.0" |
| Halley denominator vanishing without bracket raises `ZeroDivisionError` | "If |D_n| < 1e-15, raise ZeroDivisionError(\"Halley denominator vanished and no bracket supplied for bisection fallback\")" |
| Initial root hit $f(x0) == 0$ returns 0 iterations | "Before starting iterations, if abs(f(x0)) < tol, return immediately: iterations: 0" |
