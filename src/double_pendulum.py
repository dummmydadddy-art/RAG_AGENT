import math
from typing import Any, Dict, Tuple
import numpy as np


class DoublePendulum:
    """
    Simulates chaotic double pendulum dynamics using 4th-order Runge-Kutta (RK4).
    Tracks total mechanical energy T + V.
    """

    def __init__(
        self,
        l1: float = 1.0,
        l2: float = 1.0,
        m1: float = 1.0,
        m2: float = 1.0,
        g: float = 9.81,
    ) -> None:
        if l1 <= 0.0 or l2 <= 0.0 or m1 <= 0.0 or m2 <= 0.0 or g <= 0.0:
            raise ValueError("Lengths, masses and gravity must be positive")
        self.l1 = float(l1)
        self.l2 = float(l2)
        self.m1 = float(m1)
        self.m2 = float(m2)
        self.g = float(g)

    def _derivatives(self, state: np.ndarray) -> np.ndarray:
        th1, w1, th2, w2 = state[0], state[1], state[2], state[3]
        delta = th1 - th2

        den1 = self.l1 * (2.0 * self.m1 + self.m2 - self.m2 * math.cos(2.0 * delta))
        num1 = (
            -self.g * (2.0 * self.m1 + self.m2) * math.sin(th1)
            - self.m2 * self.g * math.sin(th1 - 2.0 * th2)
            - 2.0 * math.sin(delta) * self.m2 * (w2**2 * self.l2 + w1**2 * self.l1 * math.cos(delta))
        )
        alpha1 = num1 / den1

        den2 = self.l2 * (2.0 * self.m1 + self.m2 - self.m2 * math.cos(2.0 * delta))
        num2 = (
            2.0
            * math.sin(delta)
            * (
                w1**2 * self.l1 * (self.m1 + self.m2)
                + self.g * (self.m1 + self.m2) * math.cos(th1)
                + w2**2 * self.l2 * self.m2 * math.cos(delta)
            )
        )
        alpha2 = num2 / den2

        return np.array([w1, alpha1, w2, alpha2], dtype=float)

    def compute_energy(self, state: np.ndarray) -> float:
        th1, w1, th2, w2 = state[0], state[1], state[2], state[3]
        delta = th1 - th2
        t1 = 0.5 * self.m1 * (self.l1 * w1) ** 2
        t2 = 0.5 * self.m2 * (
            (self.l1 * w1) ** 2
            + (self.l2 * w2) ** 2
            + 2.0 * self.l1 * self.l2 * w1 * w2 * math.cos(delta)
        )
        v1 = -(self.m1 + self.m2) * self.g * self.l1 * math.cos(th1)
        v2 = -self.m2 * self.g * self.l2 * math.cos(th2)
        return float(t1 + t2 + v1 + v2)

    def simulate(
        self,
        theta1: float,
        omega1: float,
        theta2: float,
        omega2: float,
        dt: float,
        steps: int,
    ) -> Dict[str, Any]:
        t_arr = np.linspace(0.0, dt * steps, steps + 1)
        th1_arr = np.zeros(steps + 1)
        w1_arr = np.zeros(steps + 1)
        th2_arr = np.zeros(steps + 1)
        w2_arr = np.zeros(steps + 1)
        e_arr = np.zeros(steps + 1)

        curr_state = np.array([theta1, omega1, theta2, omega2], dtype=float)

        th1_arr[0], w1_arr[0] = curr_state[0], curr_state[1]
        th2_arr[0], w2_arr[0] = curr_state[2], curr_state[3]
        e_arr[0] = self.compute_energy(curr_state)

        for i in range(steps):
            # RK4 step
            k1 = self._derivatives(curr_state)
            k2 = self._derivatives(curr_state + 0.5 * dt * k1)
            k3 = self._derivatives(curr_state + 0.5 * dt * k2)
            k4 = self._derivatives(curr_state + dt * k3)
            curr_state = curr_state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

            th1_arr[i + 1], w1_arr[i + 1] = curr_state[0], curr_state[1]
            th2_arr[i + 1], w2_arr[i + 1] = curr_state[2], curr_state[3]
            e_arr[i + 1] = self.compute_energy(curr_state)

        return {
            "t": t_arr,
            "theta1": th1_arr,
            "omega1": w1_arr,
            "theta2": th2_arr,
            "omega2": w2_arr,
            "energy": e_arr,
        }
