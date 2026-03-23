---
globs: roadmaps/**
---
# Roadmap Rules

- Canonical file: `roadmaps/SSOT/roadmap.v1.json`
- Never edit silently; always use Change Proposal (CHG) process
- Version bump on every edit (semver patch for content, minor for structure)
- Milestones have: id, title, status (open/in_progress/done), target_date
- Hash change triggers auto-rerun of dependent milestones
- Evidence: roadmap changes recorded in `.cache/reports/`
