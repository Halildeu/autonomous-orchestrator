# Board Setup Decision (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-1B target GitHub Project decision  
Current mode: docs-only; no GitHub Project, issue, PR, workflow, or source/runtime mutation is authorized by this document alone

## 1. Decision

Initial adoption should use a new, narrow GitHub Project dedicated to
governance/roadmap-visible work for this repo family.

Recommended working title:

```text
autonomous-orchestrator Governance Board
```

This decision does not create the Project. It only selects the target strategy
for later dry-run tooling and operator-approved live setup.

## 2. Decision Status

| Item | Decision |
|---|---|
| Target type | new GitHub Project |
| Initial scope | curated governance, risk, gate, roadmap-visible work |
| Intake rule | `project-roadmap` label only |
| Existing Project reuse | not selected for initial adoption |
| Live creation | not authorized |
| Live field creation | not authorized |
| Live issue/PR mutation | not authorized |
| Next implementation mode | dry-run/read-only preflight first |

## 3. Rationale

A new narrow Project is safer for the first rollout because it avoids hidden
coupling with existing board fields, existing automations, or broad intake
rules.

It also preserves the operating boundaries already defined:

- board state does not override repo SSOT,
- board is not an intake firehose,
- normal PRs do not auto-enter the board,
- `Needs Verify` is an acceptance queue,
- `Done` requires evidence plus deliberate close,
- live GitHub writes require explicit operator boundary.

Existing Project reuse can be revisited after dry-run inventory proves that its
fields, labels, automations, and owner permissions match this contract.

## 4. Options Considered

| Option | Decision | Reason |
|---|---|---|
| New narrow Project | selected | lowest conflict risk; clean field contract; easy rollback |
| Existing Project | rejected for initial rollout | field names/options/automations may conflict; needs inventory first |
| No Project | rejected | loses active work visibility and claim/verification queue benefits |
| Broad auto-add Project | rejected | violates curated board and `project-roadmap` gate |

## 5. Initial Board Contract

The board must implement the field and label contract in:

```text
docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md
```

Required fields:

| Field | Type | Options source |
|---|---|---|
| `Status` | single select | BOG-1A field contract |
| `Faz` | single select | BOG-1A field contract |
| `Track` | single select | BOG-1A field contract |
| `Priority` | single select | BOG-1A field contract |
| `Kind` | single select | BOG-1A field contract |

Required labels:

- `project-roadmap`
- `risk`
- `gate`
- `needs-verification`
- `blocked`
- `security`
- `quality`

Only `project-roadmap` is allowed to act as board ingestion signal.

## 6. Dry-Run Preflight Before Live Setup

Before any live Project creation or mutation, a dry-run/read-only preflight must
produce a report with these checks:

- authenticated GitHub identity,
- target owner account,
- repository owner/name,
- whether a same-title Project already exists,
- whether an existing selected Project has conflicting fields,
- whether required labels already exist on the repository,
- whether token/PAT scopes are sufficient,
- whether any live write would be needed,
- whether live writes are explicitly authorized for that run.

The preflight must fail closed if identity, owner, token scope, or target board
ambiguity cannot be resolved.

## 7. Existing Project Conflict Criteria

If an existing Project is reconsidered later, it must pass all criteria below
before it can replace the new-board decision:

- no broad auto-add workflow that ingests every issue or PR,
- field names match the BOG-1A contract exactly or have an explicit mapping,
- field option names match the BOG-1A contract exactly or have an explicit
  mapping,
- no automation auto-marks runtime/governance issues as `Done`,
- no automation closes issues from PR merge for runtime/governance work,
- `Needs Verify` can be represented without conflicting with existing workflow,
- existing owners accept that repo SSOT remains authority,
- dry-run drift report is reviewed before any apply mode.

Failing any criterion keeps the initial new-board decision in force.

## 8. Rollout Boundary

BOG-1B authorizes only the planning decision.

It does not authorize:

- creating a GitHub Project,
- editing an existing GitHub Project,
- creating labels,
- editing issues,
- editing PRs,
- adding workflows,
- adding live GitHub write scripts.

Those actions belong to later BOG steps and require dry-run evidence plus
explicit operator approval.

## 9. BOG-1B Acceptance

BOG-1B is `REVIEW_READY` when:

- this file exists,
- it chooses new vs existing Project for initial adoption,
- it states why the other options are not selected,
- it defines dry-run/preflight requirements,
- it defines existing Project conflict criteria,
- `BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md` records this decision,
- `SSOT-MAP.md` links this decision,
- schema/policy/doc-nav checks still pass,
- no GitHub Project, issue, PR, workflow, or source/runtime mutation was made.

BOG-1B is not live-active until the operator explicitly authorizes a separate
live setup step after preflight evidence.
