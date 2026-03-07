from __future__ import annotations

import json

from src.orchestrator.failure_preview import failure_preview_from_exception


class DetailedError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("detailed failure")
        self.details = {
            "cmd": "python build.py",
            "return_code": 7,
            "stdout_tail": "stdout line 1\nstdout line 2",
            "stderr_tail": "stderr line 1\nstderr line 2",
        }


class ProcessLikeError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("process failure")
        self.cmd = ["python", "serve.py"]
        self.returncode = 3
        self.stdout = "ok\nwarn\n"
        self.stderr = "traceback\nboom\n"


class JsonEncodedError(RuntimeError):
    def __str__(self) -> str:
        return json.dumps(
            {
                "cmd": ["npm", "run", "build"],
                "return_code": "2",
                "stdout_tail": "vite start\nvite fail",
                "stderr_tail": "error one\nerror two",
            }
        )


def main() -> None:
    detailed = failure_preview_from_exception(DetailedError())
    if detailed != {
        "failed_cmd": "python build.py",
        "failed_return_code": 7,
        "failed_stdout_preview": "stdout line 1\nstdout line 2",
        "failed_stderr_preview": "stderr line 1\nstderr line 2",
    }:
        raise SystemExit("failure_preview_contract_test failed: details extraction mismatch")

    process_like = failure_preview_from_exception(ProcessLikeError())
    if process_like != {
        "failed_cmd": "python serve.py",
        "failed_return_code": 3,
        "failed_stdout_preview": "ok\nwarn",
        "failed_stderr_preview": "traceback\nboom",
    }:
        raise SystemExit("failure_preview_contract_test failed: process-like extraction mismatch")

    json_encoded = failure_preview_from_exception(JsonEncodedError("ignored"))
    if json_encoded != {
        "failed_cmd": "npm run build",
        "failed_return_code": 2,
        "failed_stdout_preview": "vite start\nvite fail",
        "failed_stderr_preview": "error one\nerror two",
    }:
        raise SystemExit("failure_preview_contract_test failed: JSON string extraction mismatch")

    print("failure_preview_contract_test: PASS")


if __name__ == "__main__":
    main()
