# CLAUDE.md — dev repo (managed execution repo)

@AGENTS.md

## Claude Code-Specific (AGENTS.md'de olmayan)

### Multi-Agent Worktree Zorunluluğu (MUST — İLK KONTROL)

**Bu repoda birden fazla agent aynı anda çalışır. Canonical tree'de (`/Documents/dev`) çalışma YASAKTIR.**

Oturum başında şunu kontrol et:
1. `git rev-parse --git-dir` vs `git rev-parse --git-common-dir` — aynıysa canonical tree'desin
2. `git worktree list --porcelain | grep -c '^worktree '` — 1'den fazlaysa side worktree'ler aktif

**Eğer canonical tree'deysen ve side worktree varsa:**
- Commit/push hook tarafından BLOCKED
- Yeni worktree aç: `git worktree add /Users/halilkocoglu/Documents/dev-claude-<task> -b feat/claude-<task> main`
- O worktree'ye geç ve orada çalış

**Eğer zaten bir worktree'deysen:** Devam et, hook'lar light mode çalışır.

### Build & Run
- Install: `pip install -e ".[dev]"`
- Cockpit UI: `python extensions/PRJ-UI-COCKPIT-LITE/server.py --port 8787`
- Cockpit API: `python -m src.ops.manage cockpit-serve --workspace-root .cache/ws_customer_default --port 8790`

### Worktree Conventions
- Branch naming: `feat/claude-<task>`, `fix/claude-<task>`
- Her branch main'den açılır (zincirleme yok)
- Worktree kendi `.cache/` altına yazar (canonical `.cache` paylaşımı yok)
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
