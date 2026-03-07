# Observability Coverage Matrix (v1)

status=OK
entrypoints_total=6
required_entrypoints=5
trace_hook_present=5
evidence_signal_present=5
otel_bridge_present=3
ci_gate_present=6

| entrypoint | expectation | trace_meta | evidence | otel | ci_gate | status | path |
|---|---|---:|---:|---:|---:|---|---|
| runner_execute_finalize | required | true | true | true | true | OK | src/orchestrator/runner_stages/execute_finalize_stage.py |
| runner_quota_autonomy | required | true | true | true | true | OK | src/orchestrator/runner_stages/quota_autonomy_stage.py |
| runner_routing_workflow | required | true | true | true | true | OK | src/orchestrator/runner_stages/routing_workflow_stage.py |
| github_ops_runtime | required | true | true | false | true | OK | src/prj_github_ops/github_ops_runtime.py |
| cockpit_ops_server | required | true | true | false | true | OK | extensions/PRJ-UI-COCKPIT-LITE/server_utils_ops.py |
| ops_manage_cli | optional | false | false | false | true | OK | src/ops/manage.py |
