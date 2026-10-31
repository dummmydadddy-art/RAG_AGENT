"""
tests/physmath/test_soundness_and_solvers.py

TDD Acceptance Tests for Milestone 2: PhysMath Engine Soundness & Domain Expansion.
Verifies:
1. Stratified Complex Sampling & Branch Cut Fixes (sym_equiv):
   - Correctly identifies branch cuts and sign-dependent non-equivalences (sqrt(x^2) != x, log(x*y) != log(x)+log(y)).
   - Respects explicit assumptions (positive=True proves sqrt(x^2) == x).
2. Non-Commutative Operator & Lie Algebra Verification:
   - Non-commutative symbols (A*B - B*A != 0).
3. Pint Temperature Offset Handling:
   - Converts degC to kelvin without OffsetUnitCalculusError.
4. Analytical and Numerical ODE/PDE Solvers:
   - sym_ode_solve: SymPy dsolve for 1st and 2nd order ODEs with initial values.
   - numeric_ode_solve: SciPy solve_ivp for RK45 and Radau (stiff ODEs).
5. Automated Noether Invariant Synthesizer:
   - Poisson bracket {I, H} == 0 conservation verification.
"""

import pytest
import math
from physmath_mcp.server import (
    sym_equiv,
    units_check,
    sym_ode_solve,
    numeric_ode_solve,
    noether_invariant_check,
)


class TestStratifiedComplexSampling:
    """Verifies that sym_equiv does not falsely equate expressions across branch cuts."""

    def test_sqrt_square_not_equivalent_to_x_without_positive_assumption(self):
        """sqrt(x^2) is |x|, which is not equivalent to x for negative reals."""
        res = sym_equiv("sqrt(x**2)", "x")
        # Must detect non-equivalence for negative reals!
        assert res["equivalent"] is False, "sqrt(x^2) must not be equivalent to x without positive assumption"

    def test_sqrt_square_equivalent_with_positive_assumption(self):
        """sqrt(x^2) is equivalent to x when x is assumed strictly positive."""
        res = sym_equiv("sqrt(x**2)", "x", assumptions={"x": {"positive": True}})
        assert res["equivalent"] is True

    def test_log_product_not_equivalent_without_positive_assumption(self):
        """log(x*y) is not equivalent to log(x) + log(y) for negative reals or complex numbers."""
        res = sym_equiv("log(x*y)", "log(x) + log(y)")
        assert res["equivalent"] is False

    def test_log_product_equivalent_with_positive_assumptions(self):
        """log(x*y) is equivalent to log(x) + log(y) when x and y are positive."""
        res = sym_equiv(
            "log(x*y)",
            "log(x) + log(y)",
            assumptions={"x": {"positive": True}, "y": {"positive": True}}
        )
        assert res["equivalent"] is True


class TestNonCommutativeOperatorAlgebra:
    """Verifies non-commutative symbols and operator algebras in sym_equiv."""

    def test_non_commutative_symbols_commutator_non_zero(self):
        """For non-commutative operators A and B, A*B - B*A != 0."""
        res = sym_equiv("A*B - B*A", "0", non_commutative_symbols=["A", "B"])
        assert res["equivalent"] is False, "A*B - B*A must not equal 0 for non-commutative operators"

    def test_standard_commutative_symbols_cancel(self):
        """Standard symbols are commutative: x*y - y*x == 0."""
        res = sym_equiv("x*y - y*x", "0")
        assert res["equivalent"] is True

    def test_non_commutative_addition_remains_commutative(self):
        """Operator addition is still commutative: A + B == B + A."""
        res = sym_equiv("A + B", "B + A", non_commutative_symbols=["A", "B"])
        assert res["equivalent"] is True


class TestPintTemperatureOffsetConversions:
    """Verifies temperature offset handling (degC, kelvin) in units_check."""

    def test_temperature_offset_degc_to_kelvin(self):
        """units_check converts degC to kelvin without offset calculus error."""
        res = units_check(
            expression="T",
            symbol_units={"T": "degC"},
            target_unit="kelvin"
        )
        assert res["valid"] is True
        assert res["compatible_with_target"] is True

    def test_temperature_difference_delta_kelvin(self):
        """Temperature differences produce compatible temperature dimensions."""
        res = units_check(
            expression="T2 - T1",
            symbol_units={"T1": "degC", "T2": "degC"},
            target_unit="kelvin"
        )
        assert res["valid"] is True
        assert res["compatible_with_target"] is True


class TestAnalyticalAndNumericalOdeSolvers:
    """Verifies SymPy dsolve and SciPy solve_ivp tools."""

    def test_sym_ode_solve_first_order_linear(self):
        """Solves y'(x) + 2*y(x) = 0 -> y(x) = C1*exp(-2*x)."""
        res = sym_ode_solve(
            equation="Derivative(y(x), x) + 2*y(x)",
            func="y(x)",
            var="x",
        )
        assert res["success"] is True
        assert "exp(-2*x)" in res["solution"]

    def test_sym_ode_solve_initial_value_problem(self):
        """Solves y'(x) - y(x) = 0 with y(0) = 5 -> y(x) = 5*exp(x)."""
        res = sym_ode_solve(
            equation="Derivative(y(x), x) - y(x)",
            func="y(x)",
            var="x",
            ics={"y(0)": 5},
        )
        assert res["success"] is True
        assert "5*exp(x)" in res["solution"] or "5*E**x" in res["solution"]

    def test_sym_ode_solve_second_order_harmonic(self):
        """Solves y''(x) + 4*y(x) = 0 -> y(x) = C1*sin(2*x) + C2*cos(2*x)."""
        res = sym_ode_solve(
            equation="Derivative(y(x), x, 2) + 4*y(x)",
            func="y(x)",
            var="x",
        )
        assert res["success"] is True
        assert "sin(2*x)" in res["solution"] or "cos(2*x)" in res["solution"]

    def test_numeric_ode_solve_rk45(self):
        """Numerically integrates dy/dt = -0.5*y from y(0)=10 to t=4. y(4) = 10*exp(-2) ~= 1.3533."""
        res = numeric_ode_solve(
            system_code="def f(t, y): return [-0.5 * y[0]]",
            y0=[10.0],
            t_span=[0.0, 4.0],
            method="RK45",
        )
        assert res["success"] is True
        assert len(res["t"]) > 0
        final_y = res["y"][0][-1]
        expected_y = 10.0 * math.exp(-2.0)
        assert abs(final_y - expected_y) < 1e-3

    def test_numeric_ode_solve_stiff_radau(self):
        """Numerically integrates stiff system with Radau solver."""
        res = numeric_ode_solve(
            system_code="import numpy as np\ndef f(t, y): return [-1000.0 * (y[0] - np.sin(t))]",
            y0=[0.0],
            t_span=[0.0, 1.0],
            method="Radau",
        )
        assert res["success"] is True
        assert len(res["t"]) > 0


class TestNoetherInvariantSynthesizer:
    """Verifies Hamiltonian Poisson bracket invariant checking."""

    def test_conserved_energy_invariant(self):
        """For H = p^2/(2*m) + k*q^2/2, H itself is conserved ({H, H} == 0)."""
        res = noether_invariant_check(
            hamiltonian="p**2 / (2*m) + k*q**2 / 2",
            invariant="p**2 / (2*m) + k*q**2 / 2",
            q="q",
            p="p",
        )
        assert res["success"] is True
        assert res["conserved"] is True
        assert res["poisson_bracket"] == "0"

    def test_non_conserved_coordinate_invariant(self):
        """For harmonic oscillator, coordinate q is not conserved ({q, H} = p/m != 0)."""
        res = noether_invariant_check(
            hamiltonian="p**2 / (2*m) + k*q**2 / 2",
            invariant="q",
            q="q",
            p="p",
        )
        assert res["success"] is True
        assert res["conserved"] is False
        assert res["poisson_bracket"] != "0"
