# Task Specification: Symplectic Störmer-Verlet Integrator via Project Conventions

## 1. Scope & Directives
Implement the numerical integrator in `src/integrator.py`.

### Mandatory Knowledge Retrieval Requirement
- You MUST follow this project's exact Hamiltonian integrator conventions.
- Do NOT assume formulas or coordinate conventions from memory or parametric recall.
- **Action**: Query the RAG engine using `rag_search` on the `knowledge` collection for project integrator conventions to retrieve:
  1. The function signature and parameter validations.
  2. The exact coordinate and momentum conventions ($q$ vs $p$).
  3. The two-step coordinate recursion formula.
  4. The startup step for the first position $q_1$.
  5. The momentum recovery conventions for boundary and interior points.
- The evaluation runner will audit your execution trace to verify that a `rag_search` call was issued and successfully returned the project's integrator conventions knowledge document.
