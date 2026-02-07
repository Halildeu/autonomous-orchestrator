# PRJ-PORTFOLIO-TRACKING (doc-only v0.1)

## Purpose
Provide a program-led portfolio view across project manifests without changing core runtime behavior.

## Scope
- Read project manifests under roadmaps/PROJECTS/README.md.
- Summarize status, open actions, and next focus deterministically.
- Surface results in portfolio-status and system-status.

## Non-goals
- No core unlock or core writes.
- No network calls.
- No runtime behavior changes beyond reporting.

## Single Gate (program-led)
- Portfolio status is produced by the program and reported in AUTOPILOT CHAT.
- The user does not type commands.

## Expected Evidence
- .cache/reports/portfolio_status.v1.json
