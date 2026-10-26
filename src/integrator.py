from typing import Any, Callable


def solve_stormer_verlet(
    q0: float,
    p0: float,
    dV_dq_fn: Callable[[float], float],
    dt: float,
    steps: int,
) -> dict[str, Any]:
    """
    Symplectic Störmer-Verlet numerical integrator for separable Hamiltonian systems H(q, p) = 1/2 p^2 + V(q).

    Conventions retrieved from project knowledge entry:
    - Coordinate: q, conjugate momentum: p (unit mass m = 1).
    - Recursion: q_{n+1} = 2*q_n - q_{n-1} - dt^2 * dV/dq(q_n)
    - Startup step: q_1 = q_0 + dt*p_0 - 0.5*dt^2 * dV/dq(q_0)
    - Momentum recovery:
        p_0 = p_0 (exact initial condition)
        p_n = (q_{n+1} - q_{n-1}) / (2*dt) for interior points
        p_{steps} = (q_{steps} - q_{steps-1}) / dt - 0.5*dt * dV/dq(q_{steps})
    """
    if dt <= 0.0:
        raise ValueError("Time step dt must be positive")
    if steps < 1:
        raise ValueError("Steps must be at least 1")

    q = [float(q0)] * (steps + 1)
    p = [float(p0)] * (steps + 1)
    time = [round(n * dt, 10) for n in range(steps + 1)]

    # 1. Compute startup step q1
    f0 = float(dV_dq_fn(q[0]))
    q[1] = q[0] + dt * p[0] - 0.5 * (dt**2) * f0

    # 2. Coordinate recurrence for q_{n+1}
    for n in range(1, steps):
        fn = float(dV_dq_fn(q[n]))
        q[n + 1] = 2.0 * q[n] - q[n - 1] - (dt**2) * fn

    # 3. Momentum recovery
    # Initial momentum p[0] is already set to float(p0)

    # Interior momenta: centered finite difference
    for n in range(1, steps):
        p[n] = (q[n + 1] - q[n - 1]) / (2.0 * dt)

    # Final boundary momentum: backward difference with half-step acceleration correction
    f_last = float(dV_dq_fn(q[steps]))
    p[steps] = (q[steps] - q[steps - 1]) / dt - 0.5 * dt * f_last

    return {
        "q": q,
        "p": p,
        "time": time,
    }
