from typing import Any, Callable, Optional


def find_root_halley(
    f: Callable[[float], float],
    df: Callable[[float], float],
    d2f: Callable[[float], float],
    x0: float,
    tol: float = 1e-10,
    max_iter: int = 50,
    bracket: Optional[tuple[float, float]] = None,
) -> dict[str, Any]:
    """Finds root of f(x) = 0 using Halley's method with optional bracket-protected bisection fallback."""
    if tol <= 0.0:
        raise ValueError("tol must be positive")
    if max_iter < 1:
        raise ValueError("max_iter must be >= 1")

    a, b = 0.0, 0.0
    if bracket is not None:
        if len(bracket) != 2 or bracket[0] >= bracket[1]:
            raise ValueError("Invalid bracket: a must be strictly less than b")
        a, b = float(bracket[0]), float(bracket[1])
        if x0 < a or x0 > b:
            raise ValueError("Initial guess x0 must lie within bracket [a, b]")

        fa = f(a)
        fb = f(b)
        if fa * fb > 0.0:
            raise ValueError("Bracket endpoints must have opposite signs")

        if fa == 0.0:
            return {"root": a, "iterations": 0, "converged": True, "f_val": 0.0}
        if fb == 0.0:
            return {"root": b, "iterations": 0, "converged": True, "f_val": 0.0}

    # Zero-iteration check
    f_x0 = f(x0)
    if abs(f_x0) < tol:
        return {"root": float(x0), "iterations": 0, "converged": True, "f_val": float(f_x0)}

    x_curr = float(x0)

    for n in range(max_iter):
        f_val = f(x_curr)
        df_val = df(x_curr)
        d2f_val = d2f(x_curr)

        D = 2.0 * (df_val**2) - f_val * d2f_val

        if bracket is not None:
            # Update bracket with current point
            fa = f(a)
            if fa * f_val <= 0.0:
                b = x_curr
            else:
                a = x_curr

            # Safeguard Halley step: fallback to bisection on vanishing denominator,
            # vanishing derivative (extremum), or if candidate falls outside bracket
            if abs(D) < 1e-15 or abs(df_val) < 1e-14:
                x_next = 0.5 * (a + b)
            else:
                x_cand = x_curr - (2.0 * f_val * df_val) / D
                if x_cand <= a or x_cand >= b or abs(x_cand - x_curr) < 1e-15:
                    x_next = 0.5 * (a + b)
                else:
                    x_next = x_cand
        else:
            if abs(D) < 1e-15:
                raise ZeroDivisionError(
                    "Halley denominator vanished and no bracket supplied for bisection fallback"
                )
            x_next = x_curr - (2.0 * f_val * df_val) / D

        f_next = f(x_next)
        # Convergence requires true root convergence
        if abs(f_next) < tol or (abs(x_next - x_curr) < tol and abs(f_next) < 1e-6):
            return {"root": x_next, "iterations": n + 1, "converged": True, "f_val": f_next}

        x_curr = x_next

    return {"root": x_curr, "iterations": max_iter, "converged": False, "f_val": f(x_curr)}
