from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"north_star_profile_order_compare_contract_test failed: {message}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_registry(ws: Path) -> str:
    subject_id = "ai_ile_yazilim_gelistirirken_baglam_yonetimi"
    registry_obj = {
        "version": "v1",
        "generated_at": "2026-03-02T00:00:00Z",
        "source": "contract_test",
        "subjects": [
            {
                "subject_id": subject_id,
                "subject_title_tr": "AI ile yazilim gelistirirken baglam yonetimi",
                "subject_title_en": "Context management while developing software with AI",
                "themes": [
                    {
                        "theme_id": "context_core",
                        "title_tr": "Baglam Cekirdegi",
                        "title_en": "Context Core",
                        "subthemes": [
                            {"subtheme_id": "memory", "title_tr": "Memory", "title_en": "Memory"},
                            {"subtheme_id": "session", "title_tr": "Session", "title_en": "Session"},
                        ],
                    },
                    {
                        "theme_id": "execution",
                        "title_tr": "Yurutme",
                        "title_en": "Execution",
                        "subthemes": [
                            {"subtheme_id": "router", "title_tr": "Router", "title_en": "Router"},
                            {"subtheme_id": "evidence", "title_tr": "Evidence", "title_en": "Evidence"},
                        ],
                    },
                ],
            }
        ],
    }
    path = ws / ".cache" / "index" / "mechanisms.registry.v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return subject_id


def _seed_policy(ws: Path) -> None:
    policy_obj = {
        "version": "v1",
        "synthesis": {
            "mode": "holistic_module_pack.v1",
            "stopwords": ["ve", "ile", "icin", "the", "and", "module", "theme", "subtheme"],
            "module_blueprints": [
                {
                    "module_id": "context_core",
                    "title_tr": "Baglam Core",
                    "title_en": "Context Core",
                    "module_kind": "context",
                    "keywords": ["context", "memory", "session", "baglam"],
                    "flow": {
                        "inputs": ["request_text", "history"],
                        "process": ["context_extract", "memory_link"],
                        "outputs": ["context_pack"],
                    },
                },
                {
                    "module_id": "execution_core",
                    "title_tr": "Yurutme Core",
                    "title_en": "Execution Core",
                    "module_kind": "execution",
                    "keywords": ["router", "dispatch", "evidence", "execution"],
                    "flow": {
                        "inputs": ["context_pack", "policy_state"],
                        "process": ["route", "execute"],
                        "outputs": ["execution_trace"],
                    },
                },
                {
                    "module_id": "general_delivery_backlog",
                    "title_tr": "Genel Teslimat",
                    "title_en": "General Delivery",
                    "module_kind": "general_delivery",
                    "keywords": [],
                    "flow": {
                        "inputs": ["subject_catalog"],
                        "process": ["backlog_prepare"],
                        "outputs": ["delivery_backlog"],
                    },
                },
            ],
        },
        "quality_gate": {
            "enforce": True,
            "max_module_count": 6,
            "min_coverage_quality": 0.70,
            "require_full_coverage": True,
            "preferred_profile_order": ["C", "B", "A"],
            "scoring_weights": {
                "pair_weight": 0.55,
                "theme_weight": 0.35,
                "completeness_weight": 0.10,
            },
        },
        "limits": {
            "max_steps": 16,
            "max_plan_bytes": 131072,
            "plan_bytes_over_limit_action": "warn",
        },
    }
    policy_path = ws / "policies" / "policy_north_star_subject_plan.v1.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _parse_last_json_line(raw_stdout: str) -> dict:
    lines = [line.strip() for line in str(raw_stdout or "").splitlines() if line.strip()]
    _must(bool(lines), "command stdout is empty")
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise SystemExit("north_star_profile_order_compare_contract_test failed: no JSON payload in stdout")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    ws = repo_root / ".cache" / "ws_north_star_profile_order_compare_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    subject_id = _seed_registry(ws)
    _seed_policy(ws)

    cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "north-star-profile-order-compare",
        "--workspace-root",
        str(ws),
        "--subject-id",
        subject_id,
        "--orders",
        "BCA;ACB;CAB",
        "--mode",
        "plan_first",
        "--out",
        "latest",
        "--report-path",
        ".cache/reports/north_star_profile_order_ab_compare.v1.json",
    ]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    _must(proc.returncode == 0, f"command failed rc={proc.returncode} stderr={proc.stderr.strip()}")
    payload = _parse_last_json_line(proc.stdout)

    _must(str(payload.get("status") or "") in {"OK", "WARN"}, "payload status must be OK/WARN")
    _must(str(payload.get("subject_id") or "") == subject_id, "subject_id mismatch")
    _must(str(payload.get("orders_spec") or "") == "BCA;ACB;CAB", "orders_spec mismatch")

    scenarios = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else []
    _must(len(scenarios) == 3, "scenario count must be 3")

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    _must(int(summary.get("total_scenarios") or 0) == 3, "summary total_scenarios must be 3")
    _must(bool(summary.get("all_runs_ok")), "all_runs_ok must be true")
    _must(bool(summary.get("all_comparisons_ok")), "all_comparisons_ok must be true")

    report_path_raw = str(payload.get("report_path") or "").strip()
    _must(bool(report_path_raw), "report_path missing")
    report_path = Path(report_path_raw)
    _must(report_path.exists(), "report_path does not exist")
    report_obj = _load_json(report_path)
    _must(str(report_obj.get("subject_id") or "") == subject_id, "report subject_id mismatch")

    override_path = ws / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json"
    _must(not override_path.exists(), "temporary preferred_profile_order override must be restored")

    print(
        json.dumps(
            {
                "status": "OK",
                "subject_id": subject_id,
                "scenarios": len(scenarios),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
