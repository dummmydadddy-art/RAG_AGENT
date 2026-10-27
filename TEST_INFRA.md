# E2E Test Infra: stem-coder-expert

## Test Philosophy
- Opaque-box, requirement-driven derived strictly from `ORIGINAL_REQUEST.md`.
- No reliance on internal implementation details; evaluates system through public CLI, Python scripts, SQLite vector store, and Ollama HTTP API.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Workload Testing across 4 tiers.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|----------------------|:------:|:------:|:------:|:------:|
| 1 | F1: Polyglot Multi-Language Dataset Curation | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | F2: 3-Tier Zero-Redundancy Deduplication | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | F3: SQLite Vector Store Ingestion (PHP 128M limit) | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 4 | F4: Pre-flight GPU VRAM Eviction | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 5 | F5: 4-Bit QLoRA Fine-Tuning (Peak VRAM <= 3.8 GB) | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | F6: CPU RAM Weight Merge (<= 12 GB RAM, 0 VRAM) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 7 | F7: GGUF Quantization (q4_k_m) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 8 | F8: Zero-Redundancy SSD Purging (<= 10 GB net) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 9 | F9: Ollama Registration (stem-coder-expert:latest) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 10 | F10: Automated Polyglot Verification & Quality Gate | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test runner: `pytest tests/e2e/test_stem_coder_e2e.py -v`
- Pass/Fail semantics: Exit code 0, all assertions pass, hardware metrics verified.
- Directory layout:
  - `tests/e2e/test_stem_coder_e2e.py`: Main E2E test suite covering Tiers 1–4.
  - `tests/e2e/fixtures/`: Polyglot challenge inputs and test vectors.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Target Language |
|---|----------|--------------------|-----------------|
| 1 | Python: Fast LRU Cache with TTL | F9, F10 | Python |
| 2 | TypeScript: Type-Safe Event Bus | F9, F10 | TypeScript |
| 3 | C++: Lock-Free Single-Producer Single-Consumer Queue | F9, F10 | C++ |
| 4 | Rust: Zero-Copy String Tokenizer | F9, F10 | Rust |
| 5 | SQL: Recursive CTE for Hierarchical Organization Chart | F9, F10 | SQL |
| 6 | PHP: PSR-4 Autoloading Router with Middleware Pipeline | F9, F10 | PHP |
| 7 | Java: Thread-Safe Object Pool | F9, F10 | Java |
| 8 | Go: Worker Pool with Graceful Cancellation | F9, F10 | Go |

## Coverage Thresholds
- Tier 1: ≥ 5 tests per feature (50 tests total across F1–F10)
- Tier 2: ≥ 5 tests per feature (boundary/error cases, 50 tests total)
- Tier 3: Pairwise cross-feature interactions (≥ 10 tests)
- Tier 4: ≥ 8 real-world polyglot application scenarios
- Total: ≥ 118 E2E test cases
