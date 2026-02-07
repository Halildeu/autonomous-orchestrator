from __future__ import annotations

from src.orchestrator.runner_cli_args import parse_args
from src.orchestrator.runner_execute import run_envelope
from src.orchestrator.runner_inputs import load_envelope
from src.orchestrator.runner_paths import resolve_out_dir, resolve_workspace
from src.orchestrator.runner_resume import handle_resume


def main() -> None:
    args = parse_args()
    workspace = resolve_workspace(args.workspace)
    out_dir = resolve_out_dir(workspace=workspace, out_arg=str(args.out))

    if args.resume:
        handle_resume(args=args, workspace=workspace, out_dir=out_dir)
        return

    envelope, envelope_path, replay_ctx = load_envelope(args=args, workspace=workspace)
    run_envelope(
        envelope=envelope,
        envelope_path=envelope_path,
        workspace=workspace,
        out_dir=out_dir,
        replay_ctx=replay_ctx,
    )


if __name__ == "__main__":
    main()
