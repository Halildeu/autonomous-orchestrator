from __future__ import annotations

import argparse


def register_planner_and_intake_subcommands(
    parent: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    cmd_planner_notes_create,
    cmd_planner_notes_delete,
    cmd_preflight_stamp,
    cmd_work_item_lease_seed,
    cmd_doer_loop_lock_seed,
    cmd_doer_loop_lock_status,
    cmd_doer_loop_lock_clear,
    cmd_work_intake_select,
    cmd_work_intake_claim,
    cmd_work_intake_close,
    cmd_work_intake_autoselect,
    cmd_doer_actionability,
) -> None:
    ap_notes_create = parent.add_parser("planner-notes-create", help="Create a planner note (workspace-only).")
    ap_notes_create.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_notes_create.add_argument("--title", default="", help="Note title.")
    ap_notes_create.add_argument("--body", default="", help="Note body.")
    ap_notes_create.add_argument("--tags", default="", help="Comma-separated tags.")
    ap_notes_create.add_argument("--links-json", dest="links_json", default="", help="Links JSON array.")
    ap_notes_create.set_defaults(func=cmd_planner_notes_create)

    ap_notes_delete = parent.add_parser("planner-notes-delete", help="Delete a planner note (workspace-only).")
    ap_notes_delete.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_notes_delete.add_argument("--note-id", dest="note_id", required=True, help="Note id (NOTE-<sha>).")
    ap_notes_delete.set_defaults(func=cmd_planner_notes_delete)

    ap_preflight = parent.add_parser("preflight-stamp", help="Write or read preflight stamp (no-wait safe gate).")
    ap_preflight.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_preflight.add_argument("--mode", default="write", help="write|read (default: write).")
    ap_preflight.set_defaults(func=cmd_preflight_stamp)

    ap_lease_seed = parent.add_parser(
        "work-item-lease-seed",
        help="Seed a deterministic lease for one intake item (workspace-only).",
    )
    ap_lease_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_lease_seed.add_argument("--intake-id", required=False, help="Intake id to lock (optional).")
    ap_lease_seed.add_argument("--ttl-seconds", default="900", help="Lease TTL seconds (default: 900).")
    ap_lease_seed.add_argument("--owner", default="planner-proof", help="Lease owner (default: planner-proof).")
    ap_lease_seed.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_lease_seed.set_defaults(func=cmd_work_item_lease_seed)

    ap_doer_lock_seed = parent.add_parser(
        "doer-loop-lock-seed",
        help="Seed the doer loop lock for proof (workspace-only).",
    )
    ap_doer_lock_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doer_lock_seed.add_argument("--ttl-seconds", default="600", help="Lock TTL seconds (default: 600).")
    ap_doer_lock_seed.add_argument("--owner", default="chat-proof", help="Lock owner tag (default: chat-proof).")
    ap_doer_lock_seed.add_argument("--run-id", required=False, help="Optional run_id override.")
    ap_doer_lock_seed.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_doer_lock_seed.set_defaults(func=cmd_doer_loop_lock_seed)

    ap_doer_lock_status = parent.add_parser(
        "doer-loop-lock-status",
        help="Show doer loop lock status (workspace-only).",
    )
    ap_doer_lock_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doer_lock_status.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_doer_lock_status.set_defaults(func=cmd_doer_loop_lock_status)

    ap_doer_lock_clear = parent.add_parser(
        "doer-loop-lock-clear",
        help="Clear doer loop lock (owner or stale, workspace-only).",
    )
    ap_doer_lock_clear.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doer_lock_clear.add_argument("--owner", default="", help="Owner tag to clear (default: empty).")
    ap_doer_lock_clear.add_argument(
        "--mode",
        default="owner_or_stale",
        help="owner_or_stale|owner_only|stale_only (default: owner_or_stale).",
    )
    ap_doer_lock_clear.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_doer_lock_clear.set_defaults(func=cmd_doer_loop_lock_clear)

    ap_intake_select = parent.add_parser("work-intake-select", help="Select intake items for autopilot apply.")
    ap_intake_select.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_select.add_argument("--mode", default="select", help="select|clear (default: select).")
    ap_intake_select.add_argument("--backup", default="false", help="true|false (default: false).")
    ap_intake_select.add_argument("--intake-id", required=False, help="Intake id to select/deselect.")
    ap_intake_select.add_argument("--selected", default="true", help="true|false (default: true).")
    ap_intake_select.set_defaults(func=cmd_work_intake_select)

    ap_intake_claim = parent.add_parser(
        "work-intake-claim",
        help="Claim/release one intake item for exclusive focus (workspace-only, TTL-based).",
    )
    ap_intake_claim.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_claim.add_argument("--intake-id", dest="intake_id", required=True, help="Intake id to claim/release.")
    ap_intake_claim.add_argument("--mode", default="claim", help="claim|release|status (default: claim).")
    ap_intake_claim.add_argument("--ttl-seconds", dest="ttl_seconds", default="3600", help="Claim TTL seconds (default: 3600).")
    ap_intake_claim.add_argument("--owner-tag", dest="owner_tag", default="", help="Owner tag (default: env CODEX_CHAT_TAG).")
    ap_intake_claim.add_argument("--force", default="false", help="true|false (default: false; release only).")
    ap_intake_claim.set_defaults(func=cmd_work_intake_claim)

    ap_intake_close = parent.add_parser(
        "work-intake-close",
        help="Explicitly close/reopen one intake item (workspace-only, manual-request tickets only).",
    )
    ap_intake_close.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_close.add_argument("--intake-id", dest="intake_id", required=True, help="Intake id to close/reopen.")
    ap_intake_close.add_argument("--mode", default="close", help="close|reopen|status (default: close).")
    ap_intake_close.add_argument("--reason", default="", help="Optional close reason (default: empty).")
    ap_intake_close.add_argument("--owner-tag", dest="owner_tag", default="", help="Owner tag (default: env CODEX_CHAT_TAG).")
    ap_intake_close.add_argument("--force", default="false", help="true|false (default: false).")
    ap_intake_close.set_defaults(func=cmd_work_intake_close)

    ap_intake_autoselect = parent.add_parser(
        "work-intake-autoselect",
        help="Auto-select eligible intake items for autopilot apply (deterministic).",
    )
    ap_intake_autoselect.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_autoselect.add_argument("--limit", default="3", help="Max items to select (default: 3).")
    ap_intake_autoselect.add_argument("--mode", default="policy", help="policy|safe_first (default: policy).")
    ap_intake_autoselect.add_argument("--scope", default="", help="policy|safe_only (alias for --mode).")
    ap_intake_autoselect.set_defaults(func=cmd_work_intake_autoselect)

    ap_doer_actionability = parent.add_parser(
        "doer-actionability",
        help="Summarize doer actionability (program-led, workspace-only).",
    )
    ap_doer_actionability.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doer_actionability.add_argument("--out", default="auto", help="Report JSON output path (default: auto).")
    ap_doer_actionability.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_doer_actionability.set_defaults(func=cmd_doer_actionability)
