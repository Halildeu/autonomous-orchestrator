#!/usr/bin/env python3
"""AI Config Ecosystem Contract Test.

Validates the complete AI configuration ecosystem:
- CLAUDE.md structure and @AGENTS.md import
- .claudeignore patterns
- .claude/settings.json hooks and permissions
- .claude/rules/ glob-scoped conventions
- .claude/skills/ user-invocable skills
- .claude/agents/ specialized subagents
- .agents/skills/ Codex skills parity
- Provider configs (.codex/, .gemini/)
- Cross-config consistency
"""

import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _fail(msg: str, issues: list[str]) -> None:
    issues.append(msg)


# ─── Tier 1: CLAUDE.md + AGENTS.md Integration ───


def test_claude_md_exists(issues: list[str]) -> None:
    p = REPO_ROOT / "CLAUDE.md"
    if not p.exists():
        _fail("CLAUDE.md not found at repo root", issues)
        return
    content = p.read_text()
    if len(content.strip()) < 10:
        _fail("CLAUDE.md is empty or near-empty", issues)


def test_claude_md_imports_agents(issues: list[str]) -> None:
    p = REPO_ROOT / "CLAUDE.md"
    if not p.exists():
        return
    content = p.read_text()
    if "@AGENTS.md" not in content:
        _fail("CLAUDE.md missing @AGENTS.md import — Claude won't see canonical routing", issues)


def test_claude_md_size_limit(issues: list[str]) -> None:
    """CLAUDE.md + AGENTS.md combined should be < 200 lines."""
    claude = REPO_ROOT / "CLAUDE.md"
    agents = REPO_ROOT / "AGENTS.md"
    if not claude.exists() or not agents.exists():
        return
    total = len(claude.read_text().splitlines()) + len(agents.read_text().splitlines())
    if total > 200:
        _fail(f"CLAUDE.md + AGENTS.md = {total} lines (limit: 200) — context bloat risk", issues)


def test_agents_md_exists(issues: list[str]) -> None:
    if not (REPO_ROOT / "AGENTS.md").exists():
        _fail("AGENTS.md not found — canonical router missing", issues)


def test_agents_md_has_required_sections(issues: list[str]) -> None:
    p = REPO_ROOT / "AGENTS.md"
    if not p.exists():
        return
    content = p.read_text()
    required = ["Customer-friendly mode", "SSOT Entrypoint Map", "Context Bootstrap"]
    for section in required:
        if section not in content:
            _fail(f"AGENTS.md missing required section: '{section}'", issues)


# ─── Tier 2: .claudeignore ───


def test_claudeignore_exists(issues: list[str]) -> None:
    if not (REPO_ROOT / ".claudeignore").exists():
        _fail(".claudeignore not found — .cache/ and secrets may bloat context", issues)


def test_claudeignore_excludes_sensitive(issues: list[str]) -> None:
    p = REPO_ROOT / ".claudeignore"
    if not p.exists():
        return
    content = p.read_text()
    required_patterns = [".cache/", ".env"]
    for pattern in required_patterns:
        if pattern not in content:
            _fail(f".claudeignore missing required pattern: '{pattern}'", issues)


# ─── Tier 3: .claude/settings.json ───


def test_settings_json_exists(issues: list[str]) -> None:
    if not (REPO_ROOT / ".claude" / "settings.json").exists():
        _fail(".claude/settings.json not found — no permissions or hooks configured", issues)


def test_settings_json_valid(issues: list[str]) -> None:
    p = REPO_ROOT / ".claude" / "settings.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        _fail(f".claude/settings.json invalid JSON: {e}", issues)
        return

    if "permissions" not in data:
        _fail(".claude/settings.json missing 'permissions' key", issues)
    else:
        perms = data["permissions"]
        if "allow" not in perms:
            _fail(".claude/settings.json missing 'permissions.allow'", issues)
        if "deny" not in perms:
            _fail(".claude/settings.json missing 'permissions.deny'", issues)

    # Hooks check
    if "hooks" not in data:
        _fail(".claude/settings.json missing 'hooks' — no automated gates", issues)


def test_settings_deny_dangerous(issues: list[str]) -> None:
    """Verify dangerous commands are denied."""
    p = REPO_ROOT / ".claude" / "settings.json"
    if not p.exists():
        return
    data = json.loads(p.read_text())
    deny = data.get("permissions", {}).get("deny", [])
    deny_str = " ".join(deny)
    dangerous = ["rm -rf /", "git push --force", "git reset --hard"]
    for cmd in dangerous:
        if cmd not in deny_str:
            _fail(f"Dangerous command not denied: '{cmd}'", issues)


# ─── Tier 4: .claude/rules/ ───


def test_rules_directory_exists(issues: list[str]) -> None:
    d = REPO_ROOT / ".claude" / "rules"
    if not d.exists() or not d.is_dir():
        _fail(".claude/rules/ directory not found", issues)


def test_rules_have_globs_frontmatter(issues: list[str]) -> None:
    """Each rule file should have --- frontmatter with globs."""
    d = REPO_ROOT / ".claude" / "rules"
    if not d.exists():
        return
    for f in d.glob("*.md"):
        content = f.read_text()
        if not content.startswith("---"):
            # cross-repo.md may not have globs (applies globally)
            if f.name not in ("cross-repo.md",):
                _fail(f".claude/rules/{f.name} missing --- frontmatter with globs", issues)
        elif "globs:" not in content.split("---")[1] and "globs:" not in content.split("---")[1]:
            if f.name not in ("cross-repo.md",):
                _fail(f".claude/rules/{f.name} missing 'globs:' in frontmatter", issues)


def test_rules_not_empty(issues: list[str]) -> None:
    d = REPO_ROOT / ".claude" / "rules"
    if not d.exists():
        return
    for f in d.glob("*.md"):
        if len(f.read_text().strip()) < 20:
            _fail(f".claude/rules/{f.name} is empty or near-empty", issues)


# ─── Tier 5: .claude/skills/ ───


def test_skills_directory_exists(issues: list[str]) -> None:
    d = REPO_ROOT / ".claude" / "skills"
    if not d.exists() or not d.is_dir():
        _fail(".claude/skills/ directory not found", issues)


def test_skills_have_frontmatter(issues: list[str]) -> None:
    """Each skill should have name, description, user_invocable."""
    d = REPO_ROOT / ".claude" / "skills"
    if not d.exists():
        return
    for f in d.glob("*.md"):
        content = f.read_text()
        if "---" not in content:
            _fail(f".claude/skills/{f.name} missing frontmatter", issues)
            continue
        frontmatter = content.split("---")[1] if len(content.split("---")) > 1 else ""
        if "name:" not in frontmatter:
            _fail(f".claude/skills/{f.name} missing 'name:' in frontmatter", issues)
        if "description:" not in frontmatter:
            _fail(f".claude/skills/{f.name} missing 'description:' in frontmatter", issues)


# ─── Tier 6: .claude/agents/ ───


def test_agents_directory_exists(issues: list[str]) -> None:
    d = REPO_ROOT / ".claude" / "agents"
    if not d.exists() or not d.is_dir():
        _fail(".claude/agents/ directory not found", issues)


def test_agents_have_frontmatter(issues: list[str]) -> None:
    """Each agent should have name, description, tools."""
    d = REPO_ROOT / ".claude" / "agents"
    if not d.exists():
        return
    for f in d.glob("*.md"):
        content = f.read_text()
        if "---" not in content:
            _fail(f".claude/agents/{f.name} missing frontmatter", issues)
            continue
        frontmatter = content.split("---")[1] if len(content.split("---")) > 1 else ""
        if "name:" not in frontmatter:
            _fail(f".claude/agents/{f.name} missing 'name:' in frontmatter", issues)
        if "description:" not in frontmatter:
            _fail(f".claude/agents/{f.name} missing 'description:' in frontmatter", issues)


# ─── Tier 7: Codex Skills Parity ───


def test_codex_skills_directory(issues: list[str]) -> None:
    d = REPO_ROOT / ".agents" / "skills"
    if not d.exists():
        _fail(".agents/skills/ directory not found — Codex has no skills", issues)


def test_codex_skills_have_skill_md(issues: list[str]) -> None:
    d = REPO_ROOT / ".agents" / "skills"
    if not d.exists():
        return
    for skill_dir in d.iterdir():
        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                _fail(f".agents/skills/{skill_dir.name}/SKILL.md missing", issues)
            else:
                content = skill_md.read_text()
                if "name:" not in content or "description:" not in content:
                    _fail(f".agents/skills/{skill_dir.name}/SKILL.md missing name/description", issues)


def test_claude_codex_skills_parity(issues: list[str]) -> None:
    """Claude skills should have Codex equivalents."""
    claude_skills = REPO_ROOT / ".claude" / "skills"
    codex_skills = REPO_ROOT / ".agents" / "skills"
    if not claude_skills.exists() or not codex_skills.exists():
        return

    claude_names = {f.stem for f in claude_skills.glob("*.md")}
    codex_names = {f.name for f in codex_skills.iterdir() if f.is_dir()}

    missing = claude_names - codex_names
    if missing:
        _fail(f"Claude skills without Codex equivalent: {', '.join(sorted(missing))}", issues)


# ─── Tier 8: Provider Configs ───


def test_codex_config(issues: list[str]) -> None:
    p = REPO_ROOT / ".codex" / "config.toml"
    if not p.exists():
        _fail(".codex/config.toml not found — Codex provider not configured", issues)


def test_gemini_config(issues: list[str]) -> None:
    p = REPO_ROOT / ".gemini" / "settings.json"
    if not p.exists():
        _fail(".gemini/settings.json not found — Gemini provider not configured", issues)
    else:
        try:
            json.loads(p.read_text())
        except json.JSONDecodeError:
            _fail(".gemini/settings.json invalid JSON", issues)


# ─── Runner ───


def main():
    issues: list[str] = []

    tests = [
        # Tier 1: CLAUDE.md + AGENTS.md
        test_claude_md_exists,
        test_claude_md_imports_agents,
        test_claude_md_size_limit,
        test_agents_md_exists,
        test_agents_md_has_required_sections,
        # Tier 2: .claudeignore
        test_claudeignore_exists,
        test_claudeignore_excludes_sensitive,
        # Tier 3: .claude/settings.json
        test_settings_json_exists,
        test_settings_json_valid,
        test_settings_deny_dangerous,
        # Tier 4: .claude/rules/
        test_rules_directory_exists,
        test_rules_have_globs_frontmatter,
        test_rules_not_empty,
        # Tier 5: .claude/skills/
        test_skills_directory_exists,
        test_skills_have_frontmatter,
        # Tier 6: .claude/agents/
        test_agents_directory_exists,
        test_agents_have_frontmatter,
        # Tier 7: Codex parity
        test_codex_skills_directory,
        test_codex_skills_have_skill_md,
        test_claude_codex_skills_parity,
        # Tier 8: Provider configs
        test_codex_config,
        test_gemini_config,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        before = len(issues)
        test_fn(issues)
        if len(issues) == before:
            passed += 1
        else:
            failed += 1

    result = {
        "status": "pass" if not issues else "fail",
        "tests_run": len(tests),
        "passed": passed,
        "failed": failed,
        "issues": issues,
    }

    print(json.dumps(result, indent=2))
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
