from typing import Optional, Tuple
import numpy as np


def simulate_gray_scott_2d(
    width: int,
    height: int,
    Du: float = 0.16,
    Dv: float = 0.08,
    feed: float = 0.035,
    kill: float = 0.060,
    dt: float = 1.0,
    steps: int = 100,
    initial_u: Optional[np.ndarray] = None,
    initial_v: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    2D Reaction-Diffusion Gray-Scott pattern simulator using 5-point discrete Laplacian
    with periodic toroidal boundary conditions.
    """
    if width <= 0 or height <= 0 or steps <= 0:
        raise ValueError("Grid dimensions and steps must be positive")

    if initial_u is not None:
        U = np.array(initial_u, dtype=float).copy()
    else:
        U = np.ones((height, width), dtype=float)

    if initial_v is not None:
        V = np.array(initial_v, dtype=float).copy()
    else:
        V = np.zeros((height, width), dtype=float)

    def _laplacian_5pt(arr: np.ndarray) -> np.ndarray:
        return (
            np.roll(arr, 1, axis=0)
            + np.roll(arr, -1, axis=0)
            + np.roll(arr, 1, axis=1)
            + np.roll(arr, -1, axis=1)
            - 4.0 * arr
        )

    for _ in range(steps):
        lap_u = _laplacian_5pt(U)
        lap_v = _laplacian_5pt(V)

        uvv = U * V * V
        du_dt = Du * lap_u - uvv + feed * (1.0 - U)
        dv_dt = Dv * lap_v + uvv - (feed + kill) * V

        U = U + du_dt * dt
        V = V + dv_dt * dt

        # Enforce physical concentration bounds [0, 1]
        np.clip(U, 0.0, 1.0, out=U)
        np.clip(V, 0.0, 1.0, out=V)

    return U, V
