# CLAUDE.md — autonomous-orchestrator (control-plane)

@AGENTS.md

## Claude Code-Specific (AGENTS.md'de olmayan)

### Build & Run
- Install: `pip install -e ".[dev]"`
- Cockpit UI: `python extensions/PRJ-UI-COCKPIT-LITE/server.py --port 8787`
- Cockpit API: `python -m src.ops.manage cockpit-serve --workspace-root .cache/ws_customer_default --port 8790`

### Worktree Conventions
- Branch naming: `claude/<worktree-name>`
- Always work in worktree for non-trivial changes
- Run validation before commit (schema + standards + tests)

### Code Conventions (Claude-only ek)
- Imports: use `src.shared.utils` (load_json, write_json_atomic, now_iso8601, hash_string)
- New files < 800 lines (script-budget enforced)
- Python: type hints, docstrings for public functions
- Error handling: fail-closed, always produce structured error output

### Language
- User communicates in Turkish; respond in Turkish for conversation
- Code, comments, variable names: English
- Docs: Turkish or English based on existing file language

### Path-Specific Rules
See `.claude/rules/` for detailed conventions per directory.
