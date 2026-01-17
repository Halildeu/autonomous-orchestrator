from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema: dict, *, store: dict | None = None) -> Draft202012Validator:
    resolver = RefResolver.from_schema(schema, store=store or {})
    return Draft202012Validator(schema, resolver=resolver)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import start_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_jobs_index_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    start_github_ops_job(workspace_root=ws, kind="pr_list", dry_run=True)
    start_github_ops_job(workspace_root=ws, kind="merge", dry_run=True)

    index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    if not index_path.exists():
        raise SystemExit("github_ops_jobs_index_contract_test failed: jobs_index missing")

    schema_path = repo_root / "schemas" / "github-ops-jobs-index.schema.v1.json"
    job_schema_path = repo_root / "schemas" / "github-ops-job.schema.v1.json"
    trace_meta_schema_path = repo_root / "schemas" / "trace-meta.schema.v1.json"
    schema = _load_json(schema_path)
    job_schema = _load_json(job_schema_path)
    trace_meta_schema = _load_json(trace_meta_schema_path)
    store = {
        str(job_schema.get("$id") or ""): job_schema,
        str(trace_meta_schema.get("$id") or ""): trace_meta_schema,
    }
    _validator(schema, store=store).validate(_load_json(index_path))

    index_obj = _load_json(index_path)
    jobs = index_obj.get("jobs") if isinstance(index_obj, dict) else None
    if not isinstance(jobs, list):
        raise SystemExit("github_ops_jobs_index_contract_test failed: jobs list missing")

    sorted_jobs = sorted(
        [j for j in jobs if isinstance(j, dict)],
        key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")),
    )
    if sorted_jobs != jobs:
        raise SystemExit("github_ops_jobs_index_contract_test failed: job ordering not deterministic")

    print(json.dumps({"status": "OK", "jobs_count": len(jobs)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
