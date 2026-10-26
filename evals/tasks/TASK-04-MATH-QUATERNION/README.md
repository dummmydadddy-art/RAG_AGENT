# Quaternion Algebra & 3D Spatial Rotation Matrix

**Category**: maths
**Held Out**: True

## Specification
Implement `Quaternion(w: float, x: float, y: float, z: float)` in `src/quaternion.py`.
Methods:
- `__add__`, `__mul__` (Hamilton product: i^2=j^2=k^2=ijk=-1)
- `conjugate() -> Quaternion`
- `norm() -> float` and `normalize() -> Quaternion`
- `to_rotation_matrix() -> list[list[float]]`: 3x3 orthonormal rotation matrix.
- `rotate_vector(v: tuple[float, float, float]) -> tuple[float, float, float]`: Rotates vector v via q * v * q^-1.
