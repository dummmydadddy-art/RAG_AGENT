import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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
        target = 1.0 * ureg(target_unit_str)
        try:
            eval_result.to(target.units)
            compatible = True
            details = f"Consistent and matches target unit {{target_unit_str}}"
        except pint.DimensionalityError as de:
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
) -> Dict[str, Any]:
    """
    Verify symbolic equivalence between two mathematical expressions using SymPy.
    Performs simplification on (expr1 - expr2) with numerical sampling fallback.
    """
    e1_json = json.dumps(expr1)
    e2_json = json.dumps(expr2)
    assump_json = json.dumps(json.dumps(assumptions or {}))
    dom_json = json.dumps(domain)

    script = f"""
import json
import random
import sys
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

expr1_str = {e1_json}
expr2_str = {e2_json}
assumptions_dict = json.loads({assump_json})
domain_str = {dom_json}

transformations = standard_transformations + (implicit_multiplication_application,)

try:
    # Collect symbols
    e1_sym = parse_expr(expr1_str, transformations=transformations)
    e2_sym = parse_expr(expr2_str, transformations=transformations)
    
    all_syms = e1_sym.free_symbols.union(e2_sym.free_symbols)
    
    # Re-create symbols with assumptions if specified
    subs_map = {{}}
    for s in all_syms:
        s_name = s.name
        s_assump = assumptions_dict.get(s_name, {{}})
        if domain_str == "real" and "real" not in s_assump:
            s_assump["real"] = True
        subs_map[s] = sympy.Symbol(s_name, **s_assump)

    e1_sub = e1_sym.subs(subs_map)
    e2_sub = e2_sym.subs(subs_map)

    diff = sympy.simplify(e1_sub - e2_sub)
    if diff == 0:
        print(json.dumps({{
            "equivalent": True,
            "method": "symbolic_simplify",
            "residual": 0.0,
            "simplified_difference": "0"
        }}))
        sys.exit(0)

    # Numerical sampling fallback across 20 random points
    is_equiv_num = True
    max_res = 0.0
    for _ in range(20):
        pt = {{sym: random.uniform(1.1, 5.0) for sym in subs_map.values()}}
        v1 = complex(e1_sub.evalf(subs=pt))
        v2 = complex(e2_sub.evalf(subs=pt))
        diff_val = abs(v1 - v2)
        if diff_val > max_res:
            max_res = diff_val
        if diff_val > 1e-7:
            is_equiv_num = False
            break

    print(json.dumps({{
        "equivalent": is_equiv_num,
        "method": "numerical_sampling" if is_equiv_num else "symbolic_difference",
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


if __name__ == "__main__":
    mcp.run()
