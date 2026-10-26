import math
from typing import Tuple
import numpy as np


class LorenzSystem:
    """
    Simulates the chaotic Lorenz attractor and calculates maximal Lyapunov exponents.
    """

    def __init__(self, sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0 / 3.0) -> None:
        self.sigma = float(sigma)
        self.rho = float(rho)
        self.beta = float(beta)

    def _derivatives(self, state: np.ndarray) -> np.ndarray:
        x, y, z = state[0], state[1], state[2]
        dx = self.sigma * (y - x)
        dy = x * (self.rho - z) - y
        dz = x * y - self.beta * z
        return np.array([dx, dy, dz], dtype=float)

    def _rk4_step(self, state: np.ndarray, dt: float) -> np.ndarray:
        k1 = self._derivatives(state)
        k2 = self._derivatives(state + 0.5 * dt * k1)
        k3 = self._derivatives(state + 0.5 * dt * k2)
        k4 = self._derivatives(state + dt * k3)
        return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    def simulate(
        self,
        state0: Tuple[float, float, float],
        dt: float,
        steps: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        trajectory = np.zeros((steps + 1, 3), dtype=float)
        t = np.linspace(0.0, dt * steps, steps + 1)

        curr = np.array(state0, dtype=float)
        trajectory[0] = curr

        for i in range(steps):
            curr = self._rk4_step(curr, dt)
            trajectory[i + 1] = curr

        return t, trajectory

    def estimate_maximal_lyapunov(
        self,
        state0: Tuple[float, float, float],
        dt: float = 0.01,
        steps: int = 3000,
        d0: float = 1e-8,
    ) -> float:
        # Transient settling
        x = np.array(state0, dtype=float)
        for _ in range(500):
            x = self._rk4_step(x, dt)

        # Perturbed trajectory
        pert = np.array([1.0, 0.0, 0.0], dtype=float)
        pert = pert / np.linalg.norm(pert)
        y = x + d0 * pert

        divergence_sum = 0.0

        for _ in range(steps):
            x = self._rk4_step(x, dt)
            y = self._rk4_step(y, dt)

            diff = y - x
            dist = float(np.linalg.norm(diff))

            if dist > 0.0:
                divergence_sum += math.log(dist / d0)
                # Renormalize y back to distance d0 along the divergence direction
                y = x + (d0 / dist) * diff

        total_time = steps * dt
        return float(divergence_sum / total_time)
