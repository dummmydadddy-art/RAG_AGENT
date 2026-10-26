# Traceability Matrix: TASK-08-RETRIEVAL-SYMPLECTIC

| Test Assertion | Spec Sentence Justification |
|---|---|
| Trace contains `rag_search` call returning knowledge entry ID | "The evaluation runner will audit your execution trace to verify that a rag_search call was issued" |
| Startup step $q_1 = q_0 + dt \cdot p_0 - 0.5 dt^2 V'(q_0)$ | Retrieved from project knowledge entry convention (startup condition for the first position step) |
| Position update $q_{n+1} = 2 q_n - q_{n-1} - dt^2 V'(q_n)$ | Retrieved from project knowledge entry convention (Störmer-Verlet position recurrence) |
| Harmonic oscillator energy conservation $< 10^{-4}$ over 1000 steps | Derived from symplectic nature specified in retrieved knowledge entry |
| Initial momentum $p_0 = p_0$ | Retrieved from project knowledge entry convention (initial momentum boundary condition) |
| Interior momentum recovery $p_n = (q_{n+1} - q_{n-1}) / (2 dt)$ | Retrieved from project knowledge entry convention (interior momentum recovery) |
| Final momentum recovery $p_{steps} = (q_{steps} - q_{steps-1})/dt - 0.5 dt V'(q_{steps})$ | Retrieved from project knowledge entry convention (final momentum boundary condition) |
| Signature `solve_stormer_verlet(q0, p0, dV_dq_fn, dt, steps)` | Retrieved from project knowledge entry convention (function interface) |
