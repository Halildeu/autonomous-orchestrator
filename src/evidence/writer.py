from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.jsonio import save_json


@dataclass(frozen=True)
class EvidenceWriter:
    out_dir: Path
    run_id: str

    @property
    def run_dir(self) -> Path:
        return self.out_dir / self.run_id

    def write_request(self, envelope: dict) -> None:
        save_json(self.run_dir / "request.json", envelope)

    def write_summary(self, summary: dict) -> None:
        save_json(self.run_dir / "summary.json", summary)

    def write_suspend(self, suspend: dict) -> None:
        save_json(self.run_dir / "suspend.json", suspend)

    def write_resume_log(self, text: str) -> None:
        p = self.run_dir / "resume.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text.endswith("\n") else (text + "\n"), encoding="utf-8")

    def write_node_input(self, node_id: str, data: Any) -> None:
        save_json(self.run_dir / "nodes" / node_id / "input.json", data)

    def write_node_output(self, node_id: str, data: Any) -> None:
        save_json(self.run_dir / "nodes" / node_id / "output.json", data)

    def write_node_log(self, node_id: str, text: str) -> None:
        p = self.run_dir / "nodes" / node_id / "logs.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text.endswith("\n") else (text + "\n"), encoding="utf-8")
