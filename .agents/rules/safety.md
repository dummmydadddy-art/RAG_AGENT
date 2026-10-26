# Safety & Protected Boundaries Rule

This rule enforces strict boundaries for autonomous agent operations, protected files, and repository isolation.

## 1. Repository Isolation
- This repository (`RAG Agent`) is a separate, independent repository.
- **Never** push, pull-request, or merge changes from this repository into any external or previous LMS repository.
- All remotes and pushes must strictly target the designated `RAG Agent` repository only.

## 2. Protected Paths
The following files and directories are protected and require explicit human approval before being modified:
- `GEMINI.md`
- `AGENTS.md`
- `.agents/**` (rules, skills, role definitions, budgets)
- `evals/**` (evaluation benchmarks, hidden test fixtures, runners)

The reviewer role must reject any autonomous pull request or diff modifying protected paths without recorded human authorization.

## 3. Forbidden Commands & Operations
- Never push directly to the `main` branch.
- Never execute force pushes (`git push --force` / `git push -f`).
- Never perform recursive file deletions on project roots or outside isolated scratch/worktree scopes.
- Never write credentials, tokens, or private keys to files, git commits, or console logs. All credentials must be read exclusively from environment variables.

## 4. Execution Limits
- All autonomous tasks are subject to the ceilings defined in `budgets.yaml`. On breach, the agent must halt execution, document the state, and await human direction.
