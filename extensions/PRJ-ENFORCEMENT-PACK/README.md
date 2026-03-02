# PRJ-ENFORCEMENT-PACK (ENF v1)

V1 mode: **extension-only**.

- Extension single-gate wiring is `enforcement-check` via `extension-run` (P2).
- No CI (`.github/**`) wiring and no pre-commit wiring in V1 (defer to V2).
- Network is expected to be OFF.

## Contents

- `contract/enforcement-check.schema.v1.json`: Canonical enforcement-check JSON Schema (tool-agnostic).
- `contract/enforcement-check.example.v1.json`: Example payload.
- `contract/false_positive_baseline.v1.json`: Canonical sampled false-positive baseline template.
- `semgrep/rules/*.yaml`: Semgrep OSS rule skeletons for EP-001..EP-005.

## Running Semgrep offline (manual)

This repo does not wire Semgrep into CI/pre-commit in V1.
If you have Semgrep OSS available locally, you can run a single rule file against a target directory:

- Example (one rule):
  - `semgrep --config extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules/ep001_boundary_breach.yaml --json --output .cache/ws_customer_default/.cache/reports/semgrep.ep001.v1.json <TARGET_PATHS>`

For delta-based workflows, compute a file list from git diff and scan only those paths.

## Mapping results to the enforcement-check contract

Semgrep output is not the canonical contract.
The canonical contract is the JSON schema in `contract/` and the adapter (V2+) will:

1. Read Semgrep JSON output.
2. Normalize findings into `violations[]`.
3. Classify each violation as `DELTA`, `BASELINE`, or `OUT_OF_SCOPE`.
4. Emit an `enforcement-check` report that conforms to `enforcement-check.schema.v1.json`.

P1 contract hardening additionally standardizes:

- `stats.self_hit`: rule self-hit guard summary (exclude globs + violations count).
- `stats.false_positive_baseline`: sampled baseline summary for strict-profile readiness.

## EP rules (skeleton)

The following files are placeholders and intentionally match nothing until implemented:

- EP-001: `semgrep/rules/ep001_boundary_breach.yaml`
- EP-002: `semgrep/rules/ep002_structure_align.yaml`
- EP-003: `semgrep/rules/ep003_contract_drift.yaml`
- EP-004: `semgrep/rules/ep004_allow_paths_hitchhiking.yaml`
- EP-005: `semgrep/rules/ep005_evidence_check.yaml`
