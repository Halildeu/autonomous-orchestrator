# Repo Layout SSOT (v1)

This doc defines which top-level directories and files are acceptable in the repo root.
Goal: prevent uncontrolled growth and keep generated artifacts in the right place.

## Generated vs tracked
- Generated: produced during runs (e.g., `.cache/`, `dist/`, `sim_report*.json`).
- Tracked: part of SSOT (`docs/`, `schemas/`, `policies/`, `roadmaps/`).

## Codex config (SSOT)
Repo-local Codex config lives under `.codex/` and is tracked as SSOT.

v0.1 behavior:
- Warn-only: no auto delete or move.
- Hygiene reports only warn and provide manual suggestions.

## Ambiguous / dual locations
The dual location of `modules/` vs `src/modules/` is allowed but must be documented.
If both exist, hygiene reports an `AMBIGUOUS_DIR` warning.

## Packs
`packs/` is an SSOT root for pack manifests and examples.

## Generated artifact rules
Root-level report files (e.g., `sim_report*.json`) are flagged as WARN.
Preferred location: `.cache/reports/` or the workspace root.

## Workspace project boundary (SSOT)
Workspace artifacts must live under `WS/project/<project_id>/`.
`WS/.cache/` is derived-only (state, reports, indexes).

## Roadmap split (SSOT)
Core SSOT roadmap: `roadmaps/SSOT/`.
Project roadmaps (core‑etkilemeyen): `roadmaps/PROJECTS/`.

## SSOT source
Machine-readable layout: `docs/OPERATIONS/repo-layout.v1.json`.
