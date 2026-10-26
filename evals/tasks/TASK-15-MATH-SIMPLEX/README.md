# Task Specification: Two-Phase Simplex Algorithm for Linear Programming

## 1. Function Contract
Implement `solve_linear_program` in `src/simplex_solver.py`.

### Function Signature
```python
def solve_linear_program(
    c: List[float],
    A: List[List[float]],
    b: List[float]
) -> Dict[str, Any]:
```
- Solves standard form maximization: $\max c^T x$ subject to $A x \le b$ and $x \ge 0$.
- Implements two-phase simplex with slack variables.
- Returns dictionary:
  `{"status": "optimal" | "unbounded" | "infeasible", "objective_value": Optional[float], "solution": Optional[List[float]]}`.
