---
name: code-review
description: "Use when reviewing a diff or pull request. Audits against plan, tests, style, safety boundaries, and protected paths."
---

# Code Review Skill

## When to Use
Invoke this skill following task execution to evaluate code diffs before verification sign-off or PR creation.

## Review Checklist
1. **Plan Alignment**:
   - Does the implementation match the specification and acceptance criteria in `PLAN.md`?
   - Are any extraneous or unapproved changes included?
2. **Safety & Protected Paths**:
   - Were any protected files modified (`GEMINI.md`, `AGENTS.md`, `.agents/**`, `evals/**`) without explicit authorization?
   - Reject immediately if protected paths were modified autonomously.
3. **Test Integrity**:
   - Are all new code paths covered by automated tests?
   - Are there any skipped or mocked tests hiding defects?
4. **Style & Conventions**:
   - Strict adherence to PEP 8, full type annotations, and `pathlib.Path` usage.
   - Zero hardcoded credentials or API keys.
