from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.tools import fs_read, fs_write, github_pr_create, secrets_get
from src.tools.errors import PolicyViolation


def resolve_path_in_workspace(*, workspace: str, path: str) -> Path:
    ws = Path(workspace).resolve()
    if not path or not isinstance(path, str):
        raise PolicyViolation("INVALID_ARGS", "Missing or invalid path argument.")

    p = Path(path)
    resolved = p.resolve() if p.is_absolute() else (ws / p).resolve()
    try:
        resolved.relative_to(ws)
    except ValueError as e:
        raise PolicyViolation("PATH_TRAVERSAL", f"Path escapes workspace: {resolved}") from e
    return resolved


@dataclass(frozen=True)
class ToolGateway:
    max_bytes_in: int = 200_000
    max_bytes_out: int = 200_000
    tools: dict[str, Callable[..., dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        if self.tools is None:
            object.__setattr__(
                self,
                "tools",
                {
                    "fs_read": fs_read.run,
                    "fs_write": fs_write.run,
                    "secrets_get": secrets_get.run,
                    "github_pr_create": github_pr_create.run,
                },
            )

    def call(self, tool_name: str, args: dict[str, Any], capability: dict[str, Any], workspace: str) -> dict[str, Any]:
        if not isinstance(tool_name, str) or not tool_name:
            raise PolicyViolation("INVALID_ARGS", "Invalid tool_name.")

        allowed = capability.get("allowed_tools", [])
        allowed_tools = allowed if isinstance(allowed, list) else []
        if tool_name not in allowed_tools:
            raise PolicyViolation("TOOL_NOT_ALLOWED", f"Tool not allowed: {tool_name}")

        tool_fn = (self.tools or {}).get(tool_name)
        if tool_fn is None:
            raise PolicyViolation("TOOL_NOT_ALLOWED", f"Unknown tool: {tool_name}")

        if not isinstance(args, dict):
            raise PolicyViolation("INVALID_ARGS", "Tool args must be an object.")

        if tool_name == "secrets_get":
            secret_id = args.get("secret_id")
            if not isinstance(secret_id, str) or not secret_id.strip():
                raise PolicyViolation("INVALID_ARGS", "secrets_get requires non-empty 'secret_id'.")

            out = tool_fn(secret_id=secret_id.strip(), workspace=workspace)
            handle = out.get("handle") if isinstance(out, dict) else None
            handle_str = handle if isinstance(handle, str) and handle else None
            found = bool(out.get("found")) if isinstance(out, dict) else False
            status = out.get("status") if isinstance(out, dict) else None
            status_str = status if isinstance(status, str) and status else ("OK" if found else "NOT_FOUND")
            provider_used = out.get("provider_used") if isinstance(out, dict) else None
            provider_used_str = provider_used if isinstance(provider_used, str) and provider_used else None

            result: dict[str, Any] = {
                "tool": "secrets_get",
                "status": status_str,
                "bytes_in": 0,
                "bytes_out": 0,
                "secret_id": secret_id.strip(),
                "value": "***REDACTED***",
                "redacted": True,
                "found": found,
            }
            if provider_used_str is not None:
                result["provider_used"] = provider_used_str
            if handle_str is not None:
                result["handle"] = handle_str
            return result

        if tool_name == "github_pr_create":
            repo = args.get("repo")
            base = args.get("base", "main")
            head = args.get("head")
            title = args.get("title")
            body = args.get("body", "")
            draft = args.get("draft", True)

            if not isinstance(repo, str) or not repo.strip():
                raise PolicyViolation("INVALID_ARGS", "github_pr_create requires non-empty 'repo'.")
            if not isinstance(base, str) or not base.strip():
                raise PolicyViolation("INVALID_ARGS", "github_pr_create requires non-empty 'base'.")
            if not isinstance(head, str) or not head.strip():
                raise PolicyViolation("INVALID_ARGS", "github_pr_create requires non-empty 'head'.")
            if not isinstance(title, str) or not title.strip():
                raise PolicyViolation("INVALID_ARGS", "github_pr_create requires non-empty 'title'.")
            if not isinstance(body, str):
                body = ""
            if not isinstance(draft, bool):
                raise PolicyViolation("INVALID_ARGS", "github_pr_create requires boolean 'draft'.")

            out = tool_fn(
                repo=repo.strip(),
                base=base.strip(),
                head=head.strip(),
                title=title.strip(),
                body=body,
                draft=draft,
                workspace=workspace,
            )
            bytes_in = out.get("bytes_in")
            bytes_out = out.get("bytes_out")
            bytes_in_int = int(bytes_in) if isinstance(bytes_in, int) else 0
            bytes_out_int = int(bytes_out) if isinstance(bytes_out, int) else 0
            return {
                "tool": "github_pr_create",
                "status": out.get("status", "OK"),
                "bytes_in": bytes_in_int,
                "bytes_out": bytes_out_int,
                "repo": out.get("repo", repo.strip()),
                "number": out.get("number"),
                "pr_url": out.get("pr_url"),
                "redacted": True,
            }

        path_arg = args.get("path")
        if not isinstance(path_arg, str) or not path_arg.strip():
            raise PolicyViolation("INVALID_ARGS", "Tool args must include non-empty 'path'.")

        resolved = resolve_path_in_workspace(workspace=workspace, path=path_arg)

        if tool_name == "fs_read":
            encoding = args.get("encoding", "utf-8")
            if not isinstance(encoding, str) or not encoding:
                encoding = "utf-8"
            try:
                size = resolved.stat().st_size
            except FileNotFoundError as e:
                raise
            except Exception as e:
                raise RuntimeError(f"fs_read failed to stat file: {resolved}") from e

            if int(size) > int(self.max_bytes_in):
                raise PolicyViolation("READ_TOO_LARGE", f"Read too large: {size} bytes > {self.max_bytes_in}")

            out = tool_fn(path=resolved, encoding=encoding)
            raw_bytes = out.get("bytes")
            bytes_in = int(raw_bytes) if isinstance(raw_bytes, int) else int(size)
            return {
                "tool": "fs_read",
                "status": "OK",
                "bytes_in": bytes_in,
                "bytes_out": bytes_in,
                "resolved_path": out.get("resolved_path"),
                "text": out.get("text"),
            }

        if tool_name == "fs_write":
            encoding = args.get("encoding", "utf-8")
            if not isinstance(encoding, str) or not encoding:
                encoding = "utf-8"
            text = args.get("text")
            if not isinstance(text, str):
                raise PolicyViolation("INVALID_ARGS", "fs_write requires 'text' string.")

            if "\x00" in text:
                raise PolicyViolation("BINARY_FORBIDDEN", "Binary content forbidden (NUL byte present).")

            data = text.encode(encoding)
            bytes_in = len(data)
            if bytes_in > int(self.max_bytes_out):
                raise PolicyViolation("WRITE_TOO_LARGE", f"Write too large: {bytes_in} bytes > {self.max_bytes_out}")

            out = tool_fn(path=resolved, text=text, encoding=encoding)
            wrote = out.get("bytes")
            bytes_out = int(wrote) if isinstance(wrote, int) else bytes_in
            return {
                "tool": "fs_write",
                "status": "OK",
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
                "resolved_path": out.get("resolved_path"),
            }

        raise PolicyViolation("TOOL_NOT_ALLOWED", f"Unsupported tool: {tool_name}")
