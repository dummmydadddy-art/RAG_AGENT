---
name: plan-and-tasks
description: "Use when producing an implementation plan. Provides plan template, task slicing, risk scoring, and escalation criteria."
---

# Plan and Tasks Skill

## When to Use
Invoke this skill after completing pre-plan retrieval and repository scanning, whenever formulating an implementation plan artifact.

## Plan Structure (`PLAN.md`)
Every plan must be written as an artifact with the following structure:

```markdown
# Implementation Plan: [Feature/Task Title]

## 1. Goal & Acceptance Criteria
- Explicit restatement of goal and measurable acceptance criteria.

## 2. Retrieved Lessons & Citations
- Cite all lesson IDs retrieved from the RAG store: e.g. `L-2026-10-0001`.
- If unverified candidates are cited, mark them `[unverified]`.

## 3. Risk Assessment & Slicing
- **Risk Level**: Low | Medium | High
- **Escalation Triggers**: Check if 3+ modules are touched or ambiguous math exists.

## 4. Task Breakdown (Slices)
- [ ] Task 1: [Task Name] (Red test -> Green implementation)
- [ ] Task 2: [Task Name]
```

## Task Slicing Rules
1. Non-overlapping scopes: Each task must touch a distinct, well-defined set of files.
2. Test-first pairing: Each task must name its automated test fixture before implementation.
3. Iteration Budget: Maximum 4 iterations per task before escalating or halting.
