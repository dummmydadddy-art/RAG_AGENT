from typing import List, Tuple
import numpy as np
from numpy.polynomial import chebyshev as cheb


def find_chebyshev_roots(
    coeffs: List[float],
    domain: Tuple[float, float] = (-1.0, 1.0),
) -> List[float]:
    """
    Find all real roots of a Chebyshev polynomial series P(x) = sum c_k T_k(x)
    strictly within the domain [domain[0], domain[1]] via Colleague companion matrix eigenvalues.
    """
    c_arr = np.array(coeffs, dtype=float)
    # Strip trailing near-zero coefficients
    while len(c_arr) > 1 and abs(c_arr[-1]) < 1e-12:
        c_arr = c_arr[:-1]

    if len(c_arr) <= 1:
        return []

    # Compute roots via colleague matrix
    raw_roots = cheb.chebroots(c_arr)

    # Filter for real roots within domain
    real_roots = []
    d_min, d_max = domain[0], domain[1]

    for r in raw_roots:
        if abs(r.imag) < 1e-7:
            val = float(r.real)
            if (d_min - 1e-6) <= val <= (d_max + 1e-6):
                # Clamp within domain
                clamped = max(d_min, min(d_max, val))
                real_roots.append(round(clamped, 8))

    unique_sorted = sorted(list(set(real_roots)))
    return unique_sorted
