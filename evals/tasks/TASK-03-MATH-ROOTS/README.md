# High-Precision Halley's Method Root Finder with Bracket Fallback

**Category**: maths
**Held Out**: False

## Specification
Implement `find_root(f, df, d2f, x0, tol=1e-12, max_iter=50)` in `src/root_finder.py`.
Uses Halley's iteration formula:
x_{n+1} = x_n - [2 * f(x_n) * f'(x_n)] / [2 * (f'(x_n))^2 - f(x_n) * f''(x_n)]
Returns dataclass `RootResult(root: float, iterations: int, converged: bool, residual: float)`.
Must converge for cubic polynomial x^3 - x - 2 = 0 to within 1e-11 in <= 15 iterations.
