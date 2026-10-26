# Benchmark Results: Self-Learning Coding Agent

*Official record of evaluation runs across development phases.*

---

## Phase 1: Baseline Evaluation (Single Agent, Lessons Off)

- **Execution Date**: 26 October 2026
- **Surface & Platform**: Google Antigravity Desktop App v44.4.3 / CLI `agy` v1.4.7 on Windows 11
- **Evaluation Configuration**:
  - **Mode**: `single` (Lead Orchestrator with specialized subagent roles)
  - **Lessons Mode**: `off` (Clean baseline before lesson learning loop in Phase 2)
  - **Repetitions per Task (`--repeat`)**: 3 (Overall pass requires $\ge 2/3$ passing runs)
  - **Retrieval Mode (Pinned)**: `hybrid_rrf_pinned`
  - **Backend Identity**: `SqliteVectorBackend(backend/storage/vectors.sqlite)`
  - **Store Baseline SHA-256**: `302cc165dd011d4850f95cabc33f75d8cb028d1c7b3df6fb6c2bfd4d8f57825e`
  - **Hidden Checks**: Encrypted in `evals/hidden_evals.enc` (AES Fernet + PBKDF2-HMAC-SHA256)
  - **Canary Protection**: `CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456` (0 leaks detected)

### Summary Metrics

| Metric | Result | Target / Threshold | Status |
|---|---|---|---|
| **Overall Pass Rate** | **8 / 8 (100.0%)** | $\ge 4 / 8$ ($50.0\%$) | **Exceeded** |
| **Total Test Executions** | **24 / 24 (100.0%)** | $\ge 16 / 24$ | **Exceeded** |
| **Training Tasks Pass Rate** | **6 / 6 (100.0%)** | $\ge 3 / 6$ | **Exceeded** |
| **Held-Out Tasks Pass Rate** | **2 / 2 (100.0%)** | $\ge 1 / 2$ | **Exceeded** |
| **Mean TDD Iterations** | **1.0** | $\le 4.0$ (Budget cap) | **Met** |
| **Knowledge Retrieval** | **Verified** | Mandatory on Task 08 | **Met** |

---

### Detailed Task Breakdown

| Task ID | Title | Category | Held-Out | Overall Status | Runs Passed | Target File |
|---|---|---|---|---|---|---|
| `TASK-01-CODE-LRU` | Thread-safe LRU Cache with Expiration TTL | `pure_coding` | No | **PASS** | 3 / 3 | `src/lru_cache.py` |
| `TASK-02-CODE-GRAPH` | Topological Sorter with Cycle Detection | `pure_coding` | No | **PASS** | 3 / 3 | `src/dependency_graph.py` |
| `TASK-03-MATH-HALLEY` | Halley's Root Finder with Bracket Fallback | `pure_maths` | No | **PASS** | 3 / 3 | `src/root_finder.py` |
| `TASK-04-MATH-QUATERNION` | 3D Rotation Quaternion with SLERP | `pure_maths` | No | **PASS** | 3 / 3 | `src/quaternion.py` |
| `TASK-05-PHYS-KEPLER` | 2D Kepler Orbit Symplectic Integrator | `physics_numerics` | No | **PASS** | 3 / 3 | `src/kepler_solver.py` |
| `TASK-06-PHYS-HEAT-1D` | 1D Transient Heat via Crank-Nicolson | `physics_numerics` | **Yes** | **PASS** | 3 / 3 | `src/heat_solver.py` |
| `TASK-07-MULTI-EVENT-BUS` | Async Event Bus with DLQ and Middleware | `multi_module` | **Yes** | **PASS** | 3 / 3 | `src/event_system/bus.py` |
| `TASK-08-RETRIEVAL-SYMPLECTIC` | Symplectic Störmer-Verlet Integrator | `retrieval_dependent` | No | **PASS** | 3 / 3 | `src/integrator.py` |

---

### Key Verification Highlights

1. **Pure Coding (`TASK-01`, `TASK-02`)**:
   - `LRUCache` enforces strict monotonic clock injection (`time_fn`) for deterministic TTL validation without sleep calls; thread-safe under concurrent multi-threaded execution via `RLock`.
   - `DependencyGraph` achieves deterministic tie-breaking via min-heap priority queue; detects elementary cycles cyclically normalized to the lexicographical minimum node.
2. **Pure Mathematics (`TASK-03`, `TASK-04`)**:
   - `find_root_halley` demonstrates cubic convergence order for smooth roots; successfully falls back to bracket bisection when derivatives or denominators vanish.
   - `Quaternion` implements Hamilton product non-commutativity, left/right scalar multiplications, rotation matrix conversion, and SLERP interpolation along the shortest geodesic arc.
3. **Physics & Numerics (`TASK-05`, `TASK-06`)**:
   - `solve_kepler_orbit` uses Velocity Verlet symplectic stepping to conserve mechanical energy and angular momentum within relative error $< 10^{-4}$ over 10 full orbital periods.
   - `solve_heat_1d_crank_nicolson` solves the 1D transient heat equation via the unconditionally stable Crank-Nicolson method with Thomas algorithm $O(nx)$ tridiagonal elimination; analytical sine decay matches within $10^{-3}$.
4. **Multi-Module Architecture (`TASK-07`)**:
   - Asynchronous event bus across `events.py`, `dead_letter.py`, and `bus.py` supporting wildcard subscriptions (`*`), FIFO middleware pipelines, concurrent dispatch with `asyncio.gather`, and automated DLQ routing on retry exhaustion.
5. **Retrieval-Dependent Synthesis (`TASK-08`)**:
   - Evaluator audited execution trace to verify that `rag_search` was called and successfully returned document `stormer_verlet_integrator_conventions_v1`.
   - Implemented exact project conventions: $q_1$ startup formula, Störmer-Verlet coordinate recurrence, and centered difference momentum recovery with half-step acceleration correction.

---

### Exit Criteria Assessment (Phase 1)

Per `docs/ARCHITECTURE.md` Section 8:
- [x] **8 benchmark tasks run through eval harness with `--mode single --lessons off`**: Completed.
- [x] **Baseline pass rate recorded in `docs/BENCHMARK_RESULTS.md`**: Completed (**8/8, 100%**).
- [x] **At least 4 of 8 tasks pass on the baseline run**: Exceeded (**8/8 pass**).
- [x] **Separated held-out tasks reporting**: Completed (**2/2 held-out pass**).
- [x] **Store hygiene and snapshot SHA-256 recorded**: Completed.
- [x] **Trace files audit retrieval**: Completed.
