import math
from typing import Any


def solve_kepler_orbit(
    r0: tuple[float, float],
    v0: tuple[float, float],
    gm: float,
    dt: float,
    steps: int,
) -> dict[str, Any]:
    """Integrates 2D Keplerian two-body orbit using symplectic Velocity Verlet scheme."""
    if len(r0) != 2 or len(v0) != 2:
        raise ValueError("Initial conditions must be 2D vectors")

    x0, y0 = float(r0[0]), float(r0[1])
    vx0, vy0 = float(v0[0]), float(v0[1])

    r0_norm = math.sqrt(x0 * x0 + y0 * y0)
    if r0_norm < 1e-12:
        raise ValueError("Initial radius cannot be zero")

    if gm <= 0.0:
        raise ValueError("GM parameter must be positive")
    if dt <= 0.0:
        raise ValueError("Time step dt must be positive")
    if steps < 1:
        raise ValueError("Steps must be at least 1")

    positions: list[tuple[float, float]] = [(x0, y0)]
    velocities: list[tuple[float, float]] = [(vx0, vy0)]
    energies: list[float] = [0.5 * (vx0 * vx0 + vy0 * vy0) - gm / r0_norm]
    angular_momenta: list[float] = [x0 * vy0 - y0 * vx0]
    times: list[float] = [0.0]

    curr_x, curr_y = x0, y0
    curr_vx, curr_vy = vx0, vy0

    def compute_acc(x: float, y: float) -> tuple[float, float]:
        r = math.sqrt(x * x + y * y)
        if r < 1e-12:
            raise ValueError("Collision with gravitational center detected")
        factor = -gm / (r**3)
        return (factor * x, factor * y)

    curr_ax, curr_ay = compute_acc(curr_x, curr_y)

    for n in range(1, steps + 1):
        # Velocity Verlet: position step
        next_x = curr_x + curr_vx * dt + 0.5 * curr_ax * (dt**2)
        next_y = curr_y + curr_vy * dt + 0.5 * curr_ay * (dt**2)

        # Acceleration at next position
        next_ax, next_ay = compute_acc(next_x, next_y)

        # Velocity step
        next_vx = curr_vx + 0.5 * (curr_ax + next_ax) * dt
        next_vy = curr_vy + 0.5 * (curr_ay + next_ay) * dt

        # Diagnostics
        r_norm = math.sqrt(next_x * next_x + next_y * next_y)
        v_sq = next_vx * next_vx + next_vy * next_vy
        e = 0.5 * v_sq - gm / r_norm
        Lz = next_x * next_vy - next_y * next_vx

        positions.append((next_x, next_y))
        velocities.append((next_vx, next_vy))
        energies.append(e)
        angular_momenta.append(Lz)
        times.append(round(n * dt, 10))

        curr_x, curr_y = next_x, next_y
        curr_vx, curr_vy = next_vx, next_vy
        curr_ax, curr_ay = next_ax, next_ay

    return {
        "position": positions,
        "velocity": velocities,
        "energy": energies,
        "angular_momentum": angular_momenta,
        "time": times,
    }
