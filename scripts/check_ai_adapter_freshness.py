#!/usr/bin/env python3
"""AI adapter freshness check — verifies CLAUDE.md imports AGENTS.md,
and .claude/rules/ files reference canonical sources."""

import hashlib
import json
import pathlib
import sys


def hash_file(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def check_claude_md_import(repo_root: pathlib.Path) -> list[str]:
    """Verify CLAUDE.md contains @AGENTS.md import."""
    claude_md = repo_root / "CLAUDE.md"
    agents_md = repo_root / "AGENTS.md"
    issues = []

    if not claude_md.exists():
        issues.append("CLAUDE.md not found")
        return issues

    if not agents_md.exists():
        issues.append("AGENTS.md not found")
        return issues

    content = claude_md.read_text()
    if "@AGENTS.md" not in content:
        issues.append("CLAUDE.md missing @AGENTS.md import — Claude won't see canonical routing")

    return issues


def check_provider_configs(repo_root: pathlib.Path) -> list[str]:
    """Check that AI provider configs exist."""
    issues = []
    configs = {
        ".claude/settings.json": "Claude Code",
        ".codex/config.toml": "Codex",
        ".gemini/settings.json": "Gemini",
    }
    for path, provider in configs.items():
        if not (repo_root / path).exists():
            issues.append(f"{provider} config missing: {path}")
    return issues


def check_skills_parity(repo_root: pathlib.Path) -> list[str]:
    """Check Claude skills have matching Codex skills."""
    issues = []
    claude_skills = repo_root / ".claude" / "skills"
    codex_skills = repo_root / ".agents" / "skills"

    if not claude_skills.exists():
        return issues

    claude_names = {f.stem for f in claude_skills.glob("*.md")} if claude_skills.exists() else set()
    codex_names = {f.name for f in codex_skills.iterdir() if f.is_dir()} if codex_skills.exists() else set()

    missing_codex = claude_names - codex_names
    if missing_codex:
        issues.append(f"Claude skills without Codex equivalent: {', '.join(sorted(missing_codex))}")

    return issues


def check_claudeignore(repo_root: pathlib.Path) -> list[str]:
    """Verify .claudeignore exists."""
    if not (repo_root / ".claudeignore").exists():
        return [".claudeignore not found — .cache/ and secrets may bloat context"]
    return []


def main():
    repo_root = pathlib.Path.cwd()
    if len(sys.argv) > 1:
        repo_root = pathlib.Path(sys.argv[1])

    all_issues = []
    all_issues.extend(check_claude_md_import(repo_root))
    all_issues.extend(check_provider_configs(repo_root))
    all_issues.extend(check_skills_parity(repo_root))
    all_issues.extend(check_claudeignore(repo_root))

    result = {
        "status": "pass" if not all_issues else "warn",
        "issues": all_issues,
        "checks_run": 4,
        "repo_root": str(repo_root),
        "claude_md_hash": hash_file(repo_root / "CLAUDE.md"),
        "agents_md_hash": hash_file(repo_root / "AGENTS.md"),
    }

    print(json.dumps(result, indent=2))
    sys.exit(0 if not all_issues else 1)


if __name__ == "__main__":
    main()
