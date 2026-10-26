# Lesson Handling & Distillation Rule

This rule establishes the format, lifecycle, and retrieval invariants for self-learning lessons.

## 1. Lesson Schema & Format
Every lesson must follow the canonical format:
- **Title**: Short imperative sentence.
- **Rule**: `When <situation>, do <action>, because <reason>`.
- **Domain**: One or more tags: `physics`, `numerics`, `infra`, `python`, `rag`, `architecture`.
- **Evidence**: Task ID, commit hash, verified passing test IDs, and review sign-off.
- **Lifecycle Status**: Exactly one of: `candidate`, `verified`, `retired`.

## 2. Lesson Lifecycle Invariants
1. **Candidate First**: Lessons are initially stored as `candidate`. A candidate lesson can only be created following a task whose tests pass cleanly.
2. **Promotion to Verified**: A candidate lesson is promoted to `verified` only when evidence tests are green AND either the feature PR merged without revert OR one subsequent reuse succeeded.
3. **Retirement**: A lesson is retired if:
   - It accumulates 2 failures with a success ratio below 50%.
   - It directly contradicts an established entry in `knowledge` or a higher-confidence verified lesson.
   - It remains unused for 90 consecutive days.
   Retired lessons are preserved for historical audit but excluded from default retrieval.

## 3. Retrieval & Usage Invariants
- Pre-plan retrieval queries both `knowledge` and `lessons` collections.
- Retired lessons are strictly excluded. Verified lessons are prioritized. Candidate lessons are only surfaced when marked `[unverified]`.
- Retrieval injects at most 5 lessons (under ~1,500 tokens).
- The agent must explicitly cite the lesson IDs (`L-YYYY-MM-XXXX`) used in its plan and code.
- **Inviolable Invariant**: A lesson never overrides a failing automated test or a failed PhysMath check.
