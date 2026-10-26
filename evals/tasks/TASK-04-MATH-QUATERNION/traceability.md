# Traceability Matrix: TASK-04-MATH-QUATERNION

| Test Assertion | Spec Sentence Justification |
|---|---|
| `Quaternion.from_axis_angle((0, 0, 0), 1.0)` raises `ValueError` | "If axis vector norm < 1e-15, raise ValueError(\"Axis vector cannot have zero length\")" |
| `Quaternion(0, 0, 0, 0).inverse()` raises `ZeroDivisionError` | "If norm() < 1e-15, raise ZeroDivisionError(\"Cannot invert zero-norm quaternion\")" |
| Quaternion Hamilton multiplication non-commutativity ($i \cdot j = k$, $j \cdot i = -k$) | "Hamilton quaternion product." |
| Scalar left and right multiplication `2.0 * q == q * 2.0` | "Scalar multiplication on left... Scalar multiplication (s*w, s*x, s*y, s*z)" |
| 90 degree Z-axis rotation matrix transforms $(1, 0, 0)$ to $(0, 1, 0)$ | "to_rotation_matrix... Returns standard 3x3 rotation matrix" |
| `rotate_vector` transforms $(1, 0, 0)$ to $(0, 1, 0)$ under 90 deg Z rotation | "rotate_vector... Computes q_rot = q_unit * (0, v) * q_unit^-1" |
| SLERP at $t=0.0$ returns $q_1$; at $t=1.0$ returns $q_2$; at $t=0.5$ bisects angle | "Spherical linear interpolation between two quaternions for parameter t in [0.0, 1.0]" |
| SLERP with opposite polarity takes shortest arc | "If cos(Omega) < 0.0, inverts q2 <- -q2 and cos(Omega) <- -cos(Omega) to take the shortest arc." |
