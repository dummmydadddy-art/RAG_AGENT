import math
from typing import Any, Union


class Quaternion:
    """3D unit/general quaternion supporting Hamilton algebra, rotations, and SLERP."""

    __slots__ = ("w", "x", "y", "z")

    def __init__(self, w: float, x: float, y: float, z: float) -> None:
        self.w: float = float(w)
        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)

    @classmethod
    def from_axis_angle(cls, axis: tuple[float, float, float], angle_rad: float) -> "Quaternion":
        if len(axis) != 3:
            raise ValueError("Axis must be a 3D vector")
        ax, ay, az = float(axis[0]), float(axis[1]), float(axis[2])
        norm_axis = math.sqrt(ax * ax + ay * ay + az * az)
        if norm_axis < 1e-15:
            raise ValueError("Axis vector cannot have zero length")

        ux = ax / norm_axis
        uy = ay / norm_axis
        uz = az / norm_axis

        half_angle = float(angle_rad) / 2.0
        sin_half = math.sin(half_angle)
        return cls(
            w=math.cos(half_angle),
            x=ux * sin_half,
            y=uy * sin_half,
            z=uz * sin_half,
        )

    def norm(self) -> float:
        return math.sqrt(self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z)

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def inverse(self) -> "Quaternion":
        n = self.norm()
        if n < 1e-15:
            raise ZeroDivisionError("Cannot invert zero-norm quaternion")
        n2 = n * n
        return Quaternion(self.w / n2, -self.x / n2, -self.y / n2, -self.z / n2)

    def normalize(self) -> "Quaternion":
        n = self.norm()
        if n < 1e-15:
            raise ZeroDivisionError("Cannot normalize zero-norm quaternion")
        return Quaternion(self.w / n, self.x / n, self.y / n, self.z / n)

    def __add__(self, other: "Quaternion") -> "Quaternion":
        if not isinstance(other, Quaternion):
            return NotImplemented
        return Quaternion(self.w + other.w, self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Quaternion") -> "Quaternion":
        if not isinstance(other, Quaternion):
            return NotImplemented
        return Quaternion(self.w - other.w, self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other: Union["Quaternion", float, int]) -> "Quaternion":
        if isinstance(other, Quaternion):
            # Hamilton product
            w1, x1, y1, z1 = self.w, self.x, self.y, self.z
            w2, x2, y2, z2 = other.w, other.x, other.y, other.z
            return Quaternion(
                w=w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                x=w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                y=w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                z=w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            )
        elif isinstance(other, (int, float)):
            s = float(other)
            return Quaternion(self.w * s, self.x * s, self.y * s, self.z * s)
        return NotImplemented

    def __rmul__(self, scalar: Union[float, int]) -> "Quaternion":
        if isinstance(scalar, (int, float)):
            s = float(scalar)
            return Quaternion(self.w * s, self.x * s, self.y * s, self.z * s)
        return NotImplemented

    def __truediv__(self, scalar: Union[float, int]) -> "Quaternion":
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        s = float(scalar)
        if abs(s) < 1e-15:
            raise ZeroDivisionError("Division by zero")
        return Quaternion(self.w / s, self.x / s, self.y / s, self.z / s)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Quaternion):
            return False
        return (
            abs(self.w - other.w) < 1e-9
            and abs(self.x - other.x) < 1e-9
            and abs(self.y - other.y) < 1e-9
            and abs(self.z - other.z) < 1e-9
        )

    def to_rotation_matrix(self) -> list[list[float]]:
        q = self.normalize()
        w, x, y, z = q.w, q.x, q.y, q.z

        return [
            [
                1.0 - 2.0 * (y * y + z * z),
                2.0 * (x * y - w * z),
                2.0 * (x * z + w * y),
            ],
            [
                2.0 * (x * y + w * z),
                1.0 - 2.0 * (x * x + z * z),
                2.0 * (y * z - w * x),
            ],
            [
                2.0 * (x * z - w * y),
                2.0 * (y * z + w * x),
                1.0 - 2.0 * (x * x + y * y),
            ],
        ]

    def rotate_vector(self, v: tuple[float, float, float]) -> tuple[float, float, float]:
        if len(v) != 3:
            raise ValueError("Input vector must be 3D tuple")
        q_unit = self.normalize()
        v_quat = Quaternion(0.0, float(v[0]), float(v[1]), float(v[2]))
        q_rot = (q_unit * v_quat) * q_unit.inverse()
        return (q_rot.x, q_rot.y, q_rot.z)

    @staticmethod
    def slerp(q1: "Quaternion", q2: "Quaternion", t: float) -> "Quaternion":
        p1 = q1.normalize()
        p2 = q2.normalize()

        dot = p1.w * p2.w + p1.x * p2.x + p1.y * p2.y + p1.z * p2.z

        # Shortest arc check
        if dot < 0.0:
            p2 = Quaternion(-p2.w, -p2.x, -p2.y, -p2.z)
            dot = -dot

        if dot > 0.9995:
            # Fallback to normalized lerp for collinear quaternions
            res = (1.0 - t) * p1 + t * p2
            return res.normalize()

        theta = math.acos(dot)
        sin_theta = math.sin(theta)

        scale1 = math.sin((1.0 - t) * theta) / sin_theta
        scale2 = math.sin(t * theta) / sin_theta

        return (scale1 * p1) + (scale2 * p2)
