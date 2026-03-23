# CLAUDE.md — autonomous-orchestrator (control-plane)

## Identity
Python 3.11+ JSON-first orchestrator control-plane.
176 schemas, 70 policies, 240+ ops commands. Fail-closed, deterministic, offline-first.

## Multi-Agent Coordination
- **AGENTS.md** is the canonical router for all agents (ops commands, SSOT navigation, core_lock)
- This file adds Claude Code-specific behavior only
- Other agents: Codex (OpenAI), Antigravity (Google) — all share AGENTS.md as single source of truth
- Output format: AUTOPILOT CHAT (PREVIEW / RESULT / EVIDENCE / ACTIONS / NEXT) — see AGENTS.md

## Core Lock (Summary)
- `core_lock=ON` by default — src/** writes BLOCKED
- Unlock: `CORE_UNLOCK=1` + `CORE_UNLOCK_REASON` required
- Allowlisted paths: schemas/, policies/, extensions/, docs/OPERATIONS/, roadmaps/SSOT/
- All writes produce evidence artifacts

## Context Bootstrap
On new sessions, get current state:
```
python -m src.ops.manage system-status --workspace-root .cache/ws_customer_default
python -m src.ops.manage portfolio-status --workspace-root .cache/ws_customer_default
```

## Validation Commands
Run before committing:
- Schema: `python ci/validate_schemas.py`
- Policy: `python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json`
- Standards: `python ci/check_standards_lock.py`
- Tests: `pytest tests/ -x`
- Lint: `ruff check src/ ci/ scripts/`

## Build & Run
- Install: `pip install -e ".[dev]"`
- Cockpit UI: `python extensions/PRJ-UI-COCKPIT-LITE/server.py --port 8787`
- Cockpit API: `python -m src.ops.manage cockpit-serve --workspace-root .cache/ws_customer_default --port 8790`

## Worktree Conventions
- Branch naming: `claude/<worktree-name>`
- Always work in worktree for non-trivial changes
- Run validation before commit (schema + standards + tests)

## Code Conventions
- JSON: 2-space indent, UTF-8, no trailing whitespace
- Versioned files: `*.v1.json`; schemas: `*.schema.v1.json` or `*.schema.json`
- Secrets: never commit credentials/tokens/keys
- Imports: use `src.shared.utils` (load_json, write_json_atomic, now_iso8601, hash_string)
- New files < 800 lines (script-budget enforced)
- Python: type hints, docstrings for public functions
- Error handling: fail-closed, always produce structured error output

## Workspace
- Default: `.cache/ws_customer_default/`
- Reports: `.cache/ws_customer_default/.cache/reports/*.v1.json`
- Index: `.cache/ws_customer_default/.cache/index/`
- Context bootstrap if missing: `python -m src.ops.manage workspace-bootstrap`

## SSOT Layers
- L0 CORE: Motor, gates, validation (locked)
- L1 CATALOG: Persistent rules, formats, policies, packs
- L2 WORKSPACE: Reports, caches, overrides, job indexes
- L3 EXTERNAL: Customer deliverables

## Priority Framework (User Preferences)
- P0: Crash consistency, atomic writes, corruption detection
- P1: Failure visibility, structured logging, health signals
- P2: State machine, schema migration, determinism
- P3: OTEL, Vault, decision policy engine

## Language
- User communicates in Turkish; respond in Turkish for conversation
- Code, comments, variable names: English
- Docs: Turkish or English based on existing file language

## Path-Specific Rules
See `.claude/rules/` for detailed conventions per directory.
