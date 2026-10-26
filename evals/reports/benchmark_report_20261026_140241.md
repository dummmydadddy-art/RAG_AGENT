# Benchmark Evaluation Report — 20261026_140241

- **Execution Mode**: `single`
- **Lessons Mode**: `off`
- **Repetitions per Task (`--repeat`)**: `3`
- **Backend Identity**: `SqliteVectorBackend(backend/storage/vectors.sqlite)`
- **Retrieval Mode (Pinned)**: `hybrid_rrf_pinned`
- **Store Baseline SHA-256**: `302cc165dd011d4850f95cabc33f75d8cb028d1c7b3df6fb6c2bfd4d8f57825e`

## Separated Group Metrics (R8)
### 1. Training Tasks (Held-Out: False)
- **Pass Rate**: **6/6 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 2. Held-Out Tasks (Held-Out: True)
- **Pass Rate**: **2/2 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

## Detailed Task Summary
| Task ID | Title | Category | Held-Out | Overall Status | Runs Passed | Mean Time (s) |
|---|---|---|---|---|---|---|
| `TASK-01-CODE-LRU` | Thread-safe LRU Cache with Expiration TTL | `pure_coding` | No | **PASS** | 3/3 | 0.0s |
| `TASK-02-CODE-GRAPH` | Topological Sorter with Cycle Detection | `pure_coding` | No | **PASS** | 3/3 | 0.0s |
| `TASK-03-MATH-HALLEY` | Halley's Root Finder with Bracket Fallback | `pure_maths` | No | **PASS** | 3/3 | 0.0s |
| `TASK-04-MATH-QUATERNION` | 3D Rotation Quaternion with SLERP | `pure_maths` | No | **PASS** | 3/3 | 0.0s |
| `TASK-05-PHYS-KEPLER` | 2D Kepler Orbit Symplectic Integrator | `physics_numerics` | No | **PASS** | 3/3 | 0.0s |
| `TASK-06-PHYS-HEAT-1D` | 1D Transient Heat Conduction via Crank-Nicolson | `physics_numerics` | Yes | **PASS** | 3/3 | 0.0s |
| `TASK-07-MULTI-EVENT-BUS` | Asynchronous Event Bus with DLQ and Middleware | `multi_module` | Yes | **PASS** | 3/3 | 0.0s |
| `TASK-08-RETRIEVAL-SYMPLECTIC` | Symplectic Störmer-Verlet Integrator via Project Conventions | `retrieval_dependent` | No | **PASS** | 3/3 | 0.0s |

## Per-Run Breakdown

### `TASK-01-CODE-LRU`: Thread-safe LRU Cache with Expiration TTL
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-02-CODE-GRAPH`: Topological Sorter with Cycle Detection
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-03-MATH-HALLEY`: Halley's Root Finder with Bracket Fallback
- **Category**: pure_maths | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-04-MATH-QUATERNION`: 3D Rotation Quaternion with SLERP
- **Category**: pure_maths | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-05-PHYS-KEPLER`: 2D Kepler Orbit Symplectic Integrator
- **Category**: physics_numerics | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-06-PHYS-HEAT-1D`: 1D Transient Heat Conduction via Crank-Nicolson
- **Category**: physics_numerics | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-07-MULTI-EVENT-BUS`: Asynchronous Event Bus with DLQ and Middleware
- **Category**: multi_module | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-08-RETRIEVAL-SYMPLECTIC`: Symplectic Störmer-Verlet Integrator via Project Conventions
- **Category**: retrieval_dependent | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)