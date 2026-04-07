#!/usr/bin/env python3
"""
Toolchain/lockfile/library uyumu için "Version Gate" (L2.0) kontrol scripti.

Kullanım:
  python3 scripts/check_version_gates.py               # default: --mode local
  python3 scripts/check_version_gates.py --mode ci

Çıkış kodu:
  0: PASS veya WARN
  1: FAIL
  2: BLOCKED (lokalde çalıştırma için engel; CI'da BLOCKED üretilmez)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
BACKEND_DIR = ROOT / "backend"

EXPECTED_NODE_MAJOR_CI = 22  # Node 22 LTS pinned (.nvmrc=22.22.2, engines>=22.12)


@dataclass
class Finding:
    severity: str  # "FAIL" | "BLOCKED" | "WARN"
    title: str
    detail: str = ""


def run_capture(cmd: List[str], *, cwd: Path) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return proc.returncode, (proc.stdout or "").strip()
    except FileNotFoundError:
        return 127, ""


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def normalize_semver(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^[~^]", "", text)
    return text


def parse_node_major(version_text: str) -> Optional[int]:
    # node -v => v20.11.0
    m = re.search(r"\bv(\d+)\b", version_text.strip())
    return int(m.group(1)) if m else None


def parse_allowed_node_majors(engine_text: str) -> List[int]:
    return sorted({int(value) for value in re.findall(r"(\d+)(?:\s*\.x)?", engine_text or "")})


def parse_maven_wrapper_version(props_text: str) -> str:
    # distributionUrl=.../apache-maven-3.9.10-bin.zip
    m = re.search(r"apache-maven-([0-9]+(?:\.[0-9]+){1,3})", props_text)
    return m.group(1) if m else ""


def find_git_root(cwd: Path) -> Optional[Path]:
    if shutil.which("git") is None:
        return None
    code, out = run_capture(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if code != 0 or not out:
        return None
    return Path(out.strip())


def github_base_sha_from_event() -> str:
    event_path_str = (os.environ.get("GITHUB_EVENT_PATH") or "").strip()
    if not event_path_str:
        return ""
    event_path = Path(event_path_str).expanduser()
    if not event_path.is_file():
        return ""
    try:
        payload = json.loads(event_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return ""
    base = pr.get("base")
    if not isinstance(base, dict):
        return ""
    sha = base.get("sha")
    return str(sha or "").strip()


def get_changed_files(*, mode: str) -> Tuple[Optional[List[str]], List[str]]:
    """
    Changed files (ROOT-relative, posix) listesi.

    Notlar:
    - Lokal ortamda repo kökü git değilse, web/ içindeki git repo üzerinden denenecek.
    - CI'da pull_request için en güvenilir kaynak: GITHUB_EVENT_PATH içinden base sha.
    """
    notes: List[str] = []
    if shutil.which("git") is None:
        notes.append("git bulunamadı")
        return None, notes

    git_root = find_git_root(ROOT)
    if git_root is None:
        git_root = find_git_root(WEB_DIR)
    if git_root is None:
        notes.append("git worktree bulunamadı (diff unavailable)")
        return None, notes

    base_ref = ""
    base_sha = github_base_sha_from_event()
    if base_sha:
        base_ref = base_sha
    else:
        base_branch = (os.environ.get("GITHUB_BASE_REF") or "").strip()
        if base_branch:
            base_ref = f"origin/{base_branch}"

    if not base_ref:
        notes.append("base ref/sha bulunamadı (diff unavailable)")
        return None, notes

    # base_ref mevcut değilse checkout shallow olabilir; workflow tarafında fetch-depth=0 önerilir.
    code, out = run_capture(["git", "diff", "--name-only", "--no-renames", f"{base_ref}...HEAD"], cwd=git_root)
    if code != 0:
        notes.append(f"git diff çalışmadı (base={base_ref})")
        return None, notes

    files: List[str] = []
    for line in out.splitlines():
        p = line.strip()
        if not p:
            continue
        abs_path = (git_root / p).resolve()
        try:
            rel = abs_path.relative_to(ROOT.resolve())
        except Exception:
            # root dışıysa ignore
            continue
        files.append(rel.as_posix())

    return sorted(set(files)), notes


def iter_web_package_json_files() -> Iterable[Path]:
    patterns = [
        WEB_DIR / "package.json",
        *WEB_DIR.glob("apps/*/package.json"),
        *WEB_DIR.glob("packages/*/package.json"),
    ]
    seen: set[Path] = set()
    for p in patterns:
        if p.exists() and p not in seen:
            seen.add(p)
            yield p


def iter_source_files_for_ag_grid_scan() -> Iterable[Path]:
    if not WEB_DIR.exists():
        return

    skip_dirs = {"node_modules", ".git", "dist", "build", "coverage", "test-results", "storybook-static"}
    exts = {".ts", ".tsx", ".js", ".jsx"}

    for path in WEB_DIR.rglob("*"):
        if path.is_dir():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in exts:
            continue
        yield path


def detect_ag_grid_ssot_version(web_package_json: Dict[str, Any], package_name: str) -> str:
    overrides = web_package_json.get("overrides")
    if isinstance(overrides, dict) and isinstance(overrides.get(package_name), str):
        return normalize_semver(overrides.get(package_name) or "")

    deps = web_package_json.get("dependencies")
    if isinstance(deps, dict) and isinstance(deps.get(package_name), str):
        return normalize_semver(deps.get(package_name) or "")

    dev = web_package_json.get("devDependencies")
    if isinstance(dev, dict) and isinstance(dev.get(package_name), str):
        return normalize_semver(dev.get(package_name) or "")

    return ""


def read_package_dep_version(pkg: Dict[str, Any], name: str) -> str:
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = pkg.get(key)
        if isinstance(deps, dict) and isinstance(deps.get(name), str):
            return normalize_semver(deps.get(name) or "")
    return ""


def scan_banned_patterns_in_text(path: Path, patterns: List[str]) -> List[Tuple[str, int, str]]:
    hits: List[Tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return hits

    for idx, line in enumerate(text.splitlines(), start=1):
        for pat in patterns:
            if pat in line:
                hits.append((pat, idx, line.strip()))
    return hits


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_version_gates.py")
    parser.add_argument("--mode", choices=["ci", "local"], default="local")
    args = parser.parse_args(argv[1:])

    mode: str = args.mode
    findings: List[Finding] = []

    # -------------------------------------------------------------------------
    # Gate 0: Toolchain report (+ Node major enforce)
    # -------------------------------------------------------------------------
    node_code, node_out = run_capture(["node", "-v"], cwd=ROOT)
    npm_code, npm_out = run_capture(["npm", "-v"], cwd=ROOT)
    pnpm_code, pnpm_out = run_capture(["pnpm", "-v"], cwd=ROOT)

    node_major = parse_node_major(node_out) if node_code == 0 else None
    web_package = read_json(WEB_DIR / "package.json") or {}
    allowed_node_majors = parse_allowed_node_majors(
        str(((web_package.get("engines") or {}) if isinstance(web_package.get("engines"), dict) else {}).get("node") or "")
    )

    if node_major is None:
        if mode == "ci":
            findings.append(Finding("FAIL", "Node bulunamadı", "node -v çalışmadı"))
        else:
            findings.append(Finding("BLOCKED", "Node bulunamadı", "L2/L3 için Node gerekli"))
    else:
        if mode == "ci" and node_major != EXPECTED_NODE_MAJOR_CI:
            findings.append(
                Finding("FAIL", "Node major uyumsuz", f"Beklenen: {EXPECTED_NODE_MAJOR_CI}, Bulunan: {node_major} ({node_out})")
            )
        elif mode == "local" and allowed_node_majors and node_major not in allowed_node_majors:
            findings.append(
                Finding(
                    "WARN",
                    "Node major farklı",
                    f"Beklenen: {allowed_node_majors}, Bulunan: {node_major} ({node_out})",
                )
            )

    java_code, java_out = run_capture(["java", "-version"], cwd=ROOT)
    if java_code != 0:
        java_out = ""

    maven_wrapper_props = BACKEND_DIR / ".mvn/wrapper/maven-wrapper.properties"
    maven_wrapper_version = ""
    if maven_wrapper_props.exists():
        maven_wrapper_version = parse_maven_wrapper_version(maven_wrapper_props.read_text(encoding="utf-8", errors="ignore"))

    ts_version = ""
    dev_deps = web_package.get("devDependencies")
    if isinstance(dev_deps, dict) and isinstance(dev_deps.get("typescript"), str):
        ts_version = str(dev_deps.get("typescript") or "")

    # -------------------------------------------------------------------------
    # Gate 1: Lockfile drift
    # -------------------------------------------------------------------------
    web_package_lock = WEB_DIR / "package-lock.json"
    web_pnpm_lock = WEB_DIR / "pnpm-lock.yaml"
    is_pnpm_workspace = (WEB_DIR / "pnpm-workspace.yaml").exists()

    if is_pnpm_workspace:
        if not web_pnpm_lock.exists():
            if mode == "ci":
                findings.append(Finding("FAIL", "web/pnpm-lock.yaml yok", "pnpm workspace için lockfile zorunlu"))
            else:
                findings.append(Finding("BLOCKED", "web/pnpm-lock.yaml yok", "pnpm install --frozen-lockfile çalışmayacak"))
    elif not web_package_lock.exists():
        if mode == "ci":
            findings.append(Finding("FAIL", "web/package-lock.json yok", "npm workspace için lockfile zorunlu"))
        else:
            findings.append(Finding("BLOCKED", "web/package-lock.json yok", "npm ci çalışmayacak; lockfile eklenmeden L2/L3 koşma"))

    changed_files, diff_notes = get_changed_files(mode=mode)
    if changed_files is None:
        if mode == "ci":
            findings.append(Finding("WARN", "git diff unavailable", "; ".join(diff_notes) if diff_notes else "diff bulunamadı"))
    else:
        pnpm_changed = "web/pnpm-lock.yaml" in changed_files
        root_lock_changed = "web/package-lock.json" in changed_files
        nested_locks_changed = [
            p
            for p in changed_files
            if p.startswith("web/") and p.endswith("package-lock.json") and p != "web/package-lock.json"
        ]

        if web_pnpm_lock.exists() and not is_pnpm_workspace:
            findings.append(Finding("WARN", "web/pnpm-lock.yaml mevcut", "SSOT npm ise pnpm lock drift yaratabilir"))
            if mode == "ci" and pnpm_changed:
                findings.append(Finding("FAIL", "pnpm-lock.yaml PR diff içinde değişmiş", "SSOT npm: pnpm lock değişikliği yasak"))

        if mode == "ci" and not is_pnpm_workspace and nested_locks_changed and not root_lock_changed:
            examples = ", ".join(nested_locks_changed[:3])
            more = f" (+{len(nested_locks_changed)-3})" if len(nested_locks_changed) > 3 else ""
            findings.append(
                Finding(
                    "FAIL",
                    "Nested package-lock drift",
                    f"Nested lock değişmiş ama web/package-lock.json değişmemiş: {examples}{more}",
                )
            )

    # -------------------------------------------------------------------------
    # Gate 2: AG Grid guard
    # -------------------------------------------------------------------------
    ssot_ag_grid_community = detect_ag_grid_ssot_version(web_package, "ag-grid-community")
    ssot_ag_grid_enterprise = detect_ag_grid_ssot_version(web_package, "ag-grid-enterprise")

    # 2.1 banned imports/deps
    banned_substrings = ["@ag-grid-community/", "@ag-grid-enterprise/", "ag-grid-community/dist/"]
    banned_hits: List[str] = []

    # package.json dosyalarında dependency adı tespiti (daha hızlı ve deterministik)
    for pkg_path in iter_web_package_json_files():
        pkg = read_json(pkg_path) or {}
        raw = pkg_path.read_text(encoding="utf-8", errors="ignore")
        for pat in banned_substrings[:2]:
            if pat in raw:
                banned_hits.append(f"{pkg_path.relative_to(ROOT).as_posix()}: contains '{pat}'")

    # import taraması (ts/js)
    for src_path in iter_source_files_for_ag_grid_scan():
        hits = scan_banned_patterns_in_text(src_path, banned_substrings)
        if hits:
            pat, line_no, line = hits[0]
            banned_hits.append(f"{src_path.relative_to(ROOT).as_posix()}:{line_no}: {pat} :: {line}")

    if banned_hits:
        detail = "\n".join(f"- {h}" for h in banned_hits[:10])
        more = f"\n- ... (+{len(banned_hits)-10})" if len(banned_hits) > 10 else ""
        findings.append(Finding("FAIL", "AG Grid banned import/dependency", f"{detail}{more}"))

    # 2.2 version consistency
    version_rows: List[Tuple[str, str, str]] = []  # (file, pkg, version)
    for pkg_path in iter_web_package_json_files():
        pkg = read_json(pkg_path)
        if not pkg:
            continue
        for name in ("ag-grid-community", "ag-grid-enterprise"):
            v = read_package_dep_version(pkg, name)
            if v:
                version_rows.append((pkg_path.relative_to(ROOT).as_posix(), name, v))

    def mismatch_against_ssot(name: str, ssot: str) -> List[str]:
        if not ssot:
            return []
        mismatches = [f"{f}: {v}" for (f, pkg, v) in version_rows if pkg == name and normalize_semver(v) != ssot]
        return mismatches

    mismatches: List[str] = []
    mismatches.extend(mismatch_against_ssot("ag-grid-community", ssot_ag_grid_community))
    mismatches.extend(mismatch_against_ssot("ag-grid-enterprise", ssot_ag_grid_enterprise))

    if mismatches:
        detail = "\n".join(f"- {m}" for m in mismatches[:10])
        more = f"\n- ... (+{len(mismatches)-10})" if len(mismatches) > 10 else ""
        findings.append(Finding("FAIL", "AG Grid version mismatch", f"{detail}{more}"))

    # -------------------------------------------------------------------------
    # Report + exit code
    # -------------------------------------------------------------------------
    def worst_severity(items: List[Finding]) -> str:
        if any(f.severity == "FAIL" for f in items):
            return "FAIL"
        if any(f.severity == "BLOCKED" for f in items):
            return "BLOCKED"
        if any(f.severity == "WARN" for f in items):
            return "WARN"
        return "PASS"

    outcome = worst_severity(findings)

    print(f"[check_version_gates] outcome={outcome} mode={mode}")
    print("")
    print("## Toolchain (report)")
    print(f"- node: {node_out or 'N/A'}")
    print(f"- npm: {npm_out or 'N/A'}")
    print(f"- pnpm: {pnpm_out or 'N/A'}")
    print(f"- java: {java_out.splitlines()[0] if java_out else 'N/A'}")
    print(f"- maven-wrapper: {maven_wrapper_version or 'N/A'}")
    print(f"- typescript (web/package.json): {ts_version or 'N/A'}")
    print("- tsconfig SSOT: web/tsconfig.json (cypress tsconfig; target/lib SSOT değildir)")
    print("")

    if findings:
        print("## Findings")
        for f in findings:
            detail = f" — {f.detail}" if f.detail else ""
            print(f"- [{f.severity}] {f.title}{detail}")
    else:
        print("## Findings")
        print("- [PASS] Bulgu yok")

    if outcome == "FAIL":
        return 1
    if outcome == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
