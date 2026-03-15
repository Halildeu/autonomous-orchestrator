"""Ops commands for domain profile management."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def cmd_domain_profile_list(args: argparse.Namespace) -> int:
    from src.ops.domain_profile_resolver import list_profiles

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    result = list_profiles(repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_domain_profile_resolve(args: argparse.Namespace) -> int:
    from src.ops.domain_profile_resolver import resolve_profile

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    result = resolve_profile(repo_root, args.profile_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "OK" else 2


def cmd_domain_profile_lanes(args: argparse.Namespace) -> int:
    from src.ops.domain_profile_resolver import generate_lane_config

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    result = generate_lane_config(repo_root, args.profile_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "OK" else 2


def register_domain_profile_subcommands(parent: Any) -> None:
    p_list = parent.add_parser("domain-profile-list", help="List available domain profiles")
    p_list.add_argument("--repo-root", default=".")
    p_list.set_defaults(func=cmd_domain_profile_list)

    p_resolve = parent.add_parser("domain-profile-resolve", help="Resolve a domain profile by ID")
    p_resolve.add_argument("--repo-root", default=".")
    p_resolve.add_argument("--profile-id", default="fullstack")
    p_resolve.set_defaults(func=cmd_domain_profile_resolve)

    p_lanes = parent.add_parser("domain-profile-lanes", help="Generate lane config for a profile")
    p_lanes.add_argument("--repo-root", default=".")
    p_lanes.add_argument("--profile-id", default="fullstack")
    p_lanes.set_defaults(func=cmd_domain_profile_lanes)
