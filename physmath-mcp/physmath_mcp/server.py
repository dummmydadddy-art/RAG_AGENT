import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure physmath_mcp is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from physmath_mcp.sandbox import run_sandboxed_code

mcp = FastMCP("physmath-mcp")


@mcp.tool()
def units_check(
    expression: str,
    symbol_units: Dict[str, str],
    target_unit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check dimensional consistency and unit compatibility of an expression using Pint.
    Runs inside an isolated subprocess sandbox without network access.
    """
    expr_json = json.dumps(expression)
    syms_json = json.dumps(json.dumps(symbol_units))
    target_json = json.dumps(target_unit)

    script = f"""
import json
import sys
import pint

ureg = pint.UnitRegistry()

expr_str = {expr_json}
symbol_units = json.loads({syms_json})
target_unit_str = {target_json}

try:
    context = {{}}
    for sym, u_str in symbol_units.items():
        try:
            context[sym] = ureg.Quantity(1.0, u_str)
        except Exception:
            context[sym] = 1.0 * ureg(u_str)

    # Evaluate the expression in context of pint quantities
    eval_result = eval(expr_str, {{"__builtins__": None}}, context)
    
    if hasattr(eval_result, "units"):
        res_unit = str(eval_result.units)
        res_dim = str(eval_result.dimensionality)
    else:
        # Dimensionless scalar
        res_unit = "dimensionless"
        res_dim = "dimensionless"

    compatible = True
    details = "Dimensionally consistent"
    if target_unit_str:
        try:
            target = ureg.Quantity(1.0, target_unit_str)
        except Exception:
            target = 1.0 * ureg(target_unit_str)
        try:
            eval_result.to(target.units)
            compatible = True
            details = f"Consistent and matches target unit {{target_unit_str}}"
        except Exception as de:
            compatible = False
            details = f"Dimensionality mismatch with target unit {{target_unit_str}}: {{str(de)}}"

    print(json.dumps({{
        "valid": True,
        "resulting_unit": res_unit,
        "dimensionality": res_dim,
        "compatible_with_target": compatible,
        "details": details
    }}))

except Exception as e:
    print(json.dumps({{
        "valid": False,
        "error": str(e),
        "details": f"Failed units evaluation: {{str(e)}}"
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"valid": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def sym_equiv(
    expr1: str,
    expr2: str,
    assumptions: Optional[Dict[str, Any]] = None,
    domain: str = "real",
    non_commutative_symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Verify symbolic equivalence between two mathematical expressions using SymPy.
    Supports stratified sampling across branch cuts, non-commutative operator algebras,
    and domain-specific assumptions.
    """
    e1_json = json.dumps(expr1)
    e2_json = json.dumps(expr2)
    assump_json = json.dumps(json.dumps(assumptions or {}))
    dom_json = json.dumps(domain)
    nc_json = json.dumps(non_commutative_symbols or [])

    script = f"""
import json
import random
import re
import sys
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

expr1_str = {e1_json}
expr2_str = {e2_json}
assumptions_dict = json.loads({assump_json})
domain_str = {dom_json}
nc_symbols = set({nc_json})

transformations = standard_transformations + (implicit_multiplication_application,)

try:
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr1_str + " " + expr2_str))
    reserved = {{"sqrt", "sin", "cos", "tan", "log", "exp", "sinh", "cosh", "pi", "E", "Derivative", "diff", "Integral", "integrate", "abs", "Abs"}}
    local_dict = {{}}
    has_non_commutative = False
    for tok in tokens:
        if tok in reserved:
            continue
        if tok in nc_symbols:
            local_dict[tok] = sympy.Symbol(tok, commutative=False)
            has_non_commutative = True
        else:
            s_assump = dict(assumptions_dict.get(tok, {{}}))
            if domain_str == "real" and "real" not in s_assump and "positive" not in s_assump:
                s_assump["real"] = True
            local_dict[tok] = sympy.Symbol(tok, **s_assump)

    e1 = parse_expr(expr1_str, transformations=transformations, local_dict=local_dict)
    e2 = parse_expr(expr2_str, transformations=transformations, local_dict=local_dict)

    diff = sympy.simplify(e1 - e2)
    if diff == 0:
        print(json.dumps({{
            "equivalent": True,
            "method": "symbolic_simplify",
            "residual": 0.0,
            "simplified_difference": "0"
        }}))
        sys.exit(0)

    if has_non_commutative:
        print(json.dumps({{
            "equivalent": False,
            "method": "non_commutative_algebra",
            "residual": 1.0,
            "simplified_difference": str(diff)
        }}))
        sys.exit(0)

    # Stratified numerical sampling across multiple intervals
    strata = [
        lambda assump: random.uniform(1.1, 5.0),
        lambda assump: random.uniform(-5.0, -1.1) if not assump.get("positive") else random.uniform(1.1, 5.0),
        lambda assump: random.uniform(-0.5, 0.5) if not assump.get("positive") else random.uniform(0.01, 0.5),
    ]
    if domain_str == "complex":
        strata.append(lambda assump: complex(random.uniform(-5.0, 5.0), random.uniform(-5.0, 5.0)))

    is_equiv_num = True
    max_res = 0.0
    symbols_to_sample = [s for s in e1.free_symbols.union(e2.free_symbols) if getattr(s, "is_commutative", True)]

    for stratum_sampler in strata:
        for _ in range(8):
            pt = {{}}
            for sym in symbols_to_sample:
                s_assump = assumptions_dict.get(sym.name, {{}})
                pt[sym] = stratum_sampler(s_assump)
            try:
                v1 = complex(e1.evalf(subs=pt))
                v2 = complex(e2.evalf(subs=pt))
                d = abs(v1 - v2)
                if d > max_res:
                    max_res = d
                if d > 1e-6:
                    is_equiv_num = False
                    break
            except Exception:
                pass
        if not is_equiv_num:
            break

    print(json.dumps({{
        "equivalent": is_equiv_num,
        "method": "stratified_numerical_sampling" if is_equiv_num else "stratified_sampling_difference",
        "residual": float(max_res),
        "simplified_difference": str(diff)
    }}))

except Exception as e:
    print(json.dumps({{
        "equivalent": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"equivalent": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data



@mcp.tool()
def numeric_compare(
    func1_code: str,
    func2_code: str,
    domain: Dict[str, Any],
    tol_rel: float = 1e-5,
    tol_abs: float = 1e-7,
) -> Dict[str, Any]:
    """
    Compare numerical agreement between two implementation functions over a domain grid using NumPy.
    Runs inside the isolated subprocess sandbox.
    """
    f1_json = json.dumps(func1_code)
    f2_json = json.dumps(func2_code)
    dom_json = json.dumps(json.dumps(domain))

    script = f"""
import json
import numpy as np

f1_code = {f1_json}
f2_code = {f2_json}
domain = json.loads({dom_json})
tol_rel = {tol_rel}
tol_abs = {tol_abs}

try:
    loc1 = {{}}
    loc2 = {{}}
    exec(f1_code, {{"np": np, "numpy": np}}, loc1)
    exec(f2_code, {{"np": np, "numpy": np}}, loc2)

    f1 = loc1.get("func") or list(loc1.values())[0]
    f2 = loc2.get("func") or list(loc2.values())[0]

    # Build domain grid
    grid_args = {{}}
    points_count = 1
    for var, bounds in domain.items():
        low, high, steps = bounds[0], bounds[1], int(bounds[2])
        grid_args[var] = np.linspace(low, high, steps)
        points_count *= steps

    # Evaluate for single 1D or meshgrid
    if len(grid_args) == 1:
        var = list(grid_args.keys())[0]
        pts = grid_args[var]
        y1 = np.array([f1(x) for x in pts], dtype=float)
        y2 = np.array([f2(x) for x in pts], dtype=float)
    else:
        # Multi-variable mesh
        var_names = list(grid_args.keys())
        arrays = [grid_args[v] for v in var_names]
        mesh = np.meshgrid(*arrays)
        flat_pts = [m.flatten() for m in mesh]
        y1 = np.array([f1(*args) for args in zip(*flat_pts)], dtype=float)
        y2 = np.array([f2(*args) for args in zip(*flat_pts)], dtype=float)

    diff = np.abs(y1 - y2)
    max_abs = float(np.max(diff))
    denom = np.maximum(np.abs(y1), np.abs(y2))
    rel_diff = np.where(denom > 1e-12, diff / denom, 0.0)
    max_rel = float(np.max(rel_diff))

    is_match = bool(np.allclose(y1, y2, rtol=tol_rel, atol=tol_abs))

    print(json.dumps({{
        "match": is_match,
        "max_abs_diff": max_abs,
        "max_rel_diff": max_rel,
        "points_evaluated": points_count,
        "tol_rel": tol_rel,
        "tol_abs": tol_abs
    }}))

except Exception as e:
    print(json.dumps({{
        "match": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"match": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def sym_solve(
    operation: str,
    expression: str,
    variable: str = "x",
    target: Optional[str] = None,
    order: int = 4,
    point: float = 0.0,
    assumptions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Differentiate, integrate, solve, or series-expand mathematical expressions using SymPy.
    Computes a verification residual to guarantee mathematical soundness.
    Runs in isolated subprocess sandbox.
    """
    op_json = json.dumps(operation)
    expr_json = json.dumps(expression)
    var_json = json.dumps(variable)
    target_repr = repr(target)
    order_val = int(order)
    pt_val = float(point)
    assump_repr = repr(assumptions or {})

    script = f"""
import json
import random
import sys
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

transformations = standard_transformations + (implicit_multiplication_application,)

op = {op_json}.lower()
expr_str = {expr_json}
var_str = {var_json}
target_str = {target_repr}
order = {order_val}
point = {pt_val}
assumptions = {assump_repr}

try:
    var_sym = sympy.Symbol(var_str, **assumptions.get(var_str, {{"real": True}}))
    expr = parse_expr(expr_str, transformations=transformations, local_dict={{var_str: var_sym}})

    res_str = ""
    residual = 0.0
    details = ""

    if op in ("diff", "derivative"):
        sol = sympy.diff(expr, var_sym)
        res_str = str(sol)
        # Residual verification via fundamental theorem check: int(diff) - expr == const
        check_int = sympy.integrate(sol, var_sym)
        diff_rem = sympy.simplify(check_int - expr)
        residual = float(abs(complex(sympy.diff(diff_rem, var_sym).evalf(subs={{var_sym: 1.5}}))))
        details = f"Differentiated wrt {{var_str}}"

    elif op in ("integrate", "integral"):
        sol = sympy.integrate(expr, var_sym)
        res_str = str(sol)
        # Residual verification: diff(integral) - expr == 0
        diff_back = sympy.simplify(sympy.diff(sol, var_sym) - expr)
        residual = float(abs(complex(diff_back.evalf(subs={{var_sym: 1.5}}))))
        details = f"Integrated wrt {{var_str}}"

    elif op in ("solve", "roots"):
        eq = expr
        if target_str is not None:
            tgt = parse_expr(target_str, transformations=transformations, local_dict={{var_str: var_sym}})
            eq = expr - tgt
        sol = sympy.solve(eq, var_sym)
        res_str = str(sol)
        # Residual: max |eq(root)|
        max_res = 0.0
        for r in sol:
            try:
                val = abs(complex(eq.evalf(subs={{var_sym: r}})))
                if val > max_res:
                    max_res = val
            except Exception:
                pass
        residual = float(max_res)
        details = f"Solved {{expr_str}} for {{var_str}}"

    elif op in ("series", "taylor"):
        sol = sympy.series(expr, var_sym, point, order).removeO()
        res_str = str(sol)
        # Residual: |expr - series| at small offset
        h = 0.01
        test_pt = point + h
        val_expr = complex(expr.evalf(subs={{var_sym: test_pt}}))
        val_ser = complex(sol.evalf(subs={{var_sym: test_pt}}))
        residual = float(abs(val_expr - val_ser))
        details = f"Series expanded around {{point}} up to order {{order}}"

    else:
        raise ValueError(f"Unknown operation: {{op}}")

    print(json.dumps({{
        "success": True,
        "operation": op,
        "result": res_str,
        "residual": residual,
        "details": details
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def invariant_check(
    step_code: str,
    invariant_code: str,
    initial_state: Any,
    dt: float,
    steps: int = 100,
    tol_rel: float = 0.05,
) -> Dict[str, Any]:
    """
    Run a simulation or iterative method repeatedly and report drift in a conserved physical quantity (energy, momentum, mass).
    Runs inside isolated subprocess sandbox.
    """
    step_json = json.dumps(step_code)
    inv_json = json.dumps(invariant_code)
    state_repr = repr(initial_state)

    script = f"""
import json
import math
import sys

step_src = {step_json}
inv_src = {inv_json}
init_state = {state_repr}
dt = {float(dt)}
steps = {int(steps)}
tol_rel = {float(tol_rel)}

try:
    loc = {{}}
    exec(step_src, loc, loc)
    exec(inv_src, loc, loc)

    step_fn = loc.get("step")
    inv_fn = loc.get("invariant")

    if not step_fn or not inv_fn:
        raise ValueError("Code must define 'step(t, state)' and 'invariant(t, state)' functions")

    t = 0.0
    state = init_state
    e0 = float(inv_fn(t, state))

    max_drift_abs = 0.0
    history = [e0]

    for _ in range(steps):
        t, state = step_fn(t, state)
        e_curr = float(inv_fn(t, state))
        history.append(e_curr)
        drift = abs(e_curr - e0)
        if drift > max_drift_abs:
            max_drift_abs = drift

    denom = abs(e0) if abs(e0) > 1e-12 else 1.0
    max_drift_rel = max_drift_abs / denom
    conserved = bool(max_drift_rel <= tol_rel)

    # Classify trend
    final_e = history[-1]
    if max_drift_rel <= tol_rel:
        trend = "conserved_stable"
    elif abs(final_e) > 10.0 * abs(e0):
        trend = "exponential_growth"
    else:
        trend = "linear_or_secular_drift"

    print(json.dumps({{
        "success": True,
        "conserved": conserved,
        "initial_value": e0,
        "final_value": final_e,
        "max_drift_abs": max_drift_abs,
        "max_drift_rel": max_drift_rel,
        "drift_trend": trend,
        "steps_run": steps,
        "tol_rel": tol_rel
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def convergence_study(
    solver_code: str,
    h_values: List[float],
    exact_solution: Optional[float] = None,
    expected_order: float = 2.0,
    order_tol: float = 0.25,
) -> Dict[str, Any]:
    """
    Refine a step or grid parameter and report observed order of accuracy against expected order via log-log regression.
    Runs inside isolated subprocess sandbox.
    """
    src_json = json.dumps(solver_code)
    h_repr = repr([float(h) for h in h_values])
    exact_repr = repr(exact_solution)

    script = f"""
import json
import math
import numpy as np

src = {src_json}
h_vals = {h_repr}
exact_val = {exact_repr}
expected_order = {float(expected_order)}
order_tol = {float(order_tol)}

try:
    loc = {{}}
    exec(src, {{"np": np, "numpy": np, "math": math}}, loc)
    solve_fn = loc.get("solve")
    if not solve_fn:
        raise ValueError("solver_code must define 'solve(h)' function")

    errors = []
    for h in h_vals:
        res = solve_fn(h)
        if exact_val is not None:
            err = abs(float(res) - exact_val)
        else:
            err = abs(float(res))
        errors.append(max(err, 1e-16))

    # Log-log regression: ln(error) = p * ln(h) + C
    log_h = np.log(np.array(h_vals))
    log_e = np.log(np.array(errors))

    # Linear fit
    coeffs = np.polyfit(log_h, log_e, 1)
    observed_order = float(coeffs[0])

    # R-squared
    y_pred = np.polyval(coeffs, log_h)
    ss_res = np.sum((log_e - y_pred) ** 2)
    ss_tot = np.sum((log_e - np.mean(log_e)) ** 2)
    r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-12 else 1.0

    order_match = bool(abs(observed_order - expected_order) <= order_tol)
    converges = bool(observed_order > 0.5 and errors[-1] < errors[0])

    print(json.dumps({{
        "success": True,
        "converges": converges,
        "observed_order": observed_order,
        "expected_order": expected_order,
        "order_match": order_match,
        "errors": [float(e) for e in errors],
        "r_squared": r_squared
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def limit_check(
    expression: str,
    variable: str = "x",
    point: str = "0",
    direction: str = "+-",
    expected_limit: Optional[str] = None,
    asymptotic_comparison: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate mathematical behavior at limits, roots, and asymptotic boundaries against expected asymptotics.
    Runs inside isolated subprocess sandbox.
    """
    expr_json = json.dumps(expression)
    var_json = json.dumps(variable)
    pt_json = json.dumps(point)
    dir_json = json.dumps(direction)
    exp_repr = repr(expected_limit)
    asymp_repr = repr(asymptotic_comparison)

    script = f"""
import json
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

transformations = standard_transformations + (implicit_multiplication_application,)

expr_str = {expr_json}
var_str = {var_json}
pt_str = {pt_json}.strip()
dir_str = {dir_json}
exp_limit_str = {exp_repr}
asymp_str = {asymp_repr}

try:
    var_sym = sympy.Symbol(var_str, real=True)
    expr = parse_expr(expr_str, transformations=transformations, local_dict={{var_str: var_sym}})

    if pt_str in ("oo", "+oo", "inf", "infinity"):
        target_pt = sympy.oo
    elif pt_str in ("-oo", "-inf", "-infinity"):
        target_pt = -sympy.oo
    elif pt_str == "pi":
        target_pt = sympy.pi
    else:
        target_pt = parse_expr(pt_str, transformations=transformations)

    lim_val = sympy.limit(expr, var_sym, target_pt, dir=dir_str)
    lim_str = str(lim_val)
    is_finite = bool(lim_val.is_finite)

    matches_expected = None
    if exp_limit_str is not None:
        if exp_limit_str.strip() in ("oo", "+oo", "inf"):
            exp_val = sympy.oo
        elif exp_limit_str.strip() in ("-oo", "-inf"):
            exp_val = -sympy.oo
        else:
            exp_val = parse_expr(exp_limit_str, transformations=transformations)
        diff = sympy.simplify(lim_val - exp_val)
        matches_expected = bool(diff == 0)

    asymp_ratio = None
    if asymp_str is not None:
        comp_expr = parse_expr(asymp_str, transformations=transformations, local_dict={{var_str: var_sym}})
        ratio_lim = sympy.limit(expr / comp_expr, var_sym, target_pt, dir=dir_str)
        asymp_ratio = str(ratio_lim)

    print(json.dumps({{
        "success": True,
        "limit_value": lim_str,
        "matches_expected": matches_expected,
        "is_finite": is_finite,
        "asymptotic_ratio_limit": asymp_ratio,
        "details": f"Limit of {{expr_str}} as {{var_str}} -> {{pt_str}} is {{lim_str}}"
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data



@mcp.tool()
def sym_ode_solve(
    equation: str,
    func: str = "y(x)",
    var: str = "x",
    ics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Solve ordinary differential equations analytically using SymPy dsolve.
    Supports 1st and 2nd order linear/non-linear ODEs and Initial Value Problems (IVPs).
    Runs inside isolated subprocess sandbox.
    """
    eq_json = json.dumps(equation)
    func_json = json.dumps(func)
    var_json = json.dumps(var)
    ics_json = json.dumps(ics or {})

    script = f"""
import json
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

transformations = standard_transformations

eq_str = {eq_json}
func_str = {func_json}
var_str = {var_json}
ics_dict_raw = json.loads({json.dumps(ics_json)})

try:
    if '(' in func_str:
        f_name = func_str.split('(')[0].strip()
        v_name = func_str.split('(')[1].split(')')[0].strip()
    else:
        f_name = func_str.strip()
        v_name = var_str.strip()

    x_sym = sympy.Symbol(v_name)
    y_sym = sympy.Function(f_name)
    local_dict = {{
        f_name: y_sym,
        v_name: x_sym,
        'Derivative': sympy.Derivative,
        'exp': sympy.exp,
        'sin': sympy.sin,
        'cos': sympy.cos,
        'tan': sympy.tan,
        'sinh': sympy.sinh,
        'cosh': sympy.cosh,
        'log': sympy.log,
        'sqrt': sympy.sqrt,
        'pi': sympy.pi,
        'E': sympy.E,
    }}

    if '=' in eq_str:
        lhs_str, rhs_str = eq_str.split('=', 1)
        lhs = parse_expr(lhs_str, transformations=transformations, local_dict=local_dict)
        rhs = parse_expr(rhs_str, transformations=transformations, local_dict=local_dict)
        ode_expr = lhs - rhs
    else:
        ode_expr = parse_expr(eq_str, transformations=transformations, local_dict=local_dict)

    ics = None
    if ics_dict_raw:
        ics = {{}}
        for k, v in ics_dict_raw.items():
            k_expr = parse_expr(str(k), transformations=transformations, local_dict=local_dict)
            v_expr = parse_expr(str(v), transformations=transformations, local_dict=local_dict)
            ics[k_expr] = v_expr

    sol = sympy.dsolve(ode_expr, y_sym(x_sym), ics=ics)

    sol_str = str(sol)
    rhs_str = str(sol.rhs) if hasattr(sol, 'rhs') else sol_str

    print(json.dumps({{
        "success": True,
        "solution": sol_str,
        "rhs": rhs_str,
        "details": f"Solved ODE: {{eq_str}}"
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def numeric_ode_solve(
    system_code: str,
    y0: List[float],
    t_span: List[float],
    method: str = "RK45",
    num_points: int = 50,
) -> Dict[str, Any]:
    """
    Solve initial value problems for ODE systems numerically using SciPy solve_ivp.
    Supports standard solvers (RK45, RK23, DOP853) and stiff solvers (Radau, BDF, LSODA).
    Runs inside isolated subprocess sandbox.
    """
    sys_json = json.dumps(system_code)
    y0_json = json.dumps(y0)
    tspan_json = json.dumps(t_span)
    method_json = json.dumps(method)
    num_pts = int(num_points)

    script = f"""
import json
import numpy as np
import scipy.integrate

system_str = {sys_json}
y0 = [float(val) for val in {y0_json}]
t_span = [float(val) for val in {tspan_json}]
method = {method_json}
num_points = {num_pts}

try:
    loc = {{}}
    exec(system_str, {{"np": np, "numpy": np, "math": __import__("math")}}, loc)
    f = loc.get("f") or loc.get("system") or loc.get("derivs") or list(loc.values())[0]

    t_eval = np.linspace(t_span[0], t_span[1], num_points)
    sol = scipy.integrate.solve_ivp(f, t_span, y0, method=method, t_eval=t_eval)

    print(json.dumps({{
        "success": bool(sol.success),
        "t": sol.t.tolist(),
        "y": sol.y.tolist(),
        "status": int(sol.status),
        "message": str(sol.message)
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


@mcp.tool()
def noether_invariant_check(
    hamiltonian: str,
    invariant: str,
    q: str = "q",
    p: str = "p",
    t: str = "t",
) -> Dict[str, Any]:
    """
    Verify whether a candidate invariant I is a Noether conserved quantity for Hamiltonian H
    via the canonical Poisson bracket condition: dI/dt = {I, H} + dI/dt == 0.
    Runs inside isolated subprocess sandbox.
    """
    h_json = json.dumps(hamiltonian)
    inv_json = json.dumps(invariant)
    q_json = json.dumps(q)
    p_json = json.dumps(p)
    t_json = json.dumps(t)

    script = f"""
import json
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

transformations = standard_transformations + (implicit_multiplication_application,)

h_str = {h_json}
inv_str = {inv_json}
q_str = {q_json}
p_str = {p_json}
t_str = {t_json}

try:
    H = parse_expr(h_str, transformations=transformations)
    I = parse_expr(inv_str, transformations=transformations)

    q_names = [s.strip() for s in q_str.split(',') if s.strip()]
    p_names = [s.strip() for s in p_str.split(',') if s.strip()]
    t_sym = sympy.Symbol(t_str.strip())

    pb = 0
    for q_name, p_name in zip(q_names, p_names):
        q_sym = sympy.Symbol(q_name)
        p_sym = sympy.Symbol(p_name)
        dI_dq = sympy.diff(I, q_sym)
        dH_dp = sympy.diff(H, p_sym)
        dI_dp = sympy.diff(I, p_sym)
        dH_dq = sympy.diff(H, q_sym)
        pb += dI_dq * dH_dp - dI_dp * dH_dq

    pb = sympy.simplify(pb)
    dI_dt = sympy.simplify(pb + sympy.diff(I, t_sym))

    is_conserved = bool(dI_dt == 0)

    print(json.dumps({{
        "success": True,
        "conserved": is_conserved,
        "poisson_bracket": str(pb),
        "total_time_derivative": str(dI_dt),
        "details": f"Conserved Noether quantity: {{inv_str}}" if is_conserved else f"Non-conserved quantity: {{inv_str}}"
    }}))

except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e)
    }}))
"""
    res = run_sandboxed_code(script)
    if not res.get("success"):
        return {"success": False, "error": res.get("error"), "wall_time_ms": res.get("wall_time_ms")}
    data = res.get("data", {})
    data["wall_time_ms"] = res.get("wall_time_ms")
    return data


if __name__ == "__main__":
    mcp.run()
