#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_STANDARD_SOURCE_KEYS = {
    "technical_baseline_aistd",
    "layer_boundary_policy",
    "llm_live_policy",
    "llm_provider_guardrails_policy",
    "kernel_api_guardrails_policy",
    "ui_design_system_policy",
    "security_policy",
    "secrets_policy",
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out", default=".cache/reports/technical_baseline_checklist.v1.json")
    return parser.parse_args(argv)


def _parse_major(version_text: str) -> int:
    m = re.search(r"(\d+)", str(version_text or ""))
    return int(m.group(1)) if m else 0


def _status_counts(checks: list[dict[str, Any]]) -> tuple[int, int, int]:
    ok = 0
    warn = 0
    fail = 0
    for item in checks:
        status = str(item.get("status") or "")
        if status == "OK":
            ok += 1
        elif status == "WARN":
            warn += 1
        else:
            fail += 1
    return ok, warn, fail


def _section_status(checks: list[dict[str, Any]]) -> str:
    _, warn, fail = _status_counts(checks)
    if fail > 0:
        return "FAIL"
    if warn > 0:
        return "WARN"
    return "OK"


def _check(id_: str, status: str, expected: str, actual: str, evidence: list[str]) -> dict[str, Any]:
    return {
        "id": id_,
        "status": status,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _run_backend_layout_check(repo_root: Path) -> tuple[str, str]:
    script = repo_root / "scripts" / "check_backend_service_layout.py"
    if not script.exists():
        return "WARN", "layout_script_missing"
    proc = subprocess.run(
        ["python3", str(script)],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        return "OK", "layout_check_ok"
    return "FAIL", "layout_check_fail"


def _run_process(cmd: list[str], cwd: Path) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=180,
        )
    except FileNotFoundError:
        return "WARN", "binary_missing"
    except subprocess.TimeoutExpired:
        return "FAIL", "timeout"
    if proc.returncode == 0:
        return "OK", "exit=0"
    return "FAIL", f"exit={proc.returncode}"


def _iter_code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if any(part in {"node_modules", "dist", "build", "coverage"} for part in path.parts):
            continue
        files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).expanduser().resolve()
    out_path = Path(str(args.out)).expanduser()
    out_path = (repo_root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = repo_root / "standards.lock"
    if not lock_path.exists():
        payload = {"status": "FAIL", "error_code": "STANDARDS_LOCK_MISSING", "repo_root": str(repo_root)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    lock = _load_json(lock_path)
    standard_sources = lock.get("standard_sources") if isinstance(lock.get("standard_sources"), dict) else {}
    source_keys = {str(k) for k in standard_sources.keys()}
    source_missing = sorted(EXPECTED_STANDARD_SOURCE_KEYS - source_keys)
    source_extra = sorted(source_keys - EXPECTED_STANDARD_SOURCE_KEYS)

    baseline_rel = str(standard_sources.get("technical_baseline_aistd") or "").strip()
    baseline_path = (repo_root / baseline_rel).resolve() if baseline_rel else Path("")
    if not baseline_rel or not baseline_path.exists():
        payload = {
            "status": "FAIL",
            "error_code": "TECHNICAL_BASELINE_MISSING",
            "baseline_path": baseline_rel,
            "repo_root": str(repo_root),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    baseline = _load_json(baseline_path)
    profile_id = str(baseline.get("profile_id") or "")
    baseline_obj = baseline.get("baseline") if isinstance(baseline.get("baseline"), dict) else {}
    backend_cfg = baseline_obj.get("backend") if isinstance(baseline_obj.get("backend"), dict) else {}
    frontend_cfg = baseline_obj.get("frontend") if isinstance(baseline_obj.get("frontend"), dict) else {}
    database_cfg = baseline_obj.get("database") if isinstance(baseline_obj.get("database"), dict) else {}
    api_cfg = baseline_obj.get("api") if isinstance(baseline_obj.get("api"), dict) else {}
    ci_cfg = baseline.get("ci_contract") if isinstance(baseline.get("ci_contract"), dict) else {}
    frontend_design_contract = (
        frontend_cfg.get("design_contract") if isinstance(frontend_cfg.get("design_contract"), dict) else {}
    )
    frontend_page_composition = (
        frontend_cfg.get("page_composition") if isinstance(frontend_cfg.get("page_composition"), dict) else {}
    )
    frontend_parametric_data = (
        frontend_cfg.get("parametric_data") if isinstance(frontend_cfg.get("parametric_data"), dict) else {}
    )
    ui_policy_rel = str(standard_sources.get("ui_design_system_policy") or "").strip()
    ui_policy_path = (repo_root / ui_policy_rel).resolve() if ui_policy_rel else Path("")
    ui_policy: dict[str, Any] = _load_json(ui_policy_path) if ui_policy_rel and ui_policy_path.exists() else {}

    source_checks: list[dict[str, Any]] = []
    source_checks.append(
        _check(
            "source.contract.keys",
            "OK" if not source_missing and not source_extra else "FAIL",
            ",".join(sorted(EXPECTED_STANDARD_SOURCE_KEYS)),
            f"missing={source_missing} extra={source_extra}",
            ["standards.lock:standard_sources"],
        )
    )

    policy_checks: list[dict[str, Any]] = []
    for key in sorted(EXPECTED_STANDARD_SOURCE_KEYS - {"technical_baseline_aistd"}):
        rel = str(standard_sources.get(key) or "").strip()
        path = (repo_root / rel).resolve() if rel else Path("")
        ok = bool(rel) and path.exists()
        policy_checks.append(
            _check(
                f"policy.{key}.exists",
                "OK" if ok else "FAIL",
                "file_exists",
                rel if rel else "missing_path",
                [rel] if rel else [],
            )
        )

    backend_checks: list[dict[str, Any]] = []
    backend_dir = repo_root / "backend"
    backend_checks.append(
        _check(
            "backend.dir.exists",
            "OK" if backend_dir.exists() else "FAIL",
            "backend_directory_present",
            "present" if backend_dir.exists() else "missing",
            ["backend"],
        )
    )

    service_poms = sorted((backend_dir.glob("*/pom.xml"))) if backend_dir.exists() else []
    java_expected = int(backend_cfg.get("java_major") or 0)
    java_values: list[int] = []
    spring_values: list[str] = []
    for pom in service_poms:
        text = _read_text(pom)
        m_java = re.search(r"<java\.version>\s*(\d+)\s*</java\.version>", text)
        if m_java:
            java_values.append(int(m_java.group(1)))
        m_spring = re.search(
            r"<artifactId>\s*spring-boot-starter-parent\s*</artifactId>\s*<version>\s*([0-9]+\.[0-9]+\.[0-9]+)\s*</version>",
            text,
            flags=re.DOTALL,
        )
        if m_spring:
            spring_values.append(m_spring.group(1))

    java_ok = bool(java_values) and all(v >= java_expected for v in java_values)
    backend_checks.append(
        _check(
            "backend.java.major",
            "OK" if java_ok else "FAIL",
            f">={java_expected}",
            ",".join(str(v) for v in sorted(set(java_values))) if java_values else "not_detected",
            [p.relative_to(repo_root).as_posix() for p in service_poms[:10]],
        )
    )

    framework_line = str(backend_cfg.get("framework_line") or "").replace(".x", "")
    spring_ok = bool(spring_values) and all(v.startswith(framework_line) for v in spring_values)
    backend_checks.append(
        _check(
            "backend.framework.line",
            "OK" if spring_ok else "FAIL",
            f"spring-boot {framework_line}.x",
            ",".join(sorted(set(spring_values))) if spring_values else "not_detected",
            [p.relative_to(repo_root).as_posix() for p in service_poms[:10]],
        )
    )

    has_gateway = (backend_dir / "api-gateway").exists()
    has_discovery = (backend_dir / "discovery-server").exists()
    backend_checks.append(
        _check(
            "backend.topology.microservice",
            "OK" if has_gateway and has_discovery else "FAIL",
            "api-gateway+discovery-server",
            f"api-gateway={has_gateway} discovery-server={has_discovery}",
            ["backend/api-gateway", "backend/discovery-server"],
        )
    )

    layout_status, layout_actual = _run_backend_layout_check(repo_root)
    backend_checks.append(
        _check(
            "backend.layout.guard",
            layout_status,
            "check_backend_service_layout=OK",
            layout_actual,
            ["scripts/check_backend_service_layout.py"],
        )
    )

    gateway_props = backend_dir / "api-gateway" / "src" / "main" / "resources" / "application.properties"
    gateway_text = _read_text(gateway_props)
    comm_ok = "uri=lb://" in gateway_text and "/api/v1/" in gateway_text
    backend_checks.append(
        _check(
            "backend.service.communication",
            "OK" if comm_ok else "FAIL",
            "gateway lb:// + /api/v1 routes",
            "matched" if comm_ok else "not_matched",
            [gateway_props.relative_to(repo_root).as_posix()] if gateway_props.exists() else [],
        )
    )

    frontend_checks: list[dict[str, Any]] = []
    web_package_path = repo_root / "web" / "package.json"
    web_obj: dict[str, Any] = {}
    if web_package_path.exists():
        web_obj = _load_json(web_package_path)
    frontend_checks.append(
        _check(
            "frontend.package.exists",
            "OK" if web_package_path.exists() else "FAIL",
            "web/package.json",
            "present" if web_package_path.exists() else "missing",
            ["web/package.json"],
        )
    )
    node_expected = int(frontend_cfg.get("node_major") or 0)
    node_engine = ""
    if isinstance(web_obj.get("engines"), dict):
        node_engine = str(web_obj["engines"].get("node") or "")
    node_ok = _parse_major(node_engine) == node_expected
    frontend_checks.append(
        _check(
            "frontend.node.major",
            "OK" if node_ok else "FAIL",
            str(node_expected),
            node_engine or "not_detected",
            ["web/package.json"],
        )
    )

    react_expected = _parse_major(str(frontend_cfg.get("framework_line") or ""))
    react_version = ""
    if isinstance(web_obj.get("dependencies"), dict):
        react_version = str(web_obj["dependencies"].get("react") or "")
    react_ok = _parse_major(react_version) == react_expected
    frontend_checks.append(
        _check(
            "frontend.react.major",
            "OK" if react_ok else "FAIL",
            str(react_expected),
            react_version or "not_detected",
            ["web/package.json"],
        )
    )

    mfe_configs = sorted((repo_root / "web" / "apps").glob("*/webpack*.js"))
    mfe_hits = 0
    for cfg in mfe_configs:
        if "ModuleFederationPlugin" in _read_text(cfg):
            mfe_hits += 1
    frontend_checks.append(
        _check(
            "frontend.mfe.module_federation",
            "OK" if mfe_hits > 0 else "FAIL",
            "ModuleFederationPlugin present",
            f"hits={mfe_hits}",
            [p.relative_to(repo_root).as_posix() for p in mfe_configs[:10]],
        )
    )

    ui_kit_exists = (repo_root / "web" / "packages" / "ui-kit" / "package.json").exists()
    tokens_exists = (repo_root / "web" / "design-tokens").exists()
    frontend_checks.append(
        _check(
            "frontend.style.system",
            "OK" if ui_kit_exists and tokens_exists else "WARN",
            "ui-kit + design-tokens",
            f"ui-kit={ui_kit_exists} design-tokens={tokens_exists}",
            ["web/packages/ui-kit/package.json", "web/design-tokens"],
        )
    )

    ui_policy_single = ui_policy.get("single_ui_library") if isinstance(ui_policy.get("single_ui_library"), dict) else {}
    ui_pkg_rel = str(
        frontend_design_contract.get("ui_package_manifest_path")
        or ui_policy_single.get("package_manifest_path")
        or "web/packages/ui-kit/package.json"
    )
    ui_pkg_path = (repo_root / ui_pkg_rel).resolve()
    ui_pkg_obj: dict[str, Any] = _load_json(ui_pkg_path) if ui_pkg_path.exists() else {}
    expected_ui_pkg = str(
        frontend_design_contract.get("single_ui_library")
        or ui_policy_single.get("package_name")
        or "mfe-ui-kit"
    )
    actual_ui_pkg = str(ui_pkg_obj.get("name") or "")
    frontend_checks.append(
        _check(
            "frontend.design.single_ui_library",
            "OK" if ui_pkg_path.exists() and actual_ui_pkg == expected_ui_pkg else "FAIL",
            expected_ui_pkg,
            actual_ui_pkg if actual_ui_pkg else "not_detected",
            [ui_pkg_rel],
        )
    )

    catalog_rel = str(
        frontend_design_contract.get("design_catalog_index_path")
        or ui_policy_single.get("design_catalog_index_path")
        or "web/apps/mfe-shell/src/pages/admin/design-lab.index.json"
    )
    catalog_path = (repo_root / catalog_rel).resolve()
    catalog_obj: dict[str, Any] = _load_json(catalog_path) if catalog_path.exists() else {}
    catalog_items = catalog_obj.get("items") if isinstance(catalog_obj.get("items"), list) else []
    frontend_checks.append(
        _check(
            "frontend.design.catalog.index",
            "OK" if catalog_path.exists() and len(catalog_items) > 0 else "FAIL",
            "design-lab index exists and items>0",
            f"exists={catalog_path.exists()} items={len(catalog_items)}",
            [catalog_rel],
        )
    )

    ui_policy_tokens = ui_policy.get("design_tokens") if isinstance(ui_policy.get("design_tokens"), dict) else {}
    token_source_rel = str(
        frontend_design_contract.get("token_source_path")
        or ui_policy_tokens.get("source_path")
        or "web/design-tokens/figma.tokens.json"
    )
    token_source_path = (repo_root / token_source_rel).resolve()
    token_generated_paths = (
        frontend_design_contract.get("token_generated_paths")
        if isinstance(frontend_design_contract.get("token_generated_paths"), list)
        else ui_policy_tokens.get("generated_paths")
        if isinstance(ui_policy_tokens.get("generated_paths"), list)
        else [
            "web/apps/mfe-shell/src/styles/theme.css",
            "web/design-tokens/generated/theme-contract.json",
        ]
    )
    generated_rel_paths = [str(item) for item in token_generated_paths if isinstance(item, str) and str(item).strip()]
    generated_exists = []
    for rel in generated_rel_paths:
        generated_exists.append((repo_root / rel).exists())
    frontend_checks.append(
        _check(
            "frontend.design.tokens.chain",
            "OK" if token_source_path.exists() and generated_rel_paths and all(generated_exists) else "FAIL",
            "token source + generated artifacts exist",
            f"source={token_source_path.exists()} generated_ok={all(generated_exists) if generated_rel_paths else False}",
            [token_source_rel] + generated_rel_paths,
        )
    )

    token_check_script = repo_root / "web" / "scripts" / "theme" / "generate-theme-css.mjs"
    if token_check_script.exists():
        token_check_status, token_check_actual = _run_process(
            ["node", str(token_check_script), "--check"],
            cwd=repo_root,
        )
    else:
        token_check_status, token_check_actual = ("WARN", "tokens_check_script_missing")
    frontend_checks.append(
        _check(
            "frontend.design.tokens.drift_guard",
            token_check_status,
            "node web/scripts/theme/generate-theme-css.mjs --check => exit=0",
            token_check_actual,
            ["web/scripts/theme/generate-theme-css.mjs"],
        )
    )

    no_antd_script = repo_root / "web" / "scripts" / "check-no-antd.mjs"
    if no_antd_script.exists():
        no_antd_status, no_antd_actual = _run_process(
            ["node", str(no_antd_script)],
            cwd=repo_root,
        )
    else:
        no_antd_status, no_antd_actual = ("FAIL", "check-no-antd.mjs_missing")
    frontend_checks.append(
        _check(
            "frontend.design.forbidden_imports_guard",
            no_antd_status,
            "forbidden imports blocked (antd, @ant-design/icons)",
            no_antd_actual,
            ["web/scripts/check-no-antd.mjs"],
        )
    )

    extra_frontend_guards = [
        ("frontend.design.theme_contract_consistency_guard", "scripts/check_theme_contract_consistency.py"),
        ("frontend.design.theme_override_allowlist_guard", "scripts/check_theme_override_allowlist.py"),
        ("frontend.design.no_hardcoded_theme_styles_guard", "scripts/check_no_hardcoded_theme_styles.py"),
    ]
    for check_id, rel in extra_frontend_guards:
        script_path = repo_root / rel
        if script_path.exists():
            guard_status, guard_actual = _run_process(["python3", str(script_path)], cwd=repo_root)
        else:
            guard_status, guard_actual = ("WARN", "script_missing")
        guard_status_effective = "OK" if guard_status == "OK" else "WARN"
        frontend_checks.append(
            _check(
                check_id,
                guard_status_effective,
                f"{rel} => exit=0",
                guard_actual,
                [rel],
            )
        )

    required_layout_exports = (
        frontend_page_composition.get("required_layout_exports")
        if isinstance(frontend_page_composition.get("required_layout_exports"), list)
        else ["PageLayout", "DetailDrawer", "FormDrawer"]
    )
    ui_index_path = repo_root / "web" / "packages" / "ui-kit" / "src" / "index.ts"
    ui_index_text = _read_text(ui_index_path)
    missing_layout_exports = [name for name in required_layout_exports if str(name) and str(name) not in ui_index_text]
    frontend_checks.append(
        _check(
            "frontend.page.modular_layout_exports",
            "OK" if ui_index_path.exists() and not missing_layout_exports else "FAIL",
            "ui-kit index exports required page layout modules",
            f"missing={missing_layout_exports}",
            ["web/packages/ui-kit/src/index.ts"],
        )
    )

    ui_import_prefix = str(frontend_page_composition.get("ui_import_prefix") or "from 'mfe-ui-kit'")
    pages_root_rel = str(frontend_page_composition.get("pages_root") or "web/apps")
    pages_root = (repo_root / pages_root_rel).resolve()
    ui_import_hits = 0
    ui_import_files: list[str] = []
    for path in _iter_code_files(pages_root):
        text = _read_text(path)
        if ui_import_prefix in text or 'from "mfe-ui-kit"' in text:
            ui_import_hits += 1
            if len(ui_import_files) < 10:
                ui_import_files.append(path.relative_to(repo_root).as_posix())
    frontend_checks.append(
        _check(
            "frontend.page.modular_ui_import_usage",
            "OK" if ui_import_hits > 0 else "FAIL",
            "pages import from mfe-ui-kit",
            f"hits={ui_import_hits}",
            ui_import_files if ui_import_files else [pages_root_rel],
        )
    )

    parametric_paths = [
        str(frontend_parametric_data.get("query_builder_path") or ""),
        str(frontend_parametric_data.get("theme_contract_runtime_path") or ""),
        str(frontend_parametric_data.get("theme_context_provider_path") or ""),
    ]
    parametric_paths = [rel for rel in parametric_paths if rel]
    parametric_missing = [rel for rel in parametric_paths if not (repo_root / rel).exists()]
    frontend_checks.append(
        _check(
            "frontend.parametric.paths",
            "OK" if parametric_paths and not parametric_missing else "FAIL",
            "parametric data contract files exist",
            f"missing={parametric_missing}",
            parametric_paths,
        )
    )

    query_builder_rel = str(frontend_parametric_data.get("query_builder_path") or "")
    query_builder_symbol = "buildEntityGridQueryParams"
    query_usage_hits = 0
    for path in _iter_code_files(repo_root / "web" / "apps"):
        if query_builder_symbol in _read_text(path):
            query_usage_hits += 1
    frontend_checks.append(
        _check(
            "frontend.parametric.query_builder_usage",
            "OK" if query_builder_rel and query_usage_hits > 0 else "FAIL",
            f"{query_builder_symbol} used in app layer",
            f"hits={query_usage_hits}",
            [query_builder_rel] if query_builder_rel else [],
        )
    )

    database_checks: list[dict[str, Any]] = []
    pom_paths = sorted((backend_dir.glob("*/pom.xml"))) if backend_dir.exists() else []
    flyway_hits = 0
    for pom in pom_paths:
        if "flyway-core" in _read_text(pom):
            flyway_hits += 1
    database_checks.append(
        _check(
            "database.migration.flyway",
            "OK" if flyway_hits > 0 else "FAIL",
            str(database_cfg.get("migration_tool") or "flyway"),
            f"flyway-core_hits={flyway_hits}",
            [p.relative_to(repo_root).as_posix() for p in pom_paths[:10]],
        )
    )

    migration_dirs = sorted((backend_dir.glob("*/src/main/resources/db/migration"))) if backend_dir.exists() else []
    database_checks.append(
        _check(
            "database.migration.paths",
            "OK" if migration_dirs else "FAIL",
            "*/src/main/resources/db/migration",
            f"count={len(migration_dirs)}",
            [p.relative_to(repo_root).as_posix() for p in migration_dirs[:10]],
        )
    )

    sql_style_script = repo_root / "scripts" / "check_data_sql_style.py"
    database_checks.append(
        _check(
            "database.sql.style_guard",
            "OK" if sql_style_script.exists() else "WARN",
            "scripts/check_data_sql_style.py",
            "present" if sql_style_script.exists() else "missing",
            ["scripts/check_data_sql_style.py"],
        )
    )

    database_checks.append(
        _check(
            "database.engine.policy",
            "OK" if str(database_cfg.get("engine") or "") == "postgresql" else "FAIL",
            "postgresql",
            str(database_cfg.get("engine") or ""),
            [baseline_path.relative_to(repo_root).as_posix()],
        )
    )

    api_checks: list[dict[str, Any]] = []
    prefix = str(api_cfg.get("version_prefix") or "")
    api_prefix_ok = bool(prefix) and prefix in gateway_text
    api_checks.append(
        _check(
            "api.version.prefix",
            "OK" if api_prefix_ok else "FAIL",
            prefix,
            "present" if api_prefix_ok else "not_found_in_gateway",
            [gateway_props.relative_to(repo_root).as_posix()] if gateway_props.exists() else [],
        )
    )

    api_doc_script = repo_root / "scripts" / "check_api_docs.py"
    api_checks.append(
        _check(
            "api.docs.guard",
            "OK" if api_doc_script.exists() else "WARN",
            "scripts/check_api_docs.py",
            "present" if api_doc_script.exists() else "missing",
            ["scripts/check_api_docs.py"],
        )
    )

    api_docs_dir = repo_root / "docs" / "03-delivery" / "api"
    api_doc_count = len(list(api_docs_dir.glob("*.api.md"))) if api_docs_dir.exists() else 0
    api_checks.append(
        _check(
            "api.docs.count",
            "OK" if api_doc_count > 0 else "WARN",
            ">=1 *.api.md",
            f"count={api_doc_count}",
            [api_docs_dir.relative_to(repo_root).as_posix()] if api_docs_dir.exists() else [],
        )
    )

    ci_checks: list[dict[str, Any]] = []
    lane_cfg_path = repo_root / "ci" / "module_delivery_lanes.v1.json"
    lane_obj: dict[str, Any] = {}
    if lane_cfg_path.exists():
        lane_obj = _load_json(lane_cfg_path)

    expected_sequence = [str(x) for x in (ci_cfg.get("delivery_sequence") or [])]
    actual_sequence = [str(x) for x in (lane_obj.get("execution_sequence") or [])] if lane_obj else []
    ci_checks.append(
        _check(
            "ci.delivery.sequence",
            "OK" if actual_sequence == expected_sequence else "FAIL",
            ",".join(expected_sequence),
            ",".join(actual_sequence),
            ["ci/module_delivery_lanes.v1.json"],
        )
    )

    expected_lanes = {str(x) for x in (ci_cfg.get("required_lanes") or [])}
    actual_lanes = set(lane_obj.get("lanes", {}).keys()) if isinstance(lane_obj.get("lanes"), dict) else set()
    missing_lanes = sorted(expected_lanes - actual_lanes)
    ci_checks.append(
        _check(
            "ci.required.lanes",
            "OK" if not missing_lanes else "FAIL",
            ",".join(sorted(expected_lanes)),
            f"missing={missing_lanes}",
            ["ci/module_delivery_lanes.v1.json"],
        )
    )

    merge_green = bool(lane_obj.get("merge_requires_all_green")) if lane_obj else False
    ci_checks.append(
        _check(
            "ci.merge.requires_all_green",
            "OK" if merge_green else "FAIL",
            "true",
            str(merge_green).lower(),
            ["ci/module_delivery_lanes.v1.json"],
        )
    )

    workflow_path = repo_root / ".github" / "workflows" / "module-delivery-lanes.yml"
    workflow_text = _read_text(workflow_path)
    gate_name = str(ci_cfg.get("gate_name") or "module-delivery-gate")
    ci_checks.append(
        _check(
            "ci.gate.present",
            "OK" if gate_name in workflow_text else "FAIL",
            gate_name,
            "present" if gate_name in workflow_text else "missing",
            [workflow_path.relative_to(repo_root).as_posix()] if workflow_path.exists() else [],
        )
    )

    sections = {
        "source_contract": {"checks": source_checks},
        "policies": {"checks": policy_checks},
        "backend": {"checks": backend_checks},
        "frontend": {"checks": frontend_checks},
        "database": {"checks": database_checks},
        "api": {"checks": api_checks},
        "ci": {"checks": ci_checks},
    }

    fail_ids: list[str] = []
    warn_ids: list[str] = []
    for section in sections.values():
        checks = section["checks"]
        section["status"] = _section_status(checks)
        for item in checks:
            if item["status"] == "FAIL":
                fail_ids.append(str(item["id"]))
            elif item["status"] == "WARN":
                warn_ids.append(str(item["id"]))

    overall_status = "FAIL" if fail_ids else ("WARN" if warn_ids else "OK")
    report = {
        "version": "v1",
        "kind": "technical-baseline-checklist-report",
        "generated_at": _now_iso_utc(),
        "repo_root": str(repo_root),
        "status": overall_status,
        "profile_id": profile_id,
        "baseline_path": baseline_path.relative_to(repo_root).as_posix(),
        "sections": sections,
        "summary": {
            "fail_count": len(fail_ids),
            "warn_count": len(warn_ids),
            "failed_check_ids": sorted(fail_ids),
            "warning_check_ids": sorted(warn_ids),
        },
    }

    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    payload = {
        "status": overall_status,
        "report_path": str(out_path),
        "fail_count": len(fail_ids),
        "warn_count": len(warn_ids),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if overall_status in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
