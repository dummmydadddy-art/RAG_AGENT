# Task Specification: Chebyshev Polynomial Root Finder via Companion Matrix

## 1. Function Contract
Implement `find_chebyshev_roots` in `src/chebyshev_roots.py`.

### Function Signature
```python
def find_chebyshev_roots(
    coeffs: List[float],
    domain: Tuple[float, float] = (-1.0, 1.0)
) -> List[float]:
```
- `coeffs`: Coefficients $c_0, c_1, \dots, c_n$ for expansion $P(x) = \sum_{k=0}^n c_k T_k(x)$ where $T_k$ are Chebyshev polynomials of the first kind.
- Finds all real roots of $P(x)$ strictly within the interval `[domain[0], domain[1]]`.
- Uses Frobenius/Colleague companion matrix eigenvalue decomposition.
- Returns list of sorted unique real roots within tolerance `1e-6`.
