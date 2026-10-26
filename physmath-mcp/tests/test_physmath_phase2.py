import pytest
from physmath_mcp.server import (
    sym_solve,
    invariant_check,
    convergence_study,
    limit_check,
)


def test_sym_solve_diff():
    res = sym_solve(operation="diff", expression="sin(x**2)", variable="x")
    assert res.get("success") is True
    assert "cos(x**2)" in res.get("result")
    assert "2*x" in res.get("result") or "2 x" in res.get("result")


def test_sym_solve_integrate():
    res = sym_solve(operation="integrate", expression="2*x*cos(x**2)", variable="x")
    assert res.get("success") is True
    assert "sin(x**2)" in res.get("result")
    assert res.get("residual") is not None
    assert abs(res.get("residual")) < 1e-10


def test_sym_solve_solve():
    res = sym_solve(operation="solve", expression="x**2 - 9", variable="x")
    assert res.get("success") is True
    # Should find -3 and 3
    result_str = res.get("result")
    assert "-3" in result_str and "3" in result_str
    assert res.get("residual") is not None
    assert abs(res.get("residual")) < 1e-10


def test_sym_solve_series():
    res = sym_solve(operation="series", expression="exp(x)", variable="x", order=4, point=0.0)
    assert res.get("success") is True
    res_str = res.get("result")
    # 1 + x + x**2/2 + x**3/6
    assert "1" in res_str
    assert "x" in res_str


def test_invariant_check_symplectic():
    # Harmonic oscillator with symplectic Euler
    step_code = """
def step(t, state):
    x, v = state[0], state[1]
    dt = 0.01
    v_next = v - x * dt
    x_next = x + v_next * dt
    return t + dt, [x_next, v_next]
"""
    invariant_code = """
def invariant(t, state):
    x, v = state[0], state[1]
    return 0.5 * (x**2 + v**2)
"""
    res = invariant_check(
        step_code=step_code,
        invariant_code=invariant_code,
        initial_state=[1.0, 0.0],
        dt=0.01,
        steps=200,
        tol_rel=0.05,
    )
    assert res.get("success") is True
    assert res.get("conserved") is True
    assert res.get("max_drift_rel") < 0.05


def test_invariant_check_forward_euler_detects_drift():
    # Harmonic oscillator with explicit Euler (unstable energy growth)
    step_code = """
def step(t, state):
    x, v = state[0], state[1]
    dt = 0.1
    x_next = x + v * dt
    v_next = v - x * dt
    return t + dt, [x_next, v_next]
"""
    invariant_code = """
def invariant(t, state):
    x, v = state[0], state[1]
    return 0.5 * (x**2 + v**2)
"""
    res = invariant_check(
        step_code=step_code,
        invariant_code=invariant_code,
        initial_state=[1.0, 0.0],
        dt=0.1,
        steps=200,
        tol_rel=0.05,
    )
    assert res.get("success") is True
    assert res.get("conserved") is False
    assert res.get("max_drift_rel") > 0.05


def test_convergence_study_second_order():
    # Central difference f'(0) of sin(x) has order 2
    solver_code = """
import math
def solve(h):
    # central diff of sin(x) at x=1.0: exact deriv is cos(1.0)
    deriv_approx = (math.sin(1.0 + h) - math.sin(1.0 - h)) / (2.0 * h)
    exact = math.cos(1.0)
    return abs(deriv_approx - exact)
"""
    h_vals = [0.1, 0.05, 0.025, 0.0125]
    res = convergence_study(
        solver_code=solver_code,
        h_values=h_vals,
        expected_order=2.0,
        order_tol=0.2,
    )
    assert res.get("success") is True
    assert res.get("converges") is True
    assert res.get("order_match") is True
    assert abs(res.get("observed_order") - 2.0) < 0.2
    assert res.get("r_squared") > 0.99


def test_limit_check():
    # sin(x)/x as x -> 0 is 1
    res = limit_check(
        expression="sin(x)/x",
        variable="x",
        point="0",
        expected_limit="1",
    )
    assert res.get("success") is True
    assert res.get("limit_value") == "1"
    assert res.get("matches_expected") is True
    assert res.get("is_finite") is True

    # (2*x**2 + 1)/(x**2 - 3) as x -> oo is 2
    res2 = limit_check(
        expression="(2*x**2 + 1)/(x**2 - 3)",
        variable="x",
        point="oo",
        expected_limit="2",
    )
    assert res2.get("success") is True
    assert res2.get("limit_value") == "2"
    assert res2.get("matches_expected") is True
