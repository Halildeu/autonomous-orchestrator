"""Decision registry ops — capture, check, and sync architectural decisions.

Programmatic decision management:
- decision-capture: create/update topic + auto-sync registry
- decision-check: verify target path against active decisions

Usage (CLI):
    # Capture a new decision
    python -m src.ops.manage decision-capture \
        --topic-id zanzibar-openfga \
        --decision "OpenFGA kullan" \
        --rationale "Codex istişaresi" \
        --status FINAL

    # Add rejected alternative
    python -m src.ops.manage decision-capture \
        --topic-id zanzibar-openfga \
        --reject "Kendi engine yaz" \
        --reject-reason "Bakım maliyeti yüksek" \
        --tried-count 2

    # Check decisions for a target path
    python -m src.ops.manage decision-check \
        --target-path policies/policy_autonomy.v1.json

    # List all active topics
    python -m src.ops.manage decision-check --list
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.shared.utils import load_json, write_json_atomic, now_iso8601

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DECISIONS_DIR = _REPO_ROOT / "decisions"
_TOPICS_DIR = _DECISIONS_DIR / "topics"
_REGISTRY_PATH = _DECISIONS_DIR / "registry.v1.json"


def _load_registry() -> dict[str, Any]:
    if _REGISTRY_PATH.exists():
        return load_json(_REGISTRY_PATH)
    return {"version": "v1", "topics": []}


def _load_topic(topic_id: str) -> dict[str, Any] | None:
    path = _TOPICS_DIR / f"{topic_id}.v1.json"
    if path.exists():
        return load_json(path)
    return None


def _save_topic(topic_id: str, topic: dict[str, Any]) -> Path:
    _TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    path = _TOPICS_DIR / f"{topic_id}.v1.json"
    write_json_atomic(path, topic)
    return path


def _sync_registry(topic_id: str, topic: dict[str, Any]) -> None:
    """Auto-sync registry index after topic change."""
    registry = _load_registry()
    topics = registry.get("topics", [])

    # Update or add entry
    found = False
    for entry in topics:
        if entry.get("topic_id") == topic_id:
            entry["title"] = topic.get("title", "")
            entry["status"] = topic.get("status", "ACTIVE")
            entry["revision"] = topic.get("revision", 1)
            entry["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            found = True
            break

    if not found:
        topics.append({
            "topic_id": topic_id,
            "title": topic.get("title", topic_id),
            "status": topic.get("status", "ACTIVE"),
            "path": f"decisions/topics/{topic_id}.v1.json",
            "revision": topic.get("revision", 1),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    registry["topics"] = topics
    write_json_atomic(_REGISTRY_PATH, registry)


def _next_decision_id(topic: dict[str, Any]) -> str:
    decisions = topic.get("decisions", [])
    max_num = 0
    for d in decisions:
        did = d.get("decision_id", "D-000")
        try:
            num = int(did.split("-")[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            pass
    return f"D-{max_num + 1:03d}"


def capture_decision(
    *,
    topic_id: str,
    title: str | None = None,
    decision: str | None = None,
    rationale: str | None = None,
    decision_status: str = "FINAL",
    reject: str | None = None,
    reject_reason: str | None = None,
    tried_count: int = 1,
    constraint: str | None = None,
    related_path: str | None = None,
    cross_repo_ref: str | None = None,
) -> dict[str, Any]:
    """Capture a decision, rejection, or constraint for a topic."""
    topic = _load_topic(topic_id)
    created = topic is None

    if topic is None:
        topic = {
            "version": "v1",
            "topic_id": topic_id,
            "title": title or topic_id,
            "status": "ACTIVE",
            "revision": 1,
            "decided_at": now_iso8601(),
            "decided_by": [],
            "decisions": [],
            "constraints": [],
            "rejected_alternatives": [],
            "related_paths": [],
            "cross_repo_refs": [],
            "supersedes": None,
            "superseded_by": None,
            "change_log": [],
        }

    # Add decision
    if decision:
        did = _next_decision_id(topic)
        topic["decisions"].append({
            "decision_id": did,
            "statement": decision,
            "rationale": rationale or "",
            "status": decision_status,
        })
        topic["revision"] = topic.get("revision", 0) + 1
        topic["change_log"].append({
            "revision": topic["revision"],
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "change": f"Added {did}: {decision[:80]}",
        })

    # Add rejected alternative
    if reject:
        existing = [r for r in topic.get("rejected_alternatives", []) if r.get("alternative") == reject]
        if existing:
            existing[0]["tried_count"] = existing[0].get("tried_count", 0) + tried_count
            if reject_reason:
                existing[0]["reason"] = reject_reason
        else:
            topic.setdefault("rejected_alternatives", []).append({
                "alternative": reject,
                "reason": reject_reason or "",
                "tried_count": tried_count,
            })
        topic["revision"] = topic.get("revision", 0) + 1
        topic["change_log"].append({
            "revision": topic["revision"],
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "change": f"Rejected: {reject[:80]} (tried {tried_count}x)",
        })

    # Add constraint
    if constraint and constraint not in topic.get("constraints", []):
        topic.setdefault("constraints", []).append(constraint)

    # Add related path
    if related_path and related_path not in topic.get("related_paths", []):
        topic.setdefault("related_paths", []).append(related_path)

    # Add cross-repo ref
    if cross_repo_ref and cross_repo_ref not in topic.get("cross_repo_refs", []):
        topic.setdefault("cross_repo_refs", []).append(cross_repo_ref)

    if title and title != topic.get("title"):
        topic["title"] = title

    path = _save_topic(topic_id, topic)
    _sync_registry(topic_id, topic)

    return {
        "status": "OK",
        "action": "created" if created else "updated",
        "topic_id": topic_id,
        "revision": topic["revision"],
        "decisions_count": len(topic.get("decisions", [])),
        "rejected_count": len(topic.get("rejected_alternatives", [])),
        "path": str(path),
    }


def check_decisions(*, target_path: str) -> dict[str, Any]:
    """Check active decisions related to a target path."""
    registry = _load_registry()
    related = []

    for entry in registry.get("topics", []):
        if entry.get("status") != "ACTIVE":
            continue
        topic = _load_topic(entry["topic_id"])
        if topic is None:
            continue

        paths = topic.get("related_paths", []) + topic.get("cross_repo_refs", [])
        match = any(target_path in p or p in target_path for p in paths)

        if match:
            decisions = [d for d in topic.get("decisions", []) if d.get("status") == "FINAL"]
            rejected = topic.get("rejected_alternatives", [])
            related.append({
                "topic_id": topic["topic_id"],
                "title": topic.get("title", ""),
                "revision": topic.get("revision", 0),
                "decisions": [{"id": d["decision_id"], "statement": d["statement"]} for d in decisions],
                "rejected": [{"alternative": r["alternative"], "tried_count": r.get("tried_count", 0)} for r in rejected],
                "constraints": topic.get("constraints", []),
            })

    return {
        "status": "OK",
        "target_path": target_path,
        "related_topics": len(related),
        "topics": related,
    }


def list_topics() -> dict[str, Any]:
    """List all decision topics."""
    registry = _load_registry()
    return {
        "status": "OK",
        "topics": registry.get("topics", []),
        "total": len(registry.get("topics", [])),
    }


# ── CLI ───────────────────────────────────────────────────────────

def register_decision_registry_subcommands(sub: argparse._SubParsersAction) -> None:
    # decision-capture
    cap = sub.add_parser("decision-capture", help="Capture a new architectural decision")
    cap.add_argument("--topic-id", required=True, help="Kebab-case topic identifier")
    cap.add_argument("--title", default=None, help="Human-readable topic title")
    cap.add_argument("--decision", default=None, help="Decision statement to add")
    cap.add_argument("--rationale", default=None, help="Why this decision was made")
    cap.add_argument("--decision-status", default="FINAL", choices=["FINAL", "TENTATIVE"])
    cap.add_argument("--reject", default=None, help="Alternative to reject")
    cap.add_argument("--reject-reason", default=None, help="Why this alternative was rejected")
    cap.add_argument("--tried-count", type=int, default=1, help="How many times this was tried")
    cap.add_argument("--constraint", default=None, help="Constraint to add")
    cap.add_argument("--related-path", default=None, help="Related repo path")
    cap.add_argument("--cross-repo-ref", default=None, help="Cross-repo reference")
    cap.set_defaults(func=_cmd_decision_capture)

    # decision-check
    chk = sub.add_parser("decision-check", help="Check decisions for a target path")
    chk.add_argument("--target-path", default=None, help="Repo-relative target path")
    chk.add_argument("--list", action="store_true", help="List all topics")
    chk.set_defaults(func=_cmd_decision_check)


def _cmd_decision_capture(args: argparse.Namespace) -> int:
    result = capture_decision(
        topic_id=args.topic_id,
        title=args.title,
        decision=args.decision,
        rationale=args.rationale,
        decision_status=args.decision_status,
        reject=args.reject,
        reject_reason=args.reject_reason,
        tried_count=args.tried_count,
        constraint=args.constraint,
        related_path=args.related_path,
        cross_repo_ref=args.cross_repo_ref,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_decision_check(args: argparse.Namespace) -> int:
    if args.list:
        result = list_topics()
    elif args.target_path:
        result = check_decisions(target_path=args.target_path)
    else:
        result = list_topics()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
