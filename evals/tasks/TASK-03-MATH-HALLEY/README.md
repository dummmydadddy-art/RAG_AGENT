# Task Specification: Halley's Root Finder with Bracket Fallback

## 1. Function Contract
Implement `find_root_halley` in `src/root_finder.py`.

### Function Signature
```python
def find_root_halley(
    f: Callable[[float], float],
    df: Callable[[float], float],
    d2f: Callable[[float], float],
    x0: float,
    tol: float = 1e-10,
    max_iter: int = 50,
    bracket: Optional[tuple[float, float]] = None
) -> dict[str, Any]:
```

### Parameter Validations
- `tol`: Float > 0.0. If `tol <= 0.0`, raise `ValueError("tol must be positive")`.
- `max_iter`: Integer >= 1. If `max_iter < 1`, raise `ValueError("max_iter must be >= 1")`.
- `bracket`: Optional tuple of two floats `(a, b)`. If provided:
  - Must satisfy `a < b`. If not, raise `ValueError("Invalid bracket: a must be strictly less than b")`.
  - Initial guess `x0` must lie within `[a, b]`. If `x0 < a` or `x0 > b`, raise `ValueError("Initial guess x0 must lie within bracket [a, b]")`.
  - Initial sign condition: `f(a) * f(b)` must be `<= 0.0`. If `f(a) * f(b) > 0`, raise `ValueError("Bracket endpoints must have opposite signs")`.
  - If `f(a) == 0.0`, return immediately: `{"root": a, "iterations": 0, "converged": True, "f_val": 0.0}`.
  - If `f(b) == 0.0`, return immediately: `{"root": b, "iterations": 0, "converged": True, "f_val": 0.0}`.

### Zero-Iteration Check
- Before starting iterations, if `abs(f(x0)) < tol`, return immediately:
  `{"root": x0, "iterations": 0, "converged": True, "f_val": f(x0)}`.

### Numerical Algorithm & Iteration
At iteration `n` (starting at `n = 0` with `x_n = x0`):
1. Compute function and derivatives: $f_n = f(x_n)$, $df_n = df(x_n)$, $d2f_n = d2f(x_n)$.
2. Compute the Halley denominator:
   $$D_n = 2 (df_n)^2 - f_n \cdot d2f_n$$
3. Candidate Halley step:
   $$x_{cand} = x_n - rac{2 f_n \cdot df_n}{D_n}$$
4. Safeguarding & Fallback Logic:
   - **If `bracket = (a, b)` was provided**:
     - Maintain and update the active bracket $(a, b)$ based on the sign of $f(x_n)$: if $f(a) \cdot f(x_n) \le 0$, new bracket is $(a, x_n)$; else $(x_n, b)$.
     - If $|D_n| < 10^{-15}$ OR $x_{cand} \le a$ OR $x_{cand} \ge b$:
       Execute a bisection fallback step:
       $$x_{next} = rac{a + b}{2.0}$$
     - Else:
       $$x_{next} = x_{cand}$$
   - **If `bracket is None`**:
     - If $|D_n| < 10^{-15}$, raise `ZeroDivisionError("Halley denominator vanished and no bracket supplied for bisection fallback")`.
     - Else:
       $$x_{next} = x_{cand}$$
5. Convergence Check:
   - If $|f(x_{next})| < tol$ OR $|x_{next} - x_n| < tol$:
     Return `{"root": x_{next}, "iterations": n + 1, "converged": True, "f_val": f(x_{next})}`.
   - Set $x_{n+1} = x_{next}$.
6. If loop reaches `max_iter` iterations without converging, return:
   `{"root": x_{last}, "iterations": max_iter, "converged": False, "f_val": f(x_{last})}`.
