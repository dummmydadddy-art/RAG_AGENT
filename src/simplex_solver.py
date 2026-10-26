from typing import Any, Dict, List, Optional
import numpy as np
from scipy.optimize import linprog


def solve_linear_program(
    c: List[float],
    A: List[List[float]],
    b: List[float],
) -> Dict[str, Any]:
    """
    Solve linear program: max c^T x subject to A x <= b, x >= 0 using Simplex.
    """
    # SciPy minimizes, so objective is -c
    c_arr = -np.array(c, dtype=float)
    A_arr = np.array(A, dtype=float)
    b_arr = np.array(b, dtype=float)

    bounds = [(0, None) for _ in range(len(c))]

    res = linprog(c=c_arr, A_ub=A_arr, b_ub=b_arr, bounds=bounds, method="highs")

    if res.success:
        return {
            "status": "optimal",
            "objective_value": float(-res.fun),
            "solution": [float(x) for x in res.x],
        }
    elif res.status == 2:
        return {
            "status": "infeasible",
            "objective_value": None,
            "solution": None,
        }
    elif res.status == 3:
        return {
            "status": "unbounded",
            "objective_value": None,
            "solution": None,
        }
    else:
        return {
            "status": "failed",
            "objective_value": None,
            "solution": None,
            "message": res.message,
        }
