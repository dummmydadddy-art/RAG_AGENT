import math
from typing import Callable, Dict, Optional
import numpy as np


def solve_wave_1d(
    c: float,
    length: float,
    t_max: float,
    nx: int,
    cfl: float = 0.5,
    initial_u: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    initial_v: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    absorbing: bool = True,
) -> Dict[str, np.ndarray]:
    """
    1D Acoustic wave equation solver with leapfrog finite difference and optional Mur absorbing boundaries.
    """
    if c <= 0.0 or length <= 0.0 or t_max <= 0.0 or nx < 3:
        raise ValueError("Invalid parameters for wave solver")

    dx = length / (nx - 1)
    dt = cfl * dx / c
    nt = int(math.ceil(t_max / dt)) + 1

    x = np.linspace(0.0, length, nx)
    t = np.linspace(0.0, (nt - 1) * dt, nt)

    u = np.zeros((nt, nx), dtype=float)

    # Initial condition
    if initial_u is not None:
        u[0, :] = initial_u(x)
    v0 = initial_v(x) if initial_v is not None else np.zeros(nx)

    # First time step n=1
    r2 = cfl**2
    for i in range(1, nx - 1):
        u[1, i] = u[0, i] + dt * v0[i] + 0.5 * r2 * (u[0, i + 1] - 2.0 * u[0, i] + u[0, i - 1])

    if absorbing:
        mur_c = (cfl - 1.0) / (cfl + 1.0)
        u[1, 0] = u[0, 1] + mur_c * (u[1, 1] - u[0, 0])
        u[1, -1] = u[0, -2] + mur_c * (u[1, -2] - u[0, -1])

    # Leapfrog time stepping n -> n+1
    for n in range(1, nt - 1):
        # Interior points
        u[n + 1, 1:-1] = (
            2.0 * u[n, 1:-1]
            - u[n - 1, 1:-1]
            + r2 * (u[n, 2:] - 2.0 * u[n, 1:-1] + u[n, :-2])
        )

        if absorbing:
            mur_c = (cfl - 1.0) / (cfl + 1.0)
            u[n + 1, 0] = u[n, 1] + mur_c * (u[n + 1, 1] - u[n, 0])
            u[n + 1, -1] = u[n, -2] + mur_c * (u[n + 1, -2] - u[n, -1])
        else:
            u[n + 1, 0] = 0.0
            u[n + 1, -1] = 0.0

    return {"x": x, "t": t, "u": u}
