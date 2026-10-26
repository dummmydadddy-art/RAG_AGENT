# Antigravity Platform Notes

*Verified against live host environment on 26 October 2026.*

## 1. Environment & Surface Verification

- **Antigravity Surface**: Google Antigravity Desktop App v44.4.3 (`C:\Users\Mukul\AppData\Local\Programs\antigravity\Antigravity.exe`).
- **Application Data Directory**: `C:\Users\Mukul\.gemini\antigravity`
  - Subdirectories: `brain/` (conversation artifacts & step logs), `conversations/`, `mcp/` (lazy schemas), `bin/` (`agentapi.bat`, `webm_encoder.exe`), `crashes/`, `plugin_data/`.
- **Global Configuration Directory**: `C:\Users\Mukul\.gemini\config`
  - Subdirectories: `agents/` (custom agent markdown definitions), `skills/` (global skills), `plugins/`, `projects/`.
- **Active MCP Configuration**: `C:\Users\Mukul\.gemini\config\mcp_config.json`.
  - Configured servers: `serena`, `context7`, `n8n-mcp`, `playwright`, `firecrawl`, `chrome-devtools`, `rag-mcp`, `physmath-mcp`.
  - Servers run as stdio JSON-RPC processes via `npx` or local virtualenv python (`.venv\Scripts\python.exe`).
- **Operating System & Tooling**:
  - Windows 11 with PowerShell 5.1 / Core.
  - Python: 3.11.15 in `.venv`.
  - Git: 2.51.0 (`core.longpaths = true` enabled).
  - PHP: 8.3.32 (with `sqlite3` and `curl` extensions).

## 2. Comparison with ARCHITECTURE.md Section 3

| Architectural Area | Spec (ARCHITECTURE.md Section 3) | Live Environment Reality | Action / Decision |
|---|---|---|---|
| **Surface** | Desktop app (2.0), CLI (`agy`), IDE, SDK | Desktop App v44.4.3 installed and active | Align paths to Desktop 44.4.3 app data (`~/.gemini/antigravity`) and config (`~/.gemini/config`). |
| **Project Rules** | `GEMINI.md` or `AGENTS.md` (GEMINI.md wins); `.agents/rules/*.md`; 12,000 char cap | Root `GEMINI.md` and `.agents/rules/*.md` verified; cap strictly enforced | Maintain `GEMINI.md` < 1,500 tokens; ensure each rule file < 12,000 characters. |
| **Global Rules** | `~/.gemini/GEMINI.md` | Verified exists at `C:\Users\Mukul\.gemini\GEMINI.md` and active in prompt | Coexists cleanly without collision. |
| **Skills** | `.agents/skills/<name>/SKILL.md` (or `.agent/skills/`) | Both project and global `~/.gemini/config/skills/` supported | Use `.agents/skills/` standard spelling. |
| **Custom Agents** | `.agents/agents/<name>.md` or global `~/.gemini/config/agents/` | Verified: `~/.gemini/config/agents/` holds `.md` files with YAML frontmatter | Use standard markdown format with YAML frontmatter (`name`, `description`, `tools`, `color`). |
| **Subagents** | Orchestrator defines and spawns in parallel; worktree isolation; no peer messaging | Verified: `invoke_subagent` and `define_subagent` present in native toolset | Supported with isolated worktrees and asynchronous parent completion callbacks. |
| **MCP Config** | Spec noted `mcp_config.json` location required confirmation | Active file is `C:\Users\Mukul\.gemini\config\mcp_config.json` | Registered project MCP servers in `C:\Users\Mukul\.gemini\config\mcp_config.json`. |
| **Workflows** | `.agents/workflows/` or `.agent/workflows/` | Markdown command macros supported | Provide slash workflows under `.agents/workflows/`. |

## 3. Subprocess & Windows Operational Constraints

1. **Subprocess Isolation**:
   - `physmath-mcp` runs mathematical and physical checks in isolated Python subprocesses with `timeout=5.0s`.
   - Windows network sandboxing: Subprocesses are executed without network sockets enabled and without access to credentials.
   - *Security Note*: On Windows, subprocess socket-patching and timeouts act as operational guardrails against runaway scripts, accidental network calls, and compute loops; they do not constitute a cryptographic or kernel-level security boundary (e.g. Linux cgroups/seccomp). Untrusted arbitrary native code must not be executed without host isolation.
2. **File Paths & Encodings**:
   - UTF-8 forced on all file reads and writes (`encoding="utf-8"`).
   - Use `pathlib.Path` with resolved absolute paths for all cross-platform file system operations.
   - Forward slashes or raw Windows string paths used in JSON-RPC MCP configuration.
3. **Safety Boundaries**:
   - `.agents/**`, `GEMINI.md`, `AGENTS.md`, and `evals/**` are protected from autonomous modification.
   - Pushing to `main` is disallowed; work proceeds via feature branches and pull requests.

## 4. Phase 1 Platform Verification Findings

1. **Custom Agent Frontmatter & Format**:
   - Files reside in `.agents/agents/<name>.md` (project) or `~/.gemini/config/agents/<name>.md` (global).
   - Schema:
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
   - Body contains `<role>`, `<input>`, responsibilities, and procedural instructions.
2. **Tool Restriction per Role**:
   - The `tools` frontmatter field strictly whitelists which tools the agent harness provides to that subagent.
   - For example:
     - `implementer`: `read_file, write_file, edit_file, run_command, units_check, sym_equiv, numeric_compare`. (Does NOT have access to `rag_upsert_lesson` or `invoke_subagent`).
     - `reviewer`: `read_file`. (Read-only; cannot modify files or run destructive commands).
     - `physmath-verifier`: `read_file, write_file, units_check, sym_equiv, numeric_compare`.
     - `librarian`: `read_file, rag_search, rag_upsert_lesson, rag_promote, rag_demote, rag_stats`.
3. **Workflows Folder & Slash Commands**:
   - Folder: `.agents/workflows/<command>.md`.
   - Contains execution stages, argument parsing (`$ARGUMENTS`), and macro directives.
4. **Non-Interactive Execution & Eval Runner Architecture**:
   - Inspection of `language_server.exe` and `Antigravity.exe` confirmed that Antigravity operates as an interactive Desktop Electron application and background language server daemon; there is no headless `agy --exec` CLI binary present on this system.
   - Therefore, `evals/run.py` is designed as a **semi-manual evaluation harness**:
     - Prepares the isolated task fixture.
     - Formulates and displays the `/gsd <task>` execution prompt for the orchestrator.
     - Awaits agent completion notification (or Enter in console).
     - Mounts/copies hidden checks from the protected hidden checks repository.
     - Runs grading tests via `pytest`, measures elapsed time and iterations, inspects `PLAN.md` and traces, and produces markdown reports under `evals/reports/`.
