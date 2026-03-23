---
globs: scripts/sync_*, docs/OPERATIONS/AI-MULTIREPO*
---
# Cross-Repo Rules

- Orchestrator is SSOT owner: schemas/, policies/, standards.lock are canonical
- Sync: `python scripts/sync_managed_repo_standards.py --dry-run` before pushing
- Verify: `python ci/check_standards_lock.py --repo-root <target>`
- Decision inheritance: parent (orchestrator) decisions flow to child (dev)
- Parent wins on conflict (SSOT-first principle)
- Context health: `python scripts/check_context_health.py`
- Never modify synced files in managed repo directly
