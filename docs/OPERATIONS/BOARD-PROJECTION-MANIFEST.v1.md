# Board Projection Manifest (v1)

Status: REVIEW_READY
Started: 2026-06-17
Scope: BOG-5A board projection manifest design
Current mode: design-only; no schema, source/runtime, GitHub Project, issue,
label, workflow, or live sync mutation is authorized by this document alone

## 1. Purpose

This document defines the future `board_projection.v1` manifest.

The manifest is a one-way expected-state projection from repo authority to a
GitHub Project board. It is not a new SSOT.

Primary goals:

- make expected board fields deterministic;
- make missing board fields visible;
- detect invalid `Done`, `Needs Verify`, `Blocked`, and close-keyword states;
- bind projection output to source evidence with a digest;
- support dry-run drift reporting before any operator-bound apply mode.

## 2. Authority Model

Authority order:

1. `AGENTS.md`
2. `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
3. `docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md`
4. `docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md`
5. `docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md`
6. `docs/OPERATIONS/BOARD-PR-MERGE-EVIDENCE-WORKFLOW.v1.md`
7. `roadmaps/SSOT/roadmap.v1.json`
8. `roadmaps/PROJECTS/*/project.manifest.v1.json`
9. live GitHub issue/PR/Project inventory as observed evidence

Live board state is evidence, not authority. Board edits do not rewrite repo
SSOT. Any mismatch becomes drift.

## 3. Manifest Location

Initial dry-run output should be workspace-scoped:

```text
.cache/ws_customer_default/.cache/reports/board_projection.v1.json
```

Future checked-in schema, if authorized:

```text
schemas/board-projection.schema.v1.json
```

Future checked-in projection snapshots should not be introduced by default.
Projection is generated evidence, so committing snapshots requires a separate
CHG/DCP-style decision.

## 4. Source Inputs

The generator should read:

- board governance docs listed in `SSOT-MAP.md`;
- field and label contract;
- issue body contract;
- PR template contract;
- PR merge evidence workflow contract;
- roadmap/project manifests;
- open GitHub issues with `project-roadmap`;
- current GitHub ProjectV2 items for the target board;
- PR bodies linked through `Tracked by #N`.

The generator must record every source path or external inventory query used.

## 5. Manifest Shape

Minimum shape:

```json
{
  "version": "v1",
  "kind": "board_projection",
  "generated_at": "2026-06-17T00:00:00Z",
  "repo": "owner/name",
  "board_title": "autonomous-orchestrator Governance Board",
  "mode": "report",
  "authority": {
    "repo_ssot_is_authority": true,
    "board_is_authority": false,
    "issue_body_is_handoff_surface": true
  },
  "source_refs": [],
  "field_contract": {
    "required_fields": ["Status", "Faz", "Track", "Priority", "Kind"],
    "required_labels": [
      "project-roadmap",
      "risk",
      "gate",
      "needs-verification",
      "blocked",
      "security",
      "quality"
    ]
  },
  "expected_items": [],
  "observed_board_items": [],
  "drift": [],
  "digest": {
    "algorithm": "sha256",
    "canonicalization": "json-stable-sort-v1",
    "value": ""
  },
  "evidence": {
    "source": [],
    "desired_state": [],
    "runtime_live": [],
    "browser_user_path": [],
    "does_not_prove": [
      "Live board mutation has not been applied.",
      "Runtime acceptance is not proven by projection."
    ]
  }
}
```

Rules:

- `does_not_prove` must never be empty.
- `expected_items` is the intended board projection.
- `observed_board_items` is a read-only inventory snapshot.
- `drift` is the comparison result.
- digest covers normalized projection inputs, not volatile timestamps.

## 6. Expected Item Shape

Minimum item shape:

```json
{
  "issue_number": 123,
  "title": "Short board item title",
  "ssot_ref": "roadmaps/SSOT/roadmap.v1.json#RM-SSOT-001",
  "owner_repo": "owner/name",
  "desired_fields": {
    "Status": "Todo",
    "Faz": "M0",
    "Track": "github-ops",
    "Priority": "P1",
    "Kind": "issue"
  },
  "desired_labels": ["project-roadmap"],
  "relation_policy": {
    "pr_relation": "Tracked by",
    "close_keyword_allowed": false,
    "default_post_merge_status": "Needs Verify"
  },
  "claim_policy": {
    "claimable": true,
    "non_claimable_reasons": []
  },
  "evidence_requirements": {
    "source": "required-before-needs-verify",
    "desired_state": "required-when-config-or-gitops",
    "runtime_live": "required-before-done-when-runtime",
    "browser_user_path": "required-before-done-when-user-facing",
    "does_not_prove": "required"
  },
  "digest_inputs": {
    "issue_body_agent_state": true,
    "field_contract_version": "v1",
    "pr_contract_version": "v1"
  },
  "digest": "sha256:..."
}
```

## 7. Field Derivation Rules

| Field | Source |
|---|---|
| `Status` | issue body `agent-state:v1`, board status, PR merge evidence, verification evidence |
| `Faz` | roadmap/project manifest phase, explicit issue field, or BOG adoption plan |
| `Track` | project manifest, issue body, or field contract option |
| `Priority` | roadmap priority, issue body, or explicit triage |
| `Kind` | issue body, label, or issue template contract |

Missing derivation is drift. The generator must not invent critical fields.

Default status derivation:

| Evidence | Desired status |
|---|---|
| label `project-roadmap`, no claim, triaged | `Todo` |
| active claim | `In Progress` |
| blocker comment or `blocked` label | `Blocked` |
| merged PR evidence, acceptance pending | `Needs Verify` |
| issue deliberately closed with complete evidence | `Done` |

`Done` cannot be derived from PR merge alone.

## 8. Drift Categories

Required drift categories:

| Code | Meaning |
|---|---|
| `MISSING_BOARD_ITEM` | `project-roadmap` issue is absent from board |
| `UNEXPECTED_BOARD_ITEM` | board item lacks `project-roadmap` |
| `MISSING_FIELD` | required board field is empty |
| `INVALID_FIELD_VALUE` | board field value not in contract |
| `AGENT_STATE_MISSING` | executable issue lacks `agent-state:v1` |
| `CLAIM_CONFLICT` | multiple active non-expired claims exist |
| `NEEDS_VERIFY_LABEL_MISMATCH` | status/label mismatch for `Needs Verify` |
| `BLOCKED_STATE_MISMATCH` | blocked status/comment/label mismatch |
| `FORBIDDEN_DONE` | item is `Done` without closure/evidence requirements |
| `FORBIDDEN_CLOSE_KEYWORD` | PR uses close keyword where `Tracked by` is required |
| `SSOT_REF_MISSING` | board item has no repo authority reference |
| `DIGEST_MISMATCH` | expected item digest differs from observed projection state |

Severity levels:

| Severity | Use |
|---|---|
| `ERROR` | unsafe contradiction or invalid closure |
| `WARN` | missing field, incomplete evidence, recoverable drift |
| `INFO` | advisory or non-blocking mismatch |

## 9. Digest Rules

Digest algorithm:

```text
sha256(json-stable-sort-v1(expected_item_without_volatile_fields))
```

Include:

- `issue_number`;
- `ssot_ref`;
- `desired_fields`;
- `desired_labels`;
- `relation_policy`;
- `evidence_requirements`;
- contract versions.

Exclude:

- `generated_at`;
- run URL;
- transient GitHub API pagination fields;
- claim heartbeat timestamp unless claim state is the tested condition;
- raw comment ordering unless order is semantically required.

The digest proves projection consistency only. It does not prove live board
mutation or runtime acceptance.

## 10. Dry-Run and Apply Boundary

BOG-5B may implement drift checking in report/dry-run mode.

BOG-5C operator-bound apply must require:

- accepted dry-run report digest;
- explicit target board title/id;
- token/PAT capability evidence;
- before/after inventory;
- mutation ledger;
- failure rollback or manual recovery note;
- no issue close automation;
- no `Done` automation for runtime/governance work.

Apply must be one-way:

```text
repo SSOT -> expected projection -> board fields/labels
```

Apply must not be:

```text
board fields -> repo SSOT
```

## 11. Test Requirements

BOG-5B implementation must test:

| Scenario | Expected result |
|---|---|
| missing required field | `MISSING_FIELD` |
| board item without `project-roadmap` | `UNEXPECTED_BOARD_ITEM` |
| roadmap issue absent from board | `MISSING_BOARD_ITEM` |
| `Needs Verify` without label | `NEEDS_VERIFY_LABEL_MISMATCH` |
| `Done` with pending `Does not prove` | `FORBIDDEN_DONE` |
| forbidden PR close keyword | `FORBIDDEN_CLOSE_KEYWORD` |
| malformed `agent-state:v1` | `AGENT_STATE_MISSING` or parse error |
| duplicate active claims | `CLAIM_CONFLICT` |
| changed expected field | `DIGEST_MISMATCH` |
| no token/live board unavailable | report-only with explicit limitation |

Tests must use fixtures and must not require live GitHub mutation.

Initial fixture examples:

- `fixtures/board/board_projection_happy.v1.json`
- `fixtures/board/board_projection_forbidden_done.v1.json`

## 12. BOG-5A Acceptance

BOG-5A is `REVIEW_READY` when:

- this file exists;
- authority order is defined;
- manifest location is defined;
- source inputs are defined;
- top-level manifest shape is defined;
- expected item shape is defined;
- field derivation rules are defined;
- drift categories are defined;
- digest rules are defined;
- dry-run/apply boundary is defined;
- test requirements are defined;
- no schema, source/runtime, GitHub Project, issue, label, workflow, or live sync
  mutation was made.

BOG-5A is not drift checker implementation. BOG-5B must implement a report/dry-run
checker under the active write boundary before any sync apply is considered.
