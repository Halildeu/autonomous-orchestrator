# Board Governance Adoption Plan (v1)

Status: DONE
Started: 2026-06-17
Current step: BOG-12 managed repo rollout contract
Current step status: DONE
Parallel docs/source progress: BOG-3B through BOG-12 DONE
Implementation boundary: BOG-3D DONE
Machine-readable contracts: BOG-5A-S/P DONE
Side effects allowed in current step: managed repo rollout contract docs, standards.lock distribution set, PRJ-GITHUB-OPS extension references, product catalog, release notes, SSOT map update, managed repo dry-run/apply reports for registered manifest targets, local gate validation
Side effects not allowed in current step: unregistered repo mutation; ungated GitHub mutation; additional issue/PR mutation beyond already accepted `#78`; historical backlog backfill; source writes outside an evidenced source window

## 1. Objective

Adopt a trackable board governance line for this repo without breaking the
existing SSOT-first, fail-closed operating model.

The plan starts with written operating rules, then issue/PR contracts, then
scripts, then workflow automation, and only later ProjectV2 drift/mirror sync.

## 2. Non-Negotiable Rules

- Repo SSOT remains authority.
- Board is curated, not an intake queue.
- `project-roadmap` label gates board ingestion.
- `Kind=umbrella` is not claimable.
- `Backlog` is not claimable.
- PR merge does not imply `Done`.
- Runtime/GitOps/governance work uses `Tracked by #N`, not `Closes #N`.
- `Needs Verify` means source-ready, acceptance pending.
- `Done` requires evidence plus deliberate issue close.
- Live GitHub write automation starts after dry-run and explicit operator boundary.

## 3. Status Vocabulary

| Status | Use |
|---|---|
| `TODO` | not started |
| `IN_PROGRESS` | actively being written or implemented |
| `REVIEW_READY` | output exists and needs review/acceptance |
| `BLOCKED` | cannot move without external decision or missing prerequisite |
| `DONE` | accepted and no required work remains |
| `DEFERRED` | intentionally parked |

## 4. Action Register

| ID | Title | Status | Deliverable | Acceptance |
|---|---|---|---|---|
| BOG-0A | Docs-only baseline | DONE | `BOARD-OPERATING-MODEL.v1.md` + this plan | files exist, no GitHub/workflow mutation |
| BOG-0B | Review adoption boundary | DONE | consultation `CNS-20260617-001` plus user continuation approval | user agrees to proceed beyond docs-only |
| BOG-1A | Board field contract | DONE | `BOARD-FIELD-LABEL-CONTRACT.v1.md` | Status/Faz/Track/Priority/Kind agreed |
| BOG-1B | Board setup decision | DONE | `BOARD-SETUP-DECISION.v1.md` | new narrow Project selected for initial adoption; no broad auto-add |
| BOG-2A | Issue template contract | DONE | `BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md` | `agent-state:v1`, evidence, safety, and future Issue Form boundaries defined |
| BOG-2B | PR template contract | DONE | `BOARD-PR-TEMPLATE-CONTRACT.v1.md` | `Tracked by` default and `Closes` exception documented |
| BOG-3A | Minimal board script design | DONE | `BOARD-SCRIPT-DESIGN.v1.md` | list/claim/heartbeat/release/verify/backlog-add scoped |
| BOG-3B | Dry-run script implementation | DONE | `BOARD-SCRIPT-IMPLEMENTATION-EVIDENCE.v1.md` | report/dry-run commands implemented; tests and gates pass; apply remains blocked |
| BOG-3C | Live script gated implementation | DONE | `BOARD-SCRIPT-GATED-APPLY-EVIDENCE.v1.md` | explicit confirmation, token/PAT boundary, fake-`gh` success path, and fail-closed behavior tested |
| BOG-3D | Implementation boundary run card | DONE | `BOARD-GOVERNANCE-IMPLEMENTATION-RUN-CARD.v1.md` | source/window allow_paths, validations, and stop conditions defined |
| BOG-4A | PR merge evidence workflow design | DONE | `BOARD-PR-MERGE-EVIDENCE-WORKFLOW.v1.md` | `pull_request.closed` + `Tracked by` parser specified |
| BOG-4B | PR merge evidence workflow implementation | DONE | `.github/workflows/board-pr-merge-evidence.yml` + `BOARD-PR-MERGE-EVIDENCE-WORKFLOW-IMPLEMENTATION-EVIDENCE.v1.md` | merged PR `Tracked by` parser, fake-`gh` Needs Verify path, idempotency, missing-token fallback, and no auto-`Done` tested |
| BOG-5A | Board projection manifest design | DONE | `BOARD-PROJECTION-MANIFEST.v1.md` | repo authority, digest, fields, labels defined |
| BOG-5A-S | Board projection schema | DONE | `schemas/board-projection.schema.v1.json` | manifest shape validates through schema gate |
| BOG-5A-P | Board governance policy | DONE | `policies/policy_board_governance.v1.json` + schema | invariants, automation boundary, projection, evidence policy validate |
| BOG-5A-F | Board projection fixtures | DONE | `fixtures/board/board_projection_*.v1.json` | happy path and forbidden Done drift examples validate against schema |
| BOG-5B | Drift checker dry-run | DONE | `BOARD-PROJECTION-DRIFT-EVIDENCE.v1.md` | projection command reports missing field and invalid Done drift; apply remains blocked |
| BOG-5C | Operator-bound sync apply | DONE | `BOARD-PROJECTION-SYNC-APPLY-EVIDENCE.v1.md` | accepted digest, target board id, metadata map, fake-`gh` apply path, before/after inventory, mutation ledger, and no auto-`Done` tested |
| BOG-6A | Live acceptance read-only probe | DONE | `BOARD-LIVE-ACCEPTANCE-PROBE-EVIDENCE.v1.md` | live `gh` auth/repo/project inventory is report-backed; target board absence and existing board field mismatch are visible; no live mutation |
| BOG-6B | Live setup dry-run/gated apply | DONE | `BOARD-LIVE-SETUP-EVIDENCE.v1.md` | `board-setup` dry-run plans missing target board create/link; fake apply path tested; confirmation/token/digest gates tested |
| BOG-6C | Real target board setup acceptance | DONE | `BOARD-LIVE-SETUP-EVIDENCE.v1.md` | ProjectV2 `#5` created; repo linked; field compatibility `OK`; sync/item population remains a later gate |
| BOG-7 | Live governed item seed acceptance | DONE | `BOARD-LIVE-ITEM-SEED-EVIDENCE.v1.md` | required labels created; issue `#78` created; ProjectV2 item added to `#5`; fields populated; no issue close or `Done` automation |
| BOG-8 | Live projection generation | DONE | `BOARD-LIVE-PROJECTION-EVIDENCE.v1.md` | live issue `#78` and ProjectV2 `#5` inventory generate schema-valid projection; drift `0`; no mutation |
| BOG-9 | Live sync validation | DONE | `BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md` | live metadata map generated; issue `#78` promoted to `Needs Verify` through accepted digest; final `board-sync` dry-run returns `OK`, `noop=true`, drift `0` |
| BOG-10 | Canonical router and review packaging | DONE | `AGENTS.md`, `CODEX-UX.md`, `BOARD-CANONICAL-ROUTER-PACKAGING-EVIDENCE.v1.md` | AGENTS canonical router names board governance docs/policy/workflow; user-facing board requests route to ops commands; review packaging boundary is explicit |
| BOG-11 | Product capability promotion | DONE | `BOARD-GOVERNANCE-CAPABILITY.v1.md`, `product_catalog.v1.json`, `PRJ-GITHUB-OPS` extension surface, release notes | Governance Board Capability v1 is versioned, active, cataloged, and explicitly bounded from managed-repo rollout |
| BOG-12 | Managed repo rollout contract | DONE | `BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`, `standards.lock`, `AI-MULTIREPO-OPERATING-CONTRACT.v1.md` | Governance Board Capability v1 is included in the managed-repo standards package; sync remains manifest-targeted and live GitHub mutation remains per-target gated |

## 5. Phase Plan

### Phase 0 — Written Boundary

Goal: Make the governance model explicit before any automation.

Deliverables:

- `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`
- `docs/OPERATIONS/SSOT-MAP.md` discovery entry

Exit criteria:

- The model states that board is not SSOT.
- The model states that board is not intake.
- The model states that PR merge is not `Done`.
- The adoption plan has trackable IDs and statuses.
- No GitHub Project, issue, PR, workflow, or source/runtime mutation is made.

Current status: DONE.

### Phase 1 — Minimal Board Contract

Goal: Decide the board fields and label gate.

Deliverables:

- field contract for `Status`, `Faz`, `Track`, `Priority`, `Kind`
- label contract for `project-roadmap`, `risk`, `gate`, `needs-verification`,
  `blocked`, `security`, `quality`
- target board decision: new Project or existing Project

Exit criteria:

- every board item type has a clear meaning,
- empty critical fields are considered tracking gaps,
- `project-roadmap` is the only ingestion label,
- normal PRs do not auto-enter the board.

Current status: DONE.

### Phase 2 — Issue and PR Contract

Goal: Make work handoff and PR closure semantics machine-readable.

Deliverables:

- issue template with `agent-state:v1`
- comment taxonomy
- PR template rule for `Tracked by`
- explicit `Closes` exception rule

Exit criteria:

- fresh sessions can continue from issue body,
- PR merge cannot silently close runtime/governance work,
- issue comments preserve append-only evidence,
- `Needs Verify` is the default post-merge state.

Current status: DONE.

### Phase 3 — Minimal Board Script

Goal: Move from manual discipline to deterministic local tooling.

Deliverables:

- `board-list`
- `board-claim`
- `board-heartbeat`
- `board-release`
- `board-verify`
- `board-backlog-add`
- dry-run mode
- fake-`gh` tests

Exit criteria:

- claim race is deterministic,
- stale claim can be detected,
- PAT missing behavior is fail-closed or report-only,
- board/body drift is reported, not hidden,
- no script marks runtime work `Done`.

Current status: DONE.

### Phase 4 — PR Merge Evidence Workflow

Goal: Let merged PRs move linked issues to `Needs Verify`.

Deliverables:

- PR merge workflow on `pull_request.closed`
- parser for `Tracked by`
- idempotent `EVIDENCE type=pr-merged`
- PAT missing fallback policy
- tests/harness

Exit criteria:

- merged PR creates source-ready evidence,
- eligible item moves to `Needs Verify`,
- `Done`, `Blocked`, and already `Needs Verify` items are not downgraded,
- missing PAT does not create board/body contradiction.

Current status: DONE.

### Phase 5 — Projection and Drift

Goal: Add the ao-kernel-style repo manifest to board mirror discipline.

Deliverables:

- `board_projection.v1.json` design
- board drift checker
- dry-run report
- operator-bound apply design

Exit criteria:

- repo manifest can derive expected board fields,
- missing/empty fields are visible,
- invalid `Done` and forbidden `Closes` patterns are reported,
- apply is not autonomous; accepted dry-run digest gates apply.

Current status: DONE.

### Phase 6 — Live Acceptance Probe

Goal: Replace assumptions about GitHub access and ProjectV2 shape with live,
read-only evidence before any mutation.

Deliverables:

- `board-live-probe`
- fake-`gh` read-only tests
- live repo/project owner inventory report
- existing board compatibility comparison

Exit criteria:

- token scopes are visible without secrets,
- repo access is proven,
- ProjectV2 owner inventory is proven,
- target board existence or absence is explicit,
- required field/option compatibility is explicit,
- no project, issue, label, or item mutation is made.

Current status: DONE.

## 6. Initial Adoption Order

Recommended PR order:

1. Docs-only baseline: operating model + adoption plan.
2. Field/label contract and templates.
3. Dry-run board script.
4. Live-gated board script.
5. PR merge evidence workflow.
6. Drift checker.
7. Operator-bound sync apply.
8. Live acceptance read-only probe.
9. Live setup dry-run/gated apply.
10. Real target board setup acceptance.
11. Live governed item seed acceptance.
12. Live projection generation from GitHub inventory.
13. Live sync validation, `Needs Verify` promotion, and final no-op dry-run.
14. Canonical AGENTS router integration and review packaging.
15. Product capability promotion under `PRJ-GITHUB-OPS`.
16. Managed repo rollout contract and standards package distribution.

## 7. Current Evidence

Docs-only baseline evidence:

- `docs/OPERATIONS/BOARD-OPERATING-MODEL.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md`
- `docs/OPERATIONS/SSOT-MAP.md`
- `docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-SETUP-DECISION.v1.md`
- `docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md`
- `docs/OPERATIONS/BOARD-SCRIPT-DESIGN.v1.md`
- `docs/OPERATIONS/BOARD-SCRIPT-IMPLEMENTATION-PROPOSAL.v1.md`
- `docs/OPERATIONS/BOARD-SCRIPT-IMPLEMENTATION-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-SCRIPT-GATED-APPLY-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-PR-MERGE-EVIDENCE-WORKFLOW.v1.md`
- `docs/OPERATIONS/BOARD-PR-MERGE-EVIDENCE-WORKFLOW-IMPLEMENTATION-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-DRIFT-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-PROJECTION-SYNC-APPLY-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-ACCEPTANCE-PROBE-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-SETUP-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-ITEM-SEED-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-PROJECTION-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-LIVE-SYNC-VALIDATION-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-CANONICAL-ROUTER-PACKAGING-EVIDENCE.v1.md`
- `docs/OPERATIONS/BOARD-ISSUE-78-ACCEPTANCE-CHECKLIST.v1.md`
- `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md`
- `docs/OPERATIONS/product_catalog.v1.json`
- `docs/OPERATIONS/release-notes-v0.4.0-rc.2.md`
- `docs/OPERATIONS/release-notes-v0.4.0-rc.1.md`
- `docs/OPERATIONS/release-notes-v0.3.0-rc.1.md`
- `extensions/PRJ-GITHUB-OPS/EXTENSION.md`
- `extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json`
- `docs/OPERATIONS/BOARD-GOVERNANCE-IMPLEMENTATION-RUN-CARD.v1.md`
- `schemas/board-projection.schema.v1.json`
- `schemas/policy-board-governance.schema.v1.json`
- `policies/policy_board_governance.v1.json`
- `fixtures/board/board_projection_happy.v1.json`
- `fixtures/board/board_projection_forbidden_done.v1.json`
- `fixtures/board/projection_missing_field.v1.json`
- `fixtures/board/board_apply_happy.v1.json`
- `fixtures/board/board_apply_missing_token.v1.json`
- `fixtures/board/board_apply_project_status.v1.json`
- `fixtures/board/pr_merge_event_merged.v1.json`
- `fixtures/board/pr_merge_event_unmerged.v1.json`
- `fixtures/board/pr_merge_event_no_tracked.v1.json`
- `fixtures/board/pr_merge_event_forbidden_close.v1.json`
- `fixtures/board/pr_merge_issues_happy.v1.json`
- `fixtures/board/pr_merge_issues_existing_marker.v1.json`
- `fixtures/board/board_sync_projection_status_drift.v1.json`
- `fixtures/board/board_sync_projection_done_forbidden.v1.json`
- `fixtures/board/board_sync_metadata_happy.v1.json`
- `fixtures/board/board_sync_metadata_missing_ids.v1.json`
- `fixtures/board/board_live_probe_project_list.v1.json`
- `fixtures/board/board_live_probe_field_list.v1.json`
- `fixtures/board/board_seed_bog7.v1.json`

Consultation evidence:

- `CNS-20260617-001`: OPEN `codex -> claude` planning consultation for board governance adoption review.
- User continuation approval on 2026-06-17: proceed in recommended order.
- BOG-1B decision: use a new narrow Project for initial adoption; no live GitHub mutation authorized.
- BOG-2A issue template contract: docs-only; no `.github/ISSUE_TEMPLATE` mutation authorized.
- BOG-2B PR template contract: docs-only; no `.github/PULL_REQUEST_TEMPLATE` mutation authorized.
- BOG-3A script design: docs-only; no script/ops command mutation authorized.
- BOG-3B implementation proposal: `src/**` write guardrail returned `CORE_UNLOCK=1 required for src/ writes`; no fake implementation performed.
- BOG-3B implementation evidence: `board-list`, `board-claim`, `board-heartbeat`,
  `board-release`, `board-verify`, and `board-backlog-add` registered through
  `src.ops.manage`; BOG-3B itself stayed report/dry-run only and did not
  implement live apply.
- BOG-3B test evidence: `python3 -m pytest tests/contract/test_board_commands.py -q`
  returned `10 passed`; `python3 ci/core_ops_contract_test.py` returned
  `{"status": "OK", "tests_passed": 10, "tests_failed": 0}`.
- BOG-3B gate evidence: `validate_schemas`, `policy-check`, and `doc-nav-check`
  returned OK after implementation.
- BOG-3B restore evidence: `.cache/ws_customer_default/.cache/reports/core_unlock_compliance.v1.json`;
  post-close write authorization for `src/ops/commands/board_cmds.py` returned
  `BLOCKED` with `core_unlock_active=false`.
- BOG-3C implementation evidence: `--mode apply` now requires explicit
  confirmation string `APPLY_BOARD_GOVERNANCE_BOG_3C`, a present token env, an
  available `gh` binary, repo identity, and apply-supported action metadata.
- BOG-3C safety evidence: missing confirmation and missing token return
  `BLOCKED` before any `gh` call; unsupported actions return `BLOCKED` before
  any `gh` call; `Done` automation and issue close remain unsupported.
- BOG-3C fake-`gh` evidence: supported `board-verify --mode apply` executes
  `gh issue comment` and `gh project item-edit` through a fake `gh` executable
  and records `applied_actions`.
- BOG-3C test evidence: `python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py -q`
  returned `18 passed`.
- BOG-4A PR merge evidence workflow design: docs-only design baseline.
- BOG-4B implementation evidence: `.github/workflows/board-pr-merge-evidence.yml`
  added; `board-pr-merge` command parses merged PR event payloads, extracts
  `Tracked by #N`, applies idempotent evidence, adds `needs-verification`, and
  can set ProjectV2 status when explicit metadata is present.
- BOG-4B safety evidence: missing token returns report-only fallback without
  `gh` calls; forbidden close keyword blocks before `gh` calls; existing marker
  avoids duplicate evidence comment; no issue close or `Done` action is emitted.
- BOG-4B test evidence: `python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py -q`
  returned `24 passed`.
- BOG-5A board projection manifest design: docs-only; no schema, source, Project,
  issue, label, workflow, or live sync mutation authorized.
- BOG-3D implementation run card: docs-only; no `src`, `.github`, schema, Project,
  issue, label, workflow, or live runtime mutation authorized.
- BOG-5A-S/P machine-readable contracts: schema/policy only; no source,
  workflow, GitHub Project, issue, label, or live sync mutation authorized.
- BOG-5A-F projection fixtures: workspace fixture examples only; no live GitHub
  inventory or mutation authorized.
- BOG-5B implementation evidence: `board-projection` registered through
  `src.ops.manage`; `apply` mode remains blocked until BOG-5C.
- BOG-5B drift evidence: happy projection returns `OK`; forbidden Done fixture
  returns `WARN` with `FORBIDDEN_DONE`; missing field fixture returns `WARN`
  with `MISSING_FIELD`.
- BOG-5B test evidence: `python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_projection.py -q`
  returned `14 passed`; `CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-5B board projection drift dry-run implementation' python3 ci/core_ops_contract_test.py`
  returned `{"status": "OK", "tests_passed": 10, "tests_failed": 0}`.
- BOG-5B gate evidence: `validate_schemas`, `policy-check`, and `doc-nav-check`
  returned OK after implementation.
- BOG-5B restore evidence: `.cache/ws_customer_default/.cache/reports/core_unlock_compliance_bog5b.v1.json`;
  post-close write authorization for `src/ops/board/projection.py` returned
  `BLOCKED` with `core_unlock_active=false`.
- BOG-5C implementation evidence: `board-sync` consumes a schema-valid
  `board_projection.v1` report plus an operator-provided ProjectV2 metadata
  map; `apply` requires accepted digest, target board id, explicit
  confirmation, token env, and `gh` availability.
- BOG-5C safety evidence: digest mismatch, missing token, missing metadata, and
  desired `Done` state all return `BLOCKED` before any `gh` call.
- BOG-5C sync evidence: fake-`gh` apply path sets ProjectV2 `Status=Needs Verify`,
  adds `needs-verification`, records before/after inventory, mutation ledger,
  and recovery note.
- BOG-5C test evidence: `python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py tests/contract/test_board_sync.py -q`
  returned `30 passed`.
- BOG-6A implementation evidence: `board-live-probe` registered through
  `src.ops.manage`; it allows only `gh auth status`, `gh repo view`,
  `gh project list`, `gh project view`, and `gh project field-list`.
- BOG-6A test evidence: `python3 -m pytest tests/contract/test_board_live_probe.py -q`
  returned `5 passed`.
- BOG-6A regression evidence: board command/apply/projection/pr-merge/sync/live-probe
  contract suite returned `35 passed`; core ops contract, schema validation,
  policy-check, and doc-nav-check returned OK.
- BOG-6A live repo evidence: `board-live-probe --repo Halildeu/autonomous-orchestrator --project-owner Halildeu`
  returned `WARN` with authenticated account `Halildeu`, required scopes
  `project` and `repo` present, repo permission `ADMIN`, and
  `PROJECT_NOT_FOUND_BY_NUMBER_OR_TITLE` for `autonomous-orchestrator Governance Board`.
- BOG-6A existing board comparison: `board-live-probe --project-number 2 --board-title 'platform Roadmap'`
  returned `WARN`; required fields exist, but `Faz` and `Track` options do not
  match the autonomous-orchestrator board contract.
- BOG-6B implementation evidence: `board-setup` registered through
  `src.ops.manage`; it plans target ProjectV2 creation, required field
  reconciliation, and optional repo link.
- BOG-6B safety evidence: `apply` requires `APPLY_BOARD_GOVERNANCE_BOG_6B`, a
  token env, and an accepted dry-run digest; missing confirmation, token, or
  digest blocks before mutation; existing field option mismatch blocks before mutation.
- BOG-6B fail-fast evidence: missing confirmation/token now blocks before any
  `gh` call; live preflight reports have empty `read_only_commands` and empty
  `mutation_commands`.
- BOG-6B digest evidence: missing accepted digest now blocks before any `gh`
  call; digest mismatch blocks before mutation after read-only recomputation.
- BOG-6C token-boundary evidence: custom `--token-env` values are bridged to
  child-process `GH_TOKEN` for board setup, live probe, board apply, and board
  sync; tests assert synthetic token values are not present in returned reports.
- BOG-6C auth preflight evidence: `board-auth-preflight` reports token
  readiness without mutation; missing `GITHUB_TOKEN` blocks before any `gh`
  call and keyring auth is not attempted by default.
- BOG-6C auth preflight test evidence: `python3 -m pytest tests/contract/test_board_auth_preflight.py -q`
  returned `5 passed`.
- BOG-6C live auth preflight evidence: `board-auth-preflight` returned
  `BLOCKED` with `TOKEN_ENV_MISSING:GITHUB_TOKEN`,
  `KEYRING_AUTH_NOT_ATTEMPTED`, and empty `read_only_commands`.
- BOG-6C explicit keyring preflight evidence: `board-auth-preflight --allow-keyring-auth --gh-timeout-seconds 10`
  returned `OK` for account `Halildeu` with required `project` and `repo`
  scopes present; no token value was recorded.
- BOG-6B test evidence: `python3 -m pytest tests/contract/test_board_setup.py -q`
  returned `8 passed`.
- BOG-6B regression evidence: board command/apply/projection/pr-merge/sync/live-probe/setup
  contract suite returned `48 passed`; core ops contract, schema validation,
  policy-check, and doc-nav-check returned OK.
- BOG-6B live dry-run evidence: `board-setup --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --mode dry-run --link-repo`
  returned `OK` with planned actions `create_project`,
  `reconcile_required_fields_after_create`, and `link_project_repo_after_create`;
  mutation commands were empty.
- BOG-6C live setup evidence: `board-setup --mode apply` with confirmation
  `APPLY_BOARD_GOVERNANCE_BOG_6B`, accepted digest
  `e4a3d24540cb5725d5bc1e33bc7a004e0945159532cdab51127214bbd3dcc7ea`,
  and token boundary returned `OK`.
- BOG-6C live mutation ledger: ProjectV2 `#5` was created at
  `https://github.com/users/Halildeu/projects/5`; `Status` options were
  reconciled with `updateProjectV2Field`; `Faz`, `Track`, `Priority`, and
  `Kind` were created; repo `Halildeu/autonomous-orchestrator` was linked.
- BOG-6C live acceptance probe: `board-live-probe --project-number 5` returned
  `OK`; field compatibility `OK`; missing fields/options none; item count `0`.
- BOG-6C projection boundary evidence: fixture projection dry-run returned
  `OK`; live item population was intentionally deferred to BOG-7.
- BOG-7 implementation evidence: `board-seed` registered through
  `src.ops.manage`; it consumes a repo-local `board_seed.v1` fixture and plans
  label, issue, ProjectV2 item, and field population actions.
- BOG-7 safety evidence: apply requires `APPLY_BOARD_GOVERNANCE_BOG_7A`,
  accepted seed digest, token env, ProjectV2 number, and ProjectV2 node id;
  missing digest/token blocks before any `gh` call.
- BOG-7 test evidence: `python3 -m pytest tests/contract/test_board_seed.py -q`
  returned `4 passed`; full board suite returned `52 passed`.
- BOG-7 live seed evidence: accepted digest
  `5a217d0ea37be5fbfc4c20e796278749bb10652537819342752a527f40b332be`
  applied successfully through `board-seed`.
- BOG-7 live mutation ledger: required board labels were created; issue `#78`
  was created at `https://github.com/Halildeu/autonomous-orchestrator/issues/78`;
  ProjectV2 item `PVTI_lAHOCx7tY84Ba38Czgv-mxA` was added to board `#5`;
  fields were set to `Status=Todo`, `Faz=F5 Projection Drift`,
  `Track=github-ops`, `Priority=P1`, `Kind=gate`.
- BOG-7 append-only issue evidence:
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725314501`.
- BOG-7 post-seed live probe: ProjectV2 `#5` items_total became `1`; field
  compatibility remained `OK`; missing fields/options none.
- BOG-8 implementation evidence: `board-projection-live` registered through
  `src.ops.manage`; it reads live GitHub issues with `project-roadmap` and
  ProjectV2 `#5` item inventory and emits schema-valid `board_projection.v1`.
- BOG-8 safety evidence: only `gh auth status`, `gh issue list`,
  `gh project field-list`, and `gh project item-list` are allowed; apply mode
  blocks before any `gh` call.
- BOG-8 test evidence: `python3 -m pytest tests/contract/test_board_live_projection.py -q`
  returned `3 passed`; full board suite returned `55 passed`.
- BOG-8 live projection evidence: `board-projection-live` returned `OK` with
  `expected_count=1`, `observed_count=1`, drift total `0`, and projection
  digest `d0fa8838e08959d46d7bd6886645ffbd2796df657e28bf1cef49b6a0f01ae506`.
- BOG-8 current projection after BOG-9 verification promotion returned `OK`
  with drift total `0` and projection digest
  `417b90e0a78d9dc2be553182bc2384522b924523a2262750cf2a86fa15e0cb0c`.
- BOG-9 implementation evidence: `board-metadata-live` registered through
  `src.ops.manage`; it reads ProjectV2 field/item inventory and emits a
  metadata map consumable by `board-sync`.
- BOG-9 sync behavior evidence: `board-sync` now treats an already synchronized
  projection as `OK` with `noop=true`, instead of blocking on no actions.
- BOG-9 test evidence: `python3 -m pytest tests/contract/test_board_metadata.py tests/contract/test_board_sync.py -q`
  returned `9 passed`.
- BOG-9 regression evidence: full board contract suite returned `58 passed`;
  core ops contract returned `{"status": "OK", "tests_passed": 10,
  "tests_failed": 0}`; `validate_schemas`, `policy-check`, `doc-nav-check`,
  and `git diff --check` returned OK.
- BOG-9 post-close write guard evidence: `write-authorize` for the BOG-7/8/9
  `src/` paths returned `BLOCKED` with `core_unlock_active=false`.
- BOG-9 live metadata evidence: `board-metadata-live` returned `OK` with
  `field_count=17`, `item_count=1`, metadata digest
  `59bf09b1109c5cc4cf0728839366ece08d729b750f6f961ab8823c961f10e5aa`.
- BOG-9 live verification promotion: issue `#78` body/label state was aligned
  to `Needs Verify`; `board-sync` dry-run planned one mutation, setting only
  ProjectV2 `Status=Needs Verify` for item
  `PVTI_lAHOCx7tY84Ba38Czgv-mxA`.
- BOG-9 live sync apply evidence: accepted projection digest
  `81626c00c971c8ee01e37a2a6bbd579a1e347fc124cf6d8448482eb086751f3f`
  applied successfully through `board-sync --mode apply` with confirmation
  `APPLY_BOARD_GOVERNANCE_BOG_3C`; mutation ledger contains one
  `set_project_field` entry; no issue close or `Done` action was emitted.
- BOG-9 append-only issue evidence:
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725408977`.
- BOG-9 final live sync evidence: `board-sync` against current live projection
  and live metadata returned `OK`, `noop=true`, drift total `0`, no planned
  actions, no applied actions, and empty mutation ledger.
- BOG-10 router evidence: `AGENTS.md` now names the board governance operating
  model, adoption plan, field/label contract, issue/PR contracts, projection
  manifest, policy, schema, and PR merge evidence workflow in the canonical
  SSOT router.
- BOG-10 UX evidence: `docs/OPERATIONS/CODEX-UX.md` now routes natural-language
  board requests to bounded ops commands; users still do not run shell commands.
- BOG-10 write-boundary evidence: `write-authorize` returned `PASS` for
  `AGENTS.md` and `.github/workflows/board-pr-merge-evidence.yml`.
- BOG-10 gate evidence: `doc-nav-check`, `policy-check`, `validate_schemas`,
  full board contract suite, core ops contract, live projection, live no-op
  sync, and `git diff --check` returned OK after router edits.
- BOG-10 merge evidence: PR `#79` merged to `main` as commit
  `ca59ad4fbbe0698214193dade523f17823f3ad77`; main push gates also passed.
- Final acceptance evidence: issue `#78` now has an explicit owner acceptance
  checklist at `docs/OPERATIONS/BOARD-ISSUE-78-ACCEPTANCE-CHECKLIST.v1.md`.
- Final closure evidence: issue `#78` is closed, ProjectV2 item status is
  `Done`, `needs-verification` was removed, and final evidence comment
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4727550151`
  records the deliberate acceptance boundary.
- BOG-11 product capability evidence:
  `docs/OPERATIONS/BOARD-GOVERNANCE-CAPABILITY.v1.md` promotes the model as
  `Governance Board Capability v1` under product surface `PRJ-GITHUB-OPS` for
  current release channel `0.4.0-rc.2`; historical promotion evidence remains
  recorded in `docs/OPERATIONS/release-notes-v0.3.0-rc.1.md`.
- BOG-11 catalog evidence: `docs/OPERATIONS/product_catalog.v1.json` includes
  `PRJ-GITHUB-OPS` as a `DONE`/`active` module with the governance board
  capability.
- BOG-11 extension evidence: `extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json`
  and `extensions/PRJ-GITHUB-OPS/EXTENSION.md` expose the capability context and
  program-led board ops.
- Manual request `REQ-20260616-c6d01b3ba13f`: source-window approval request
  created under workspace cache.
- Work intake `INTAKE-a6c7b2344efe54b723fddbc4d3aa614a82d0448d063f8d95b196c6f635331340`:
  selected and claimed by `codex-board-governance`; doer actionability reports
  `DECISION_NEEDED`.
- Decision seed `b3b2d51af084f21e872e2bba58017c5aaa7d72dd95db1f0d07d718fa0848350e`:
  `SCOPE_CONFIRM` for the BOG-3B source-write window; decision inbox default is
  `Keep blocked`.
- Decision inbox evidence:
  `.cache/ws_customer_default/.cache/index/decision_inbox.v1.json`.

Observed source patterns:

- `platform-k8s-gitops` uses board as active work/risk/gate status surface.
- `platform-k8s-gitops` uses `Tracked by` to avoid premature runtime closure.
- `platform-k8s-gitops` moves merged PR work to `Needs Verify`.
- `ao-kernel` uses one-way manifest mirror and drift checking for GitHub Project state.

## 8. Final Product Boundary

This plan is complete for the core product capability.

It did:

- create the narrow GitHub ProjectV2 `#5` for
  `autonomous-orchestrator Governance Board`,
- reconcile required ProjectV2 field families and options on that new board,
- link repo `Halildeu/autonomous-orchestrator` to the board,
- create required board labels,
- create governed issue `#78`,
- add issue `#78` to ProjectV2 `#5`,
- populate the seed item's five required board fields,
- promote issue `#78` and its ProjectV2 item to `Needs Verify` after live
  projection/sync evidence,
- adopt board governance into the AGENTS canonical router and CODEX-UX
  customer-friendly request map,
- deliberately accept and close issue `#78`,
- move the ProjectV2 item to `Done`,
- promote the model as `Governance Board Capability v1` under `PRJ-GITHUB-OPS`,
- expose the capability in the product catalog and release notes.

This plan still does not:

- edit existing non-target GitHub Project fields,
- create broad historical backlog issues,
- add ungated workflow automation,
- enable ungated live sync `apply` mode,
- silently roll the capability out to every managed repo,
- prove broader process adoption outside this repo.

BOG-3B, BOG-3C, BOG-4B, BOG-5B, BOG-5C, BOG-6A, and BOG-6B added allowlisted
local source/workflow/test/fixture code under evidenced source windows. Live
mutation paths remain gated by explicit confirmation, token env, target
metadata, and operator-provided digest/board inputs.

Final live state:

- ProjectV2 `#5` exists under owner `Halildeu`.
- ProjectV2 `#5` is field-compatible and has `1` governed item.
- Issue `#78` is closed.
- Issue `#78` labels are `gate`, `project-roadmap`, and `quality`.
- ProjectV2 item `PVTI_lAHOCx7tY84Ba38Czgv-mxA` has status `Done`.
- Live projection generation from actual issue/ProjectV2 inventory returns
  `OK` with drift `0`.
- `board-sync` still blocks desired `Done` automation with
  `DONE_AUTOMATION_FORBIDDEN`, which is the expected fail-closed boundary for
  automated closure.

Next separate gate:

- managed repo rollout and adoption validation using this capability as the
  source pattern.
