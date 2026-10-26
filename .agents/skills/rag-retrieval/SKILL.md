---
name: rag-retrieval
description: "Use before planning any task. Formulates queries, filters collections, injects at most 5 lessons within ~1,500 tokens, and records which IDs were used."
---

# RAG Retrieval Skill

## When to Use
Invoke this skill at the intake of every `/gsd` or `/team` task, **before** producing any architecture, plan, or code modifications.

## Procedure
1. **Formulate Query**:
   - Extract key domain keywords, algorithms, and technical challenges from the task description.
   - Formulate focused queries against both `knowledge` and `lessons` collections.
2. **Execute Tool Call**:
   - Call `rag_search(query=..., collections=["knowledge", "lessons"], k=5)`.
3. **Filter & Filter Invariants**:
   - Exclude retired lessons (`status == "retired"`).
   - Prioritize `verified` lessons over `candidate` lessons.
   - Mark candidate lessons explicitly as `[unverified]` in your plan.
   - Limit injection to at most 5 lessons (under 1,500 tokens).
4. **Citation Requirement**:
   - Record every retrieved lesson ID (`L-YYYY-MM-XXXX`) in the plan header under `## Retrieved Lessons`.
   - If no lessons apply, explicitly state `## Retrieved Lessons: None`.
