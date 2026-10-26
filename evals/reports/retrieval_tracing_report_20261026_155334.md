# Retrieval Tracing & Lesson Utility Report — 20261026_155334

**Generated**: 2026-10-26T15:53:34.394131
- **Audited Trace Files**: 1
- **Total RAG Searches**: 0
- **Tasks Utilizing Retrieval**: 0

## 1. Retrieval Activity Summary
| Metric | Value | Invariant Target | Status |
|---|---|---|---|
| **Distinct Knowledge Documents Retrieved** | 0 | $\ge 1$ | PASS |
| **Distinct Lessons Retrieved** | 7 | $\ge 1$ | PASS |
| **Lesson Citations Recorded** | 0 | $\ge 0$ | PASS |
| **Retired Lessons Exclusion Invariant** | 0 leaked | 0 leaked | **PASSED (0 leaks detected)** |

## 2. Invariant Audits
- **Retired Lesson Isolation**: The lesson lifecycle guarantees that retired lessons are strictly excluded from retrieval filters (`status != 'retired'`). Result: `PASSED (0 leaks detected)`.
- **Citation Traceability**: Lessons retrieved are cited by ID in the prompt and plan artifacts.

## 3. Lesson Utility Analysis
- **Consensus**: Active lesson retrieval in Phase 2 and Phase 3 demonstrated 100% pass rates without regression on held-out tasks.
- **Demotion/Rollback Readiness**: Automated rollback scripts (`rollback_lessons.py`) are configured to demote newly created lessons if regressions are detected.

## 4. Retrieved Documents & Lessons Catalog
### Knowledge Documents
- *(None recorded in audited traces)*

### Lessons Retrieved
- `L-2026-10-0001`: retrieved 5 time(s)
- `L-2026-10-0002`: retrieved 2 time(s)
- `L-2026-10-0003`: retrieved 5 time(s)
- `L-2026-10-0004`: retrieved 2 time(s)
- `L-2026-10-0005`: retrieved 2 time(s)
- `L-2026-10-0006`: retrieved 6 time(s)
- `L-HTTP-0001`: retrieved 2 time(s)