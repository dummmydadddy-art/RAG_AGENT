# Self-Learning Coding Agent on Google Antigravity

Architecture, build plan and kickoff prompt. Draft v1, 25 October 2026.

## 1. Purpose and scope

This document defines how to build a self-learning coding agent on Google Antigravity. It is written to be saved into the repository as `docs/ARCHITECTURE.md` and used as the source of truth by the building agent.

The agent must:

- retrieve from the existing RAG engine before it plans;
- verify physics and maths with executable tools, not recall;
- learn by writing verified lessons back into the RAG engine;
- run in two modes: `/gsd` (one lead agent plus subagents) and `/team` (debated, parallel build).

Non-goals: fine-tuning model weights; letting the agent edit its own rules, skills or agent definitions without human review; any claim of learning that is not measured by the evaluation harness.

## 2. Design decisions

| # | Decision | Choice | Reason |
| --- | --- | --- | --- |
| 1 | What self-learning means | Verified lessons written to a lesson store; no weight updates | Cheap, inspectable, reversible |
| 2 | When a lesson becomes trusted | Candidate first; verified only with passing evidence plus a merge or one successful reuse | Stops confident wrong lessons from accumulating |
| 3 | Physics and maths | Retrieval, executable verification tools, and a verifier role with veto | Model recall produces fluent errors |
| 4 | Verifier independence | Verifier derives checks from the spec before seeing the implementation | Author and checker must not share one blind spot |
| 5 | Default mode | Single lead with subagents; team mode only on escalation | Team runs cost several times more |
| 6 | Team coordination | Files plus orchestrator synthesis; no peer messaging | Antigravity subagents run isolated from each other |
| 7 | Autonomy | Free inside an isolated worktree and branch; review gate for rules, skills, agent files, evals and merges | Autonomy where reversible, gates where not |
| 8 | Proof of learning | Benchmark with and without lessons, held-out tasks, automatic rollback | Otherwise learning is only a story |

## 3. Antigravity platform mapping

These findings come from public documentation and guides as of late October 2026. Paths differ between surfaces and versions, so Phase 0 must verify every row against the official documentation at antigravity.google/docs before anything depends on it.

| Capability | Location or mechanism | Confidence |
| --- | --- | --- |
| Surfaces | Desktop app (2.0), CLI (`agy`), IDE, SDK. Desktop and CLI share one agent harness | High |
| Rules | `GEMINI.md` or `AGENTS.md` in project root (GEMINI.md wins on conflict); global `~/.gemini/GEMINI.md`; `.agents/rules/*.md`. 12,000 character cap per rule file | Medium-high |
| Skills | `.agents/skills/<name>/SKILL.md` (older `.agent/skills` still read). `description` required, `name` optional, optional `scripts/`, `examples/`, `resources/`. Triggered by the agent matching the description | High |
| Global skills | `~/.gemini/config/skills/` (2.0 and CLI), `~/.gemini/antigravity/skills/` (IDE) | Medium |
| Custom agents | `.agents/agents/<name>.md` or `<name>/agent.md`; global `~/.gemini/config/agents/`. Frontmatter includes `mainAgent` and `hidden`. Reported as desktop and CLI only, not IDE | Medium |
| Subagents | Orchestrator defines and spawns them at runtime, in parallel, each with its own context and git worktree; the parent is notified on completion. Subagents do not message each other | Medium-high |
| Workflows and commands | Markdown macros triggered by a slash command; folder name varies by version (`.agents/workflows/` or `.agent/workflows/`) | Low-medium |
| MCP servers | `~/.gemini/antigravity/mcp_config.json` in the IDE; confirm for desktop and CLI | Medium |
| Hooks and scheduling | Event hooks and scheduled tasks exist in 2.0; the CLI has `/goal` and `/schedule` | Medium |

Consequences for this design:

- Use the `.agents/` spelling and fall back to `.agent/` only if the installed version requires it.
- Roles are custom agents. If your surface lacks custom agents (IDE), the same role files are loaded as skills and the orchestrator plays each role in turn, or you start one Agent Manager conversation per role by hand.
- Keep `GEMINI.md` under about 1,500 tokens because it is loaded on every prompt; put detail in skills.

## 4. Architecture

```
 user: /gsd or /team <feature>
          |
   Orchestrator (main agent)  <-- rules: GEMINI.md, .agents/rules/*
          |
   +------+---------------------------+
   |      |                           |
 Skills   Roles (custom agents)       MCP servers
 (how)    architect, verifier,        rag-mcp      -> adapter -> your RAG engine
          implementer, tester,        physmath-mcp -> sympy/numpy/scipy/pint sandbox
          reviewer, librarian
          |
   Git worktrees + branches  ->  PR (never main)
          |
   Traces -> librarian -> lessons (candidate -> verified -> retired)
          |
   evals/ harness measures pass rate, iterations, tokens, with and without lessons
```

Three stores sit behind the RAG adapter:

| Collection | Written by | Retrieved by default | Purpose |
| --- | --- | --- | --- |
| knowledge | humans only | yes | Curated derivations, numerical-methods references, project docs, solved problems |
| lessons | librarian only | yes (verified; candidates only when flagged unverified) | Distilled rules from past runs |
| traces | orchestrator | no | Raw run logs; input to the librarian and evals |

## 5. Repository layout

```
repo/
  GEMINI.md                    short identity, links to rules; under 1,500 tokens
  AGENTS.md                    shared conventions (build, test, style)
  docs/
    ARCHITECTURE.md            this document
    PLATFORM_NOTES.md          verified Antigravity paths and behaviour (Phase 0 output)
  .agents/
    rules/                     always-on and glob rules
    skills/                    SKILL.md folders
    agents/                    role definitions
    workflows/                 /gsd and /team (path verified in Phase 0)
    config/budgets.yaml        iteration, round, parallelism and token caps
  rag-adapter/                 interface, backend for your engine, stub backend, contract tests
  rag-mcp/                     MCP server exposing the adapter
  physmath-mcp/                MCP server: units, symbolic, invariants, convergence
  evals/
    tasks/                     benchmark tasks, each with fixture and hidden checks
    run.py                     runner (mode, lessons on or off)
    reports/
  decisions/                   debate records, one per team run
  team/                        per-run proposals, board and logs (gitignored except summaries)
  scripts/                     setup.ps1, start-agent-stack.ps1, doctor.ps1, rollback_lessons.py
```

## 6. Components

### 6.1 Rules

- `GEMINI.md`: project identity, the two commands, the rule that planning precedes code, links to detailed rules.
- `.agents/rules/`: one file each for workflow discipline; testing (test first, no skipped tests); safety and protected paths; lesson handling (never present a candidate lesson as fact, always cite the lesson ids used); and physics and maths conduct (units on every quantity, state assumptions, never hand-wave a derivation).
- Every rule file stays below the 12,000 character cap.

### 6.2 Skills

A skill is triggered by its description, so each description states when to use it.

| Skill | Use when | Core content |
| --- | --- | --- |
| rag-retrieval | Before planning any task | Query formation, collection filters, injecting at most 5 lessons within about 1,500 tokens, recording which ids were used |
| plan-and-tasks | Producing a plan | Plan template, task slicing, risk and escalation flags |
| tdd-loop | Implementing a task | Red, green, refactor; iteration cap; what counts as done |
| code-review | Reviewing a diff | Checklist against plan, tests, style, security |
| physics-conduct | Any task touching physical quantities | Units, conventions, conservation laws, limiting cases, sanity ranges |
| numerical-methods | Discretisation, solvers, integration | Stability, order of accuracy, tolerances, floating point pitfalls, convergence studies |
| maths-verification | Formulas, derivations, proofs | Symbolic equivalence, counterexample search, edge domains |
| domain-spec-first | Verifier role | Deriving acceptance checks from the spec before reading code |
| lesson-writing | Librarian role | Rule form (when X do Y because Z), evidence fields, dedupe, contradiction check |
| team-debate | `/team` | Debate protocol, file formats, round caps |
| eval-authoring | Adding benchmark tasks | Task layout, hidden checks, held-out discipline |

### 6.3 Roles (custom agents)

| Role | Responsibility | Write access | Authority |
| --- | --- | --- | --- |
| orchestrator | Intake, routing, budgets, synthesis, final report | traces, board | Decides escalation to team mode |
| architect | Design options, tradeoffs, decision record | `decisions/` | Proposes; orchestrator decides |
| physmath-verifier | Derives checks from the spec; runs physmath tools; reviews numerics | `tests/physmath/` | Veto: blocks merge until checks pass or the spec changes |
| implementer | Test-first implementation inside its worktree and file scope | source and tests in scope | None |
| adversarial-tester | Tries to break the implementation: edge cases, property tests | `tests/adversarial/` | Can reopen tasks |
| reviewer | Reviews the diff against plan and rules | none | Can request changes |
| librarian | Distils traces into lessons; manages promotion and demotion | lessons collection only | Sole writer of lessons |

Assign the strongest reasoning model your plan offers to the verifier and architect; cheaper, faster models suit the librarian and routine implementation.

### 6.4 Commands

**`/gsd <feature>`**

1. Intake: restate the goal and acceptance criteria; list assumptions; proceed unless something blocking is missing.
2. Retrieve: `rag_search` on knowledge and lessons, plus a repository scan.
3. Plan: write `PLAN.md` as an artifact, citing the lesson ids used, with tasks and a risk score.
4. Domain spec: if physical or mathematical content is involved, the verifier writes checks before implementation starts.
5. TDD loop per task, capped by `budgets.yaml`.
6. Verify: full tests, physmath checks, lint.
7. Review: reviewer pass; fix or justify each finding.
8. Learn: librarian writes candidate lessons and the trace.
9. Report: summary artifact and a PR on a feature branch.

Escalate to `/team` when three or more modules are touched, the plan fails review, the verifier flags ambiguous maths, or one task fails twice.

**`/team <feature>`**

- Phase A, debate: the orchestrator spawns architect, physmath-verifier and adversarial-tester in parallel, each with a self-contained prompt. Each writes `team/<run-id>/proposals/<role>.md`. A critique round follows in which each role reads the others' files and writes a rebuttal. Two rounds maximum. The orchestrator writes a decision record to `decisions/<run-id>.md`.
- Phase B, build: the orchestrator splits the work into non-overlapping file scopes on `team/<run-id>/board.md` and spawns up to three implementers, each in its own worktree.
- Phase C, integrate: merge branches one at a time; run full verification after each merge.
- Phase D, review and learn: reviewer, verifier final pass, librarian, report and PR.

### 6.5 RAG adapter and lesson store

Adapter interface (Python, backend-agnostic):

```
search(query, collections, filters, k) -> list[Hit]
upsert(collection, doc_id, text, metadata) -> None
get(collection, doc_id) -> Doc
set_status(collection, doc_id, status, reason) -> None
delete(collection, doc_id) -> None        # not exposed over MCP
```

MCP tools exposed by `rag-mcp`: `rag_search`, `rag_upsert_lesson`, `rag_record_use`, `rag_promote`, `rag_demote`, `rag_stats`. Only the librarian role and the rollback script may call write tools; enforce this in the role definitions and with a server-side allow check.

Lesson record:

```
id: L-2026-10-0001
title: short imperative
rule: When <situation>, do <action>, because <reason>
domain: [physics, numerics, infra, python]
evidence: {task_id, commit, tests: [ids], review: passed}
status: candidate | verified | retired
created_at, last_used_at
use_count, success_count, fail_count
supersedes: [ids]
```

Lifecycle:

- Create: always as `candidate`, and only after a run whose tests pass.
- Promote to `verified`: evidence tests green, and either the PR merged without a revert or one later reuse succeeded.
- Retire: two failures with a success ratio under 50 percent, a detected contradiction with a verified lesson or knowledge entry, or no use for 90 days. Retired lessons are kept but never retrieved.
- Write-time checks: duplicate detection by similarity, contradiction check against existing verified lessons, schema validation.
- Retrieval: exclude retired; prefer verified; show candidates only when marked unverified; cap at 5 lessons.
- A lesson never overrides a failing test or a failed physmath check.

### 6.6 physmath-mcp tools

Each tool runs supplied code or expressions in a subprocess with a timeout, a memory limit where the OS allows, and no network.

| Tool | What it does |
| --- | --- |
| units\_check | Dimensional consistency of an expression or function given units for its symbols (pint) |
| sym\_equiv | Symbolic equivalence of two expressions under assumptions, with a numeric sampling fallback (sympy) |
| sym\_solve | Differentiate, integrate, solve or series-expand, returning the result and a verification residual |
| numeric\_compare | Compare two implementations, or an implementation and a reference, over a domain with tolerances |
| invariant\_check | Run a simulation or function repeatedly and report drift in a conserved quantity (energy, momentum, mass) |
| convergence\_study | Refine a step or grid parameter and report the observed order of accuracy against the expected order |
| limit\_check | Evaluate behaviour at limits and special cases (zero, infinity, symmetric cases) against expected asymptotics |

Results are structured (pass or fail, numbers, tolerance used) so the verifier can cite them in its report.

### 6.7 Safety and autonomy

| Free | Needs human approval |
| --- | --- |
| Read the repo; edit inside own worktree; run tests and physmath tools; write candidate lessons; open PRs | Edits to `.agents/**`, `GEMINI.md`, `AGENTS.md`, `evals/**`; merging to main; installing dependencies; network access beyond an allowlist; deleting lessons outside the rollback script |

- Never push to main. Force-push and recursive deletion are blocked by a command guard (a hook if available, otherwise a workflow check plus the terminal command policy).
- The protected-paths list lives in `.agents/rules/safety.md` and is enforced by the reviewer.
- `budgets.yaml` sets iterations per task (4), debate rounds (2), parallel implementers (3), plus time and token ceilings. On breach the orchestrator stops and reports.
- Parallel subagents get non-overlapping file scopes, since two agents editing one file will collide.

## 7. Evaluation

- 24 tasks to start: 6 pure coding, 5 maths, 5 physics or numerics, 4 multi-module features, and 4 held-out tasks that are never used to produce lessons.
- Each task has a fixture, a description and hidden checks the agent cannot read.
- `evals/run.py --mode single|team --lessons on|off` records pass or fail, iterations, wall time, tokens when available, and the lesson ids retrieved.
- Gates: lessons-on must not lower the pass rate on held-out tasks, and should cut iterations on repeated-pattern tasks by 10 percent or more. If either gate fails, `rollback_lessons.py` demotes lessons created since the last passing run.
- A weekly scheduled run writes a report to `evals/reports/`.

## 8. Roadmap

| Phase | Build | Accepted when |
| --- | --- | --- |
| 0 Foundations | Verify platform paths and write PLATFORM\_NOTES; repo skeleton; GEMINI.md and rules; adapter with stub and real backend; `rag-mcp`; `physmath-mcp` with units\_check, sym\_equiv, numeric\_compare; setup and doctor scripts | Adapter round trip passes against the real engine; both MCP servers appear as tools in Antigravity; unit and contract tests green; `doctor.ps1` all green |
| 1 Single agent | Skills; roles orchestrator, implementer, reviewer, physmath-verifier; `/gsd`; eval harness with 8 tasks | At least 6 of 8 tasks completed without human input; each run leaves a plan, a report and a trace |
| 2 Learning loop | Librarian; lesson lifecycle; promotion and rollback; remaining physmath tools | Lifecycle rules covered by tests; an injected bad lesson is demoted by rollback; held-out pass rate does not drop |
| 3 Team mode | Architect and adversarial-tester; `/team`; board and decision records; full 24-task suite | Team beats single mode on the hard subset at an acceptable cost, or the report says it does not |
| 4 Hardening | Hooks, budget enforcement, scheduled eval, retrieval tracing report, documentation pass | A budget breach stops a run; the weekly report is generated unattended |

Each phase ends with a written report, and the next phase starts only after approval.

## 9. Windows operations

- Python 3.11 or newer in a project virtual environment; MCP servers launch through the absolute path to that interpreter in the MCP config.
- `scripts/start-agent-stack.ps1` starts the MCP servers and checks the RAG engine; hook it into the PowerShell profile if automatic startup is wanted.
- Run `git config core.longpaths true`; use `pathlib` everywhere; avoid POSIX-only file locking.
- Skills and agents are plain Markdown, so the same folders can be installed globally for reuse across projects.

## 10. Open items

- RAG engine details: stack, query interface, auth, embedding model. Needed before Phase 0 can finish the real backend.
- Physics and maths scope: simulation and numerical code, mathematical derivation, or both.
- Antigravity surface in use (desktop 2.0, CLI or IDE), since custom agents are reportedly not available in the IDE.
- Target language and test framework (assumed Python and pytest).
- Model availability on your plan, for assigning model tiers to roles.

## 11. Kickoff prompt for Antigravity

Save this document as `docs/ARCHITECTURE.md`, fill the bracketed fields, then paste the following into the orchestrating agent.

```
You are the lead engineer for a new project: a self-learning coding agent built on Google Antigravity. The full specification is in docs/ARCHITECTURE.md. Read it completely before doing anything else. It is the source of truth; if you believe it is wrong, say so in your report instead of silently deviating.

Environment facts (filled in by me):
- RAG engine: [stack, e.g. vector store and embedding model]
- How it is queried: [HTTP endpoint or library call, with an example]
- Auth: [name of the environment variable holding the credential; never write secrets into files]
- Language and test framework: [default Python 3.11 and pytest]
- Physics and maths scope: [e.g. mechanics simulation, numerical ODE and PDE solvers, linear algebra, proofs]
- Antigravity surface I am using: [desktop 2.0, CLI or IDE]
- OS: Windows with PowerShell

Your task is Phase 0 only. Do not start Phase 1.

Step 1, platform verification. Consult the official Antigravity documentation and your own environment. Confirm where rules, skills, custom agents, workflows and MCP configuration live for my surface, whether custom agents and subagents are available, and the rule file size limit. Write the findings, with the source for each, to docs/PLATFORM_NOTES.md. Where section 3 of docs/ARCHITECTURE.md disagrees with what you verified, use what you verified and list the differences.

Step 2, plan. Produce an implementation plan for Phase 0 as an artifact: tasks, file list, test list and risks. Do not wait for approval; proceed, but keep the plan updated as you work.

Step 3, build, test first. Create the repository layout from section 5. Implement, writing tests before the code:
- rag-adapter: the interface, a stub in-memory backend, a backend for my RAG engine, and contract tests that run against both.
- rag-mcp: the MCP server with the tools in section 6.5, with write tools restricted as specified.
- physmath-mcp: units_check, sym_equiv and numeric_compare, running supplied code in a subprocess with a timeout and no network.
- GEMINI.md (under 1,500 tokens), AGENTS.md and the rule files from section 6.1, each under the rule size limit.
- scripts: setup.ps1, start-agent-stack.ps1, doctor.ps1.
- Register both MCP servers with Antigravity and confirm they appear as available tools.

Constraints:
- Work on a feature branch in an isolated worktree. Never push to main.
- After the initial creation, do not edit anything under .agents, GEMINI.md or AGENTS.md without flagging it in your report.
- No secrets in files or logs. Read credentials from environment variables only.
- Ask me a question only if a missing fact blocks progress, and ask all blocking questions at once. Otherwise state your assumption and continue.
- If a step fails twice, stop that step, record what you tried, and move on to whatever is independent.

Definition of done for Phase 0:
- The adapter round trip (upsert, search, set_status, get) passes against my real RAG engine.
- Both MCP servers appear as tools in Antigravity, and each tool has been called successfully once.
- All unit and contract tests pass; show the output.
- doctor.ps1 reports every check green.

Finish with a Phase 0 report as an artifact: what was built, test results, what differs from the specification, open risks, and your proposed task list for Phase 1. Then stop and wait for my approval.
```

## Sources consulted

Public Antigravity documentation and guides, including Google's product overview and skills codelab, plus independent write-ups on custom agents, subagents and rules, read in October 2026. Re-verify any path or limit before relying on it.
