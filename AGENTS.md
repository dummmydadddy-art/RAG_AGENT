# Shared Engineering Conventions

This document establishes development conventions for all agents and contributors across `RAG-Agent`.

## 1. Language & Runtime Environments
- **Primary Language**: Python 3.11+
  - Style: PEP 8, formatted with Black/Ruff standards.
  - Type Hints: Mandatory on all function signatures, methods, and interface definitions.
  - Paths: Always use `pathlib.Path` for cross-platform Windows compatibility.
  - Encodings: Always specify `encoding="utf-8"` when reading or writing files.
- **RAG Backend**: PHP 8.3 REST API and SQLite vector database (`backend/storage/vectors.sqlite`).
  - **Memory Ceiling Guard**: Capped at $\le 500$ rows in `material_chunks` until SQ8 quantization is implemented to protect the 128 MB PHP process memory limit.
- **Shell**: PowerShell 5.1 / 7 on Windows 11. Scripts located in `scripts/`.

## 2. Test-Driven Development (TDD)
- Test runner: `pytest`.
- Structure:
  - Unit tests: `tests/unit/`
  - Integration tests: `tests/integration/`
  - Contract tests: `tests/contract/`
  - PhysMath acceptance tests: `tests/physmath/`
- All tests must execute cleanly without external network access or unhandled exceptions.
- Never mock the system under test unless simulating network partition or external API failure.

## 3. Git & Worktree Conventions
- Never push directly to `main`.
- All development takes place on feature branches: `feature/<phase-or-feature-name>`.
- Parallel subagents operate in isolated git worktrees with disjoint, non-overlapping file scopes.
- Every commit message must follow Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `refactor:`).
