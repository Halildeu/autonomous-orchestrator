from __future__ import annotations

from pathlib import Path
from typing import Any


def run(*, path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode(encoding)
    return {"resolved_path": str(path), "bytes": len(data), "text": text}

