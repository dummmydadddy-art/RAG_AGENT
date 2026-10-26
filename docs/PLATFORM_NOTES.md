# Antigravity Platform Notes

*Verified against live host environment on 26 October 2026 (Revision Pass R1–R8).*

## 1. Environment & Surface Verification

- **Antigravity Surfaces**:
  - **Desktop App**: Google Antigravity Desktop App v44.4.3 (`C:\Users\Mukul\AppData\Local\Programs\antigravity\Antigravity.exe`).
  - **CLI (`agy`)**: Installed at `C:\Users\Mukul\AppData\Local\agy\bin\agy.exe` (version 1.4.7, linux-x64/win32 host).
    - Verified non-interactive execution via:
      `agy.exe -p "<prompt>" --output-format text --dangerously-skip-permissions`
- **Application Data Directory**: `C:\Users\Mukul\.gemini\antigravity`
  - Subdirectories: `brain/` (conversation artifacts & step logs), `conversations/`, `mcp/` (lazy schemas), `bin/` (`agentapi.bat`, `webm_encoder.exe`), `crashes/`, `plugin_data/`.
- **Global Configuration Directory**: `C:\Users\Mukul\.gemini\config`
  - Subdirectories: `agents/` (custom agent markdown definitions), `skills/` (global skills), `plugins/`, `projects/`.
- **Active MCP Configuration**: `C:\Users\Mukul\.gemini\config\mcp_config.json`.
  - Configured servers: `serena`, `context7`, `n8n-mcp`, `playwright`, `firecrawl`, `chrome-devtools`, `rag-mcp`, `physmath-mcp`.
  - **Read-Only Hardening**: `rag-mcp` is explicitly registered with `"RAG_MCP_READ_ONLY": "true"`. Write operations require librarian credential token passed per-invocation.
- **Operating System & Tooling**:
  - Windows 11 with PowerShell 5.1 / Core.
  - Python: 3.11.15 in `.venv`.
  - Git: 2.51.0 (`core.longpaths = true` enabled).
  - PHP: 8.3.32 (with `sqlite3` and `curl` extensions).
  - Ollama: Local daemon running `nomic-embed-text:latest` (768 dimensions).

## 2. Comparison with ARCHITECTURE.md Section 3

| Architectural Area | Spec (ARCHITECTURE.md Section 3) | Live Environment Reality | Action / Decision |
|---|---|---|---|
| **Surfaces** | Desktop app (2.0), CLI (`agy`), IDE, SDK | Desktop App v44.4.3 + CLI `agy.exe` v1.4.7 verified | Supported. Non-interactive CLI runs verified for automated harness. |
| **Project Rules** | `GEMINI.md` or `AGENTS.md` (GEMINI.md wins); `.agents/rules/*.md`; 12,000 char cap | Root `GEMINI.md` and `.agents/rules/*.md` verified; cap strictly enforced | Maintain `GEMINI.md` < 1,500 tokens; ensure each rule file < 12,000 characters. |
| **Global Rules** | `~/.gemini/GEMINI.md` | Verified exists at `C:\Users\Mukul\.gemini\GEMINI.md` and active in prompt | Coexists cleanly without collision. |
| **Skills** | `.agents/skills/<name>/SKILL.md` (or `.agent/skills/`) | Both project and global `~/.gemini/config/skills/` supported | Use `.agents/skills/` standard spelling. |
| **Custom Agents** | `.agents/agents/<name>.md` or global `~/.gemini/config/agents/` | Verified: `~/.gemini/config/agents/` holds `.md` files with YAML frontmatter | Use standard markdown format with YAML frontmatter (`name`, `description`, `tools`, `color`). |
| **Subagents** | Orchestrator defines and spawns in parallel; worktree isolation; no peer messaging | Verified: `invoke_subagent` and `define_subagent` present in native toolset | Supported with isolated worktrees and asynchronous parent completion callbacks. |
| **MCP Config** | Spec noted `mcp_config.json` location required confirmation | Active file is `C:\Users\Mukul\.gemini\config\mcp_config.json` | Registered project MCP servers with default read-only enforcement. |
| **Workflows** | `.agents/workflows/` | Collision resolved: renamed `/gsd` to `/rag-gsd` | Avoid collision with 72 global `gsd-core` workflow commands. |

## 3. Subprocess & Windows Operational Constraints

1. **Subprocess Isolation**:
   - `physmath-mcp` runs mathematical and physical checks in isolated Python subprocesses with `timeout=5.0s`.
   - Windows network sandboxing: Subprocesses are executed without network sockets enabled and without access to credentials.
   - *Security Guardrail Note*: On Windows, subprocess socket-patching and timeouts act as operational guardrails against runaway scripts, accidental network calls, and compute loops; they do not constitute a cryptographic or kernel-level security boundary (e.g. Linux cgroups/seccomp). Untrusted arbitrary native code must not be executed without host isolation.
2. **File Paths & Encodings**:
   - UTF-8 forced on all file reads and writes (`encoding="utf-8"`).
   - Use `pathlib.Path` with resolved absolute paths for all cross-platform file system operations.
   - Forward slashes or raw Windows string paths used in JSON-RPC MCP configuration.
3. **Safety Boundaries**:
   - `.agents/**`, `GEMINI.md`, `AGENTS.md`, and `evals/**` are protected from autonomous modification.
   - Pushing to `main` is disallowed; work proceeds via feature branches and pull requests.

## 4. Role Enforcement & MCP Security

1. **Frontmatter Schema**:
   - Standard frontmatter in `.agents/agents/<name>.md`:
     ```yaml
     ---
     name: agent-name
     description: "One line actionable summary"
     tools: tool1, tool2, tool3
     color: cyan | blue | green | magenta | red | yellow
     mainAgent: false # optional
     hidden: false    # optional
     ---
     ```
2. **Runtime Tool Restriction**:
   - In Antigravity's programmatic subagent dispatch (`define_subagent`), tool sets are governed by boolean capability flags (`EnableWriteTools: false` disables all file creation, editing, and bash execution tools).
   - Tested: When `test-reviewer` was invoked with `EnableWriteTools: false` and asked to write a file, it explicitly reported lack of write capabilities.
   - Server-side enforcement: `rag-mcp` verifies write credentials on `rag_upsert_lesson`, `rag_promote`, and `rag_demote`. When `test-verifier` called `rag_upsert_lesson`, it was rejected with `PermissionError: invalid or missing librarian write credential`.
   - Reviewer role receives diffs and test outputs directly within prompt context rather than relying on interactive git commands.

## 5. Benchmark Architecture & Secure Evaluation

1. **Encrypted Evaluation Fixtures**:
   - Hidden evaluation tests are encrypted in `evals/hidden_evals.enc` using PBKDF2-HMAC-SHA256 and Fernet AES.
   - Tests are decrypted only into memory during grading runs with a passphrase supplied at grading time.
2. **Canary Token Scanner**:
   - All evaluation fixtures embed the unique canary string `CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456`.
   - `evals/run.py` scans `src/`, `PLAN.md`, traces, and test output for canary string or path leakage, automatically disqualifying any contaminated run.
3. **Store Hygiene**:
   - The lesson store (`vectors.sqlite`) is snapshotted via `scripts/snapshot_store.py` before runs, with its SHA-256 hash recorded in every eval result.
   - `reset_store()` restores the lessons collection to a clean baseline state before each task.
4. **Multi-Run Reporting (R8)**:
   - Evaluator supports `--repeat k` (default 3), reporting per-run pass, overall pass ($\ge 2/3$), mean iterations, and wall time.
   - Reports strictly separate Training Tasks from Held-Out Tasks (no merged scoring).
