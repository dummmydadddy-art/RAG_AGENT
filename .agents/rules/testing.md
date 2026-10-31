# Testing Discipline Rule

This rule governs test authoring, test execution, and verification invariants across all tasks.

## 1. Test-First (TDD) Invariant
1. Red Phase: Author a failing test asserting the expected behavior, API contract, or physical invariant before writing implementation code.
2. Green Phase: Author the minimal implementation code required to make the test pass.
3. Refactor Phase: Clean up design, remove duplication, and improve readability while maintaining passing tests.

## 2. No Skipped Tests
- Disabling, skipping (`@pytest.mark.skip`), or commenting out failing tests to achieve completion is strictly forbidden.
- If a test fails, diagnose the root cause: either fix the implementation or, if the requirement changed, document the rationale in the task trace before adjusting the test assertion.

## 3. Contract Tests & Backend Parity
- All data layer and adapter interfaces (`RagAdapter`) must have dedicated contract tests.
- Contract test suites must execute identically against both in-memory test stubs and live backends (`StubBackend` and `LocalSqliteRagBackend`).
- Any backend failing a contract test is blocked from production deployment.

## 4. Windows Subprocess & Shell Isolation
- Never execute unquoted shell commands containing nested quotes in PowerShell.
- When spawning Python subprocesses from within MCP server tools on Windows, **always specify `stdin=subprocess.DEVNULL`**. Failure to do so causes child interpreters to inherit the parent JSON-RPC stdin pipe, resulting in silent timeouts.

## 5. Polyglot Sandbox Execution Integrity
- In polyglot sandboxes, never simulate execution or mock successful passes when a host compiler (e.g., `rustc`, `g++`, `clang`) is missing.
- Always perform genuine host checks and return an honest diagnostic indicating the missing toolchain.

## 6. Database Storage Isolation & Concurrency Invariant
- User-facing chat histories, UI session telemetry, and external write streams must never share write locks with background autonomous learning daemons.
- Maintain dedicated SQLite storage paths (e.g., `backend/storage/chat_history.sqlite`) segregated from the vector knowledge database (`backend/storage/vectors.sqlite`).

