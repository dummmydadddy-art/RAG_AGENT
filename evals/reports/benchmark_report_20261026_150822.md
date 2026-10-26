# Benchmark Evaluation Report — 20261026_150822

- **Execution Mode**: `single`
- **Lessons Mode**: `on`
- **Repetitions per Task (`--repeat`)**: `3`
- **Backend Identity**: `SqliteVectorBackend(backend/storage/vectors.sqlite)`
- **Retrieval Mode (Pinned)**: `hybrid_rrf_pinned`
- **Store Baseline SHA-256**: `6ba98d6f1cd91edf0d33a92565786885339bf47586c4354a9c371ec7a7f4db10`

## Separated Group Metrics (R8)
### 1. Training Tasks (Held-Out: False)
- **Pass Rate**: **20/20 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 2. Held-Out Tasks (Held-Out: True)
- **Pass Rate**: **4/4 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 3. Hard Subset Tasks (Complex Multi-Module & Coupled Physics)
- **Pass Rate**: **7/7 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

## Detailed Task Summary
| Task ID | Title | Category | Held-Out | Overall Status | Runs Passed | Mean Time (s) | Lessons Retrieved |
|---|---|---|---|---|---|---|---|
| `TASK-01-CODE-LRU` | Thread-safe LRU Cache with Expiration TTL | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-02-CODE-GRAPH` | Topological Sorter with Cycle Detection | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-03-MATH-HALLEY` | Halley's Root Finder with Bracket Fallback | `pure_maths` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-04-MATH-QUATERNION` | 3D Rotation Quaternion with SLERP | `pure_maths` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-05-PHYS-KEPLER` | 2D Kepler Orbit Symplectic Integrator | `physics_numerics` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-06-PHYS-HEAT-1D` | 1D Transient Heat Conduction via Crank-Nicolson | `physics_numerics` | Yes | **PASS** | 3/3 | 0.0s | None |
| `TASK-07-MULTI-EVENT-BUS` | Asynchronous Event Bus with DLQ and Middleware | `multi_module` | Yes | **PASS** | 3/3 | 0.0s | None |
| `TASK-08-RETRIEVAL-SYMPLECTIC` | Symplectic Störmer-Verlet Integrator via Project Conventions | `retrieval_dependent` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-09-CODE-TRIE` | Prefix Trie with Autocomplete and Longest Prefix | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-10-CODE-TOKEN-BUCKET` | Thread-safe Token Bucket Rate Limiter | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-11-CODE-RING-BUFFER` | Circular Ring Buffer with Overwrite Policy | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-12-CODE-INTERVAL-TREE` | Augmented Interval Tree for Range Stabbing | `pure_coding` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-13-MATH-POLYNOMIAL` | Chebyshev Polynomial Root Finder via Companion Matrix | `pure_maths` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-14-MATH-FFT` | Cooley-Tukey Radix-2 1D Fast Fourier Transform | `pure_maths` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-15-MATH-SIMPLEX` | Two-Phase Simplex Algorithm for Linear Programming | `pure_maths` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-16-PHYS-PENDULUM` | Double Pendulum Chaotic Dynamics via Runge-Kutta RK4 | `physics_numerics` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-17-PHYS-WAVE-1D` | 1D Acoustic Wave PDE Solver with Absorbing Boundaries | `physics_numerics` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-18-PHYS-LORENZ` | Lorenz Attractor Simulation and Lyapunov Exponent Estimation | `physics_numerics` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-19-MULTI-RAFT-KV` | Distributed In-Memory Raft Consensus KV Store | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-20-MULTI-PIPELINE` | Streaming Dataflow Pipeline with Tumbling Windows | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-21-MULTI-QUERY-ENGINE` | In-Memory Columnar Relational Query Engine | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-22-MULTI-PLUGIN-ARCH` | Pluggable Microkernel Architecture with Sandboxing | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-23-HELDOUT-SCHEDULER` | Real-Time Preemptive Task Scheduler with Earliest Deadline First | `multi_module` | Yes | **PASS** | 3/3 | 0.0s | None |
| `TASK-24-HELDOUT-DIFFUSION-2D` | 2D Reaction-Diffusion Gray-Scott Pattern Simulator | `physics_numerics` | Yes | **PASS** | 3/3 | 0.0s | None |

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

### `TASK-09-CODE-TRIE`: Prefix Trie with Autocomplete and Longest Prefix
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-10-CODE-TOKEN-BUCKET`: Thread-safe Token Bucket Rate Limiter
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-11-CODE-RING-BUFFER`: Circular Ring Buffer with Overwrite Policy
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-12-CODE-INTERVAL-TREE`: Augmented Interval Tree for Range Stabbing
- **Category**: pure_coding | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-13-MATH-POLYNOMIAL`: Chebyshev Polynomial Root Finder via Companion Matrix
- **Category**: pure_maths | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-14-MATH-FFT`: Cooley-Tukey Radix-2 1D Fast Fourier Transform
- **Category**: pure_maths | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-15-MATH-SIMPLEX`: Two-Phase Simplex Algorithm for Linear Programming
- **Category**: pure_maths | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-16-PHYS-PENDULUM`: Double Pendulum Chaotic Dynamics via Runge-Kutta RK4
- **Category**: physics_numerics | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-17-PHYS-WAVE-1D`: 1D Acoustic Wave PDE Solver with Absorbing Boundaries
- **Category**: physics_numerics | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-18-PHYS-LORENZ`: Lorenz Attractor Simulation and Lyapunov Exponent Estimation
- **Category**: physics_numerics | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-19-MULTI-RAFT-KV`: Distributed In-Memory Raft Consensus KV Store
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-20-MULTI-PIPELINE`: Streaming Dataflow Pipeline with Tumbling Windows
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-21-MULTI-QUERY-ENGINE`: In-Memory Columnar Relational Query Engine
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-22-MULTI-PLUGIN-ARCH`: Pluggable Microkernel Architecture with Sandboxing
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-23-HELDOUT-SCHEDULER`: Real-Time Preemptive Task Scheduler with Earliest Deadline First
- **Category**: multi_module | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)

### `TASK-24-HELDOUT-DIFFUSION-2D`: 2D Reaction-Diffusion Gray-Scott Pattern Simulator
- **Category**: physics_numerics | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
  - Run 2: **PASS** (0.0s)
  - Run 3: **PASS** (0.0s)