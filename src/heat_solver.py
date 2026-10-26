from typing import Any, Callable


def solve_heat_1d_crank_nicolson(
    alpha: float,
    length: float,
    nx: int,
    t_final: float,
    dt: float,
    u0_fn: Callable[[float], float],
) -> dict[str, Any]:
    """Solves 1D transient heat equation with Dirichlet boundaries using Crank-Nicolson and Thomas algorithm."""
    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    if length <= 0.0:
        raise ValueError("length must be positive")
    if nx < 3:
        raise ValueError("nx must be at least 3")
    if t_final <= 0.0:
        raise ValueError("t_final must be positive")
    if dt <= 0.0:
        raise ValueError("dt must be positive")

    dx = length / (nx - 1)
    x = [i * dx for i in range(nx)]

    nt = max(1, round(t_final / dt))
    t_reached = round(nt * dt, 10)

    # Initial condition
    u = [float(u0_fn(xi)) for xi in x]
    # Enforce boundary condition at t = 0
    u[0] = 0.0
    u[-1] = 0.0

    r = (alpha * dt) / (2.0 * (dx**2))
    m = nx - 2  # number of interior nodes

    # Tridiagonal system coefficients for interior nodes (index 1 to nx-2)
    # A * u^{n+1} = B * u^n
    # -r * u_{i-1} + (1 + 2r) * u_i - r * u_{i+1}
    for _ in range(nt):
        # Construct RHS vector d for interior points
        d = [0.0] * m
        for k in range(m):
            i = k + 1
            d[k] = r * u[i - 1] + (1.0 - 2.0 * r) * u[i] + r * u[i + 1]

        # Thomas algorithm forward sweep
        c_prime = [0.0] * m
        d_prime = [0.0] * m

        # k = 0
        b0 = 1.0 + 2.0 * r
        c_prime[0] = -r / b0
        d_prime[0] = d[0] / b0

        for k in range(1, m):
            ak = -r
            bk = 1.0 + 2.0 * r
            ck = -r if k < m - 1 else 0.0
            denom = bk - ak * c_prime[k - 1]
            if k < m - 1:
                c_prime[k] = ck / denom
            d_prime[k] = (d[k] - ak * d_prime[k - 1]) / denom

        # Back substitution
        u_interior = [0.0] * m
        u_interior[-1] = d_prime[-1]
        for k in range(m - 2, -1, -1):
            u_interior[k] = d_prime[k] - c_prime[k] * u_interior[k + 1]

        # Update full array with boundaries
        u[0] = 0.0
        for k in range(m):
            u[k + 1] = u_interior[k]
        u[-1] = 0.0

    return {
        "x": x,
        "u": u,
        "time": t_reached,
        "max_temp": max(u),
    }
