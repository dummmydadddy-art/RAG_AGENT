# Task Specification: 3D Rotation Quaternion with SLERP

## 1. Class & Method Contract
Implement `Quaternion` in `src/quaternion.py`.

### Constructor Signature
```python
def __init__(self, w: float, x: float, y: float, z: float) -> None:
```
Accepts float or int components, converted and stored internally as floats.

### Alternative Constructors
- `@classmethod from_axis_angle(cls, axis: tuple[float, float, float], angle_rad: float) -> "Quaternion"`:
  - If axis vector norm $\sqrt{a_x^2 + a_y^2 + a_z^2} < 10^{-15}$, raise `ValueError("Axis vector cannot have zero length")`.
  - Normalizes `axis` to unit vector $\mathbf{u} = \mathbf{axis} / \|\mathbf{axis}\|$.
  - Constructs unit quaternion:
    $$q = \left(\cos\left(rac{	heta}{2}ight), u_x \sin\left(rac{	heta}{2}ight), u_y \sin\left(rac{	heta}{2}ight), u_z \sin\left(rac{	heta}{2}ight)ight)$$

### Properties & Unary Methods
1. `norm(self) -> float`: Returns Euclidean magnitude $\sqrt{w^2 + x^2 + y^2 + z^2}$.
2. `conjugate(self) -> "Quaternion"`: Returns $(w, -x, -y, -z)$.
3. `inverse(self) -> "Quaternion"`:
   - If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot invert zero-norm quaternion")`.
   - Returns `self.conjugate() / (self.norm() ** 2)`.
4. `normalize(self) -> "Quaternion"`:
   - If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Returns `self / self.norm()`.

### Arithmetic Operators
1. `__add__(self, other: "Quaternion") -> "Quaternion"`: Component-wise addition.
2. `__sub__(self, other: "Quaternion") -> "Quaternion"`: Component-wise subtraction.
3. `__mul__(self, other: Union["Quaternion", float, int]) -> "Quaternion"`:
   - If `other` is `Quaternion`: Hamilton quaternion product.
   - If `other` is `float` or `int`: Scalar multiplication $(s \cdot w, s \cdot x, s \cdot y, s \cdot z)$.
   - Otherwise, returns `NotImplemented`.
4. `__rmul__(self, scalar: Union[float, int]) -> "Quaternion"`:
   - Scalar multiplication on left ($s \cdot q$). Returns `NotImplemented` if `scalar` is not `float` or `int`.
5. `__truediv__(self, scalar: Union[float, int]) -> "Quaternion"`:
   - Component-wise division by scalar. If $|scalar| < 10^{-15}$, raise `ZeroDivisionError("Division by zero")`.
6. `__eq__(self, other: Any) -> bool`:
   - Returns `True` if `other` is a `Quaternion` and all corresponding components agree within absolute tolerance $10^{-9}$.

### Geometry & Rotation Methods
1. `to_rotation_matrix(self) -> list[list[float]]`:
   - Normalizes `self` to unit quaternion $\hat{q} = (w, x, y, z)$. If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Returns standard $3 	imes 3$ rotation matrix as a nested list of floats:
     $$R = \begin{bmatrix} 1 - 2(y^2 + z^2) & 2(xy - wz) & 2(xz + wy) \\ 2(xy + wz) & 1 - 2(x^2 + z^2) & 2(yz - wx) \\ 2(xz - wy) & 2(yz + wx) & 1 - 2(x^2 + y^2) \end{bmatrix}$$
2. `rotate_vector(self, v: tuple[float, float, float]) -> tuple[float, float, float]`:
   - Normalizes `self` to $\hat{q}$. If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Computes $q_{rot} = \hat{q} \cdot (0, v_x, v_y, v_z) \cdot \hat{q}^{-1}$.
   - Returns rotated 3D tuple $(x', y', z')$.
3. `@staticmethod slerp(q1: "Quaternion", q2: "Quaternion", t: float) -> "Quaternion"`:
   - Spherical linear interpolation between two quaternions for parameter $t \in [0.0, 1.0]$.
   - Normalizes inputs $q_1$ and $q_2$.
   - Computes dot product $\cos(\Omega) = w_1 w_2 + x_1 x_2 + y_1 y_2 + z_1 z_2$.
   - If $\cos(\Omega) < 0.0$, inverts $q_2 \leftarrow -q_2$ and $\cos(\Omega) \leftarrow -\cos(\Omega)$ to take the shortest arc.
   - If $\cos(\Omega) > 0.9995$ (nearly collinear), falls back to normalized linear interpolation (NLERP): $	ext{normalize}((1 - t) q_1 + t q_2)$.
   - Otherwise, computes standard SLERP:
     $$rac{\sin((1 - t)\Omega)}{\sin(\Omega)} q_1 + rac{\sin(t \Omega)}{\sin(\Omega)} q_2$$
