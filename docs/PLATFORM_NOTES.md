# Antigravity Platform Notes (Phase 0 Output)

*Verified against live host environment on 26 October 2026.*

## 1. Environment & Surface Verification

- **Antigravity Surface**: Google Antigravity Desktop App v44.4.3 (`C:\Users\Mukul\AppData\Local\Programs\antigravity\Antigravity.exe`).
- **Application Data Directory**: `C:\Users\Mukul\.gemini\antigravity`
  - Subdirectories: `brain/` (conversation artifacts & step logs), `conversations/`, `mcp/` (lazy schemas), `bin/` (`agentapi.bat`, `webm_encoder.exe`), `crashes/`, `plugin_data/`.
- **Global Configuration Directory**: `C:\Users\Mukul\.gemini\config`
  - Subdirectories: `agents/` (custom agent markdown definitions), `skills/` (global skills), `plugins/`, `projects/`.
- **Active MCP Configuration**: `C:\Users\Mukul\.gemini\config\mcp_config.json`.
  - Configured servers: `serena`, `context7`, `n8n-mcp`, `playwright`, `firecrawl`, `chrome-devtools`.
  - Servers run as stdio JSON-RPC processes via `npx` or local executables.
- **Operating System & Tooling**:
  - Windows 11 with PowerShell 5.1 / Core.
  - Python: 3.11.15.
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
| **MCP Config** | Spec noted `mcp_config.json` location required confirmation | Active file is `C:\Users\Mukul\.gemini\config\mcp_config.json` | Register project MCP servers in `C:\Users\Mukul\.gemini\config\mcp_config.json`. |
| **Workflows** | `.agents/workflows/` or `.agent/workflows/` | Markdown command macros supported | Provide slash workflows under `.agents/workflows/`. |

## 3. Subprocess & Windows Operational Constraints

1. **Subprocess Isolation**:
   - `physmath-mcp` runs mathematical and physical checks in isolated Python subprocesses with `timeout=5.0s`.
   - Windows network sandboxing: Subprocesses are executed without network sockets enabled and without access to credentials.
2. **File Paths & Encodings**:
   - UTF-8 forced on all file reads and writes (`encoding="utf-8"`).
   - Use `pathlib.Path` with resolved absolute paths for all cross-platform file system operations.
   - Forward slashes or raw Windows string paths used in JSON-RPC MCP configuration.
3. **Safety Boundaries**:
   - `.agents/**`, `GEMINI.md`, `AGENTS.md`, and `evals/**` are protected from autonomous modification.
   - Pushing to `main` is disallowed; work proceeds via feature branches and pull requests.
