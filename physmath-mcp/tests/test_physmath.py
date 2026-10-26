import pytest
from physmath_mcp.sandbox import run_sandboxed_code
from physmath_mcp.server import numeric_compare, sym_equiv, units_check


def test_units_check_valid_force():
    res = units_check(
        expression="m * a",
        symbol_units={"m": "kilogram", "a": "meter / second**2"},
        target_unit="newton",
    )
    assert res.get("valid") is True
    assert res.get("compatible_with_target") is True


def test_units_check_invalid_dimension():
    res = units_check(
        expression="m * v",
        symbol_units={"m": "kilogram", "v": "meter / second"},
        target_unit="joule",
    )
    assert res.get("valid") is True
    assert res.get("compatible_with_target") is False
    assert "mismatch" in res.get("details", "").lower()


def test_sym_equiv_trig_identity():
    res = sym_equiv(
        expr1="sin(x)**2 + cos(x)**2",
        expr2="1",
        assumptions={"x": {"real": True}},
    )
    assert res.get("equivalent") is True
    assert res.get("method") == "symbolic_simplify"
    assert res.get("residual") == 0.0


def test_sym_equiv_polynomial_expansion():
    res = sym_equiv(
        expr1="(x + y)**2",
        expr2="x**2 + 2*x*y + y**2",
    )
    assert res.get("equivalent") is True
    assert res.get("residual") == 0.0


def test_sym_equiv_non_equivalent():
    res = sym_equiv(
        expr1="x**2",
        expr2="x**3",
    )
    assert res.get("equivalent") is False


def test_numeric_compare_matching():
    func1 = "def func(x):\n    return np.sin(x)\n"
    func2 = "def func(x):\n    return x - (x**3)/6.0 + (x**5)/120.0\n"
    domain = {"x": [-0.2, 0.2, 50]}

    res = numeric_compare(func1, func2, domain, tol_rel=1e-3, tol_abs=1e-4)
    assert res.get("match") is True
    assert res.get("points_evaluated") == 50


def test_numeric_compare_divergent():
    func1 = "def func(x):\n    return x**2\n"
    func2 = "def func(x):\n    return x**2 + 5.0\n"
    domain = {"x": [0, 10, 20]}

    res = numeric_compare(func1, func2, domain, tol_rel=1e-3, tol_abs=1e-3)
    assert res.get("match") is False
    assert res.get("max_abs_diff") >= 5.0


def test_sandbox_timeout_enforcement():
    # Attempt an infinite loop or excessive sleep
    infinite_script = "import time\ntime.sleep(5.0)\nprint('finished')"
    res = run_sandboxed_code(infinite_script, timeout_seconds=0.5)
    assert res.get("success") is False
    assert "timed out after 0.5s" in res.get("error", "")


def test_sandbox_network_denial_enforcement():
    # Attempt network connection
    network_script = (
        "import socket\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.connect(('1.1.1.1', 80))\n"
    )
    res = run_sandboxed_code(network_script, timeout_seconds=2.0)
    assert res.get("success") is False
    assert "Network access is disabled inside the physmath sandbox" in res.get("error", "")
