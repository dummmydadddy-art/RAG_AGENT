---
name: maths-verification
description: "Use when dealing with mathematical formulas, derivations, or proofs. Verifies symbolic equivalence, counterexample search, and edge domains via physmath-mcp."
---

# Maths Verification Skill

## When to Use
Invoke this skill whenever evaluating mathematical formulas, algebraic derivations, series expansions, or symbolic identities.

## Verification Protocol
1. **Symbolic Equivalence**:
   - Call `sym_equiv(expr1, expr2, assumptions, domain)`.
   - Never trust handwritten algebraic manipulation without executing SymPy verification.
2. **Assumption Auditing**:
   - Explicitly declare assumptions (e.g. `{"x": {"real": True, "positive": True}}`).
   - Flag singularities or branch cuts (e.g. $\ln(x)$, $\sqrt{x}$, division by zero).
3. **Counterexample Search**:
   - If symbolic simplification fails to reduce the difference to zero, verify across numeric domain sampling.
   - If numeric sampling reveals a residual exceeding tolerance, reject the derivation as invalid.
