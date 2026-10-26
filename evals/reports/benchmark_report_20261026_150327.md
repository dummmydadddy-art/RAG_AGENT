# Benchmark Evaluation Report — 20261026_150327

- **Execution Mode**: `team`
- **Lessons Mode**: `off`
- **Repetitions per Task (`--repeat`)**: `1`
- **Backend Identity**: `SqliteVectorBackend(backend/storage/vectors.sqlite)`
- **Retrieval Mode (Pinned)**: `hybrid_rrf_pinned`
- **Store Baseline SHA-256**: `f2e96d7729db7a4b1b35029508178e2edd6a917a46bdf24d4311ee5542af49a1`

## Separated Group Metrics (R8)
### 1. Training Tasks (Held-Out: False)
- **Pass Rate**: **1/1 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

### 2. Held-Out Tasks (Held-Out: True)
- **Pass Rate**: **0/0 (0.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 0.0

### 3. Hard Subset Tasks (Complex Multi-Module & Coupled Physics)
- **Pass Rate**: **1/1 (100.0%)**
- **Mean Wall Time**: 0.0s
- **Mean Iterations**: 1.0

## Detailed Task Summary
| Task ID | Title | Category | Held-Out | Overall Status | Runs Passed | Mean Time (s) | Lessons Retrieved |
|---|---|---|---|---|---|---|---|
| `TASK-19-MULTI-RAFT-KV` | Distributed In-Memory Raft Consensus KV Store | `multi_module` | No | **PASS** | 1/1 | 0.0s | None |

## Per-Run Breakdown

### `TASK-19-MULTI-RAFT-KV`: Distributed In-Memory Raft Consensus KV Store
- **Category**: multi_module | **Held-Out**: False
- **Overall Status**: **PASS** (1/1 runs passed)
  - Run 1: **PASS** (0.0s)
    - Architecture Decision Record: `decisions\team-task-19-multi-raft-kv-run1.md`
    - Coordination Board: `team\team-task-19-multi-raft-kv-run1\board.md`