from __future__ import annotations

from pathlib import Path
from typing import Any

from src.shared.utils import write_bytes_atomic


def run(*, path: Path, text: str, encoding: str = "utf-8") -> dict[str, Any]:
    data = text.encode(encoding)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(path, data)
    return {"resolved_path": str(path), "bytes": len(data)}

