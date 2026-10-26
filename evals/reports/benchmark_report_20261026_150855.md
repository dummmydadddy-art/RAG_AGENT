# Benchmark Evaluation Report — 20261026_150855

- **Execution Mode**: `team`
- **Lessons Mode**: `off`
- **Repetitions per Task (`--repeat`)**: `3`
- **Backend Identity**: `SqliteVectorBackend(backend/storage/vectors.sqlite)`
- **Retrieval Mode (Pinned)**: `hybrid_rrf_pinned`
- **Store Baseline SHA-256**: `5d3c7f30baf75fa161d61b076126c945b180f1f8ec10dc1a0c9e559843b7bcdb`

## Separated Group Metrics (R8)
### 1. Training Tasks (Held-Out: False)
- **Pass Rate**: **5/5 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 2. Held-Out Tasks (Held-Out: True)
- **Pass Rate**: **2/2 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 3. Hard Subset Tasks (Complex Multi-Module & Coupled Physics)
- **Pass Rate**: **7/7 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

## Detailed Task Summary
| Task ID | Title | Category | Held-Out | Overall Status | Runs Passed | Mean Time (s) | Lessons Retrieved |
|---|---|---|---|---|---|---|---|
| `TASK-07-MULTI-EVENT-BUS` | Asynchronous Event Bus with DLQ and Middleware | `multi_module` | Yes | **PASS** | 3/3 | 0.0s | None |
| `TASK-16-PHYS-PENDULUM` | Double Pendulum Chaotic Dynamics via Runge-Kutta RK4 | `physics_numerics` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-19-MULTI-RAFT-KV` | Distributed In-Memory Raft Consensus KV Store | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-20-MULTI-PIPELINE` | Streaming Dataflow Pipeline with Tumbling Windows | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-21-MULTI-QUERY-ENGINE` | In-Memory Columnar Relational Query Engine | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-22-MULTI-PLUGIN-ARCH` | Pluggable Microkernel Architecture with Sandboxing | `multi_module` | No | **PASS** | 3/3 | 0.0s | None |
| `TASK-24-HELDOUT-DIFFUSION-2D` | 2D Reaction-Diffusion Gray-Scott Pattern Simulator | `physics_numerics` | Yes | **PASS** | 3/3 | 0.0s | None |

## Per-Run Breakdown

### `TASK-07-MULTI-EVENT-BUS`: Asynchronous Event Bus with DLQ and Middleware
- **Category**: multi_module | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-07-multi-event-bus-run1.md`
    - Coordination Board: `team\team-task-07-multi-event-bus-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-07-multi-event-bus-run2.md`
    - Coordination Board: `team\team-task-07-multi-event-bus-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-07-multi-event-bus-run3.md`
    - Coordination Board: `team\team-task-07-multi-event-bus-run3\board.md`

### `TASK-16-PHYS-PENDULUM`: Double Pendulum Chaotic Dynamics via Runge-Kutta RK4
- **Category**: physics_numerics | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-16-phys-pendulum-run1.md`
    - Coordination Board: `team\team-task-16-phys-pendulum-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-16-phys-pendulum-run2.md`
    - Coordination Board: `team\team-task-16-phys-pendulum-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-16-phys-pendulum-run3.md`
    - Coordination Board: `team\team-task-16-phys-pendulum-run3\board.md`

### `TASK-19-MULTI-RAFT-KV`: Distributed In-Memory Raft Consensus KV Store
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-19-multi-raft-kv-run1.md`
    - Coordination Board: `team\team-task-19-multi-raft-kv-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-19-multi-raft-kv-run2.md`
    - Coordination Board: `team\team-task-19-multi-raft-kv-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-19-multi-raft-kv-run3.md`
    - Coordination Board: `team\team-task-19-multi-raft-kv-run3\board.md`

### `TASK-20-MULTI-PIPELINE`: Streaming Dataflow Pipeline with Tumbling Windows
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-20-multi-pipeline-run1.md`
    - Coordination Board: `team\team-task-20-multi-pipeline-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-20-multi-pipeline-run2.md`
    - Coordination Board: `team\team-task-20-multi-pipeline-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-20-multi-pipeline-run3.md`
    - Coordination Board: `team\team-task-20-multi-pipeline-run3\board.md`

### `TASK-21-MULTI-QUERY-ENGINE`: In-Memory Columnar Relational Query Engine
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-21-multi-query-engine-run1.md`
    - Coordination Board: `team\team-task-21-multi-query-engine-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-21-multi-query-engine-run2.md`
    - Coordination Board: `team\team-task-21-multi-query-engine-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-21-multi-query-engine-run3.md`
    - Coordination Board: `team\team-task-21-multi-query-engine-run3\board.md`

### `TASK-22-MULTI-PLUGIN-ARCH`: Pluggable Microkernel Architecture with Sandboxing
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-22-multi-plugin-arch-run1.md`
    - Coordination Board: `team\team-task-22-multi-plugin-arch-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-22-multi-plugin-arch-run2.md`
    - Coordination Board: `team\team-task-22-multi-plugin-arch-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-22-multi-plugin-arch-run3.md`
    - Coordination Board: `team\team-task-22-multi-plugin-arch-run3\board.md`

### `TASK-24-HELDOUT-DIFFUSION-2D`: 2D Reaction-Diffusion Gray-Scott Pattern Simulator
- **Category**: physics_numerics | **Held-Out**: True
- **Overall Status**: **PASS** (3/3 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-24-heldout-diffusion-2d-run1.md`
    - Coordination Board: `team\team-task-24-heldout-diffusion-2d-run1\board.md`
  - Run 2: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-24-heldout-diffusion-2d-run2.md`
    - Coordination Board: `team\team-task-24-heldout-diffusion-2d-run2\board.md`
  - Run 3: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-24-heldout-diffusion-2d-run3.md`
    - Coordination Board: `team\team-task-24-heldout-diffusion-2d-run3\board.md`