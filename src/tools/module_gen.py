from __future__ import annotations

import argparse
import re
from pathlib import Path


MODULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,64}$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _render_template(text: str, *, module_id: str, intent: str) -> str:
    return text.replace("{{MODULE_ID}}", module_id).replace("{{INTENT}}", intent)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_inputs(*, module_id: str, intent: str) -> None:
    if not MODULE_ID_RE.match(module_id):
        raise SystemExit(
            "Invalid --module-id. Expected UPPER_SNAKE_CASE like MOD_EXAMPLE, "
            + f"regex={MODULE_ID_RE.pattern} got={module_id!r}"
        )
    if not (isinstance(intent, str) and intent.startswith("urn:") and len(intent) >= 5):
        raise SystemExit("Invalid --intent. Expected a URN like urn:core:example:demo.")


def generate_module_kit(*, module_id: str, intent: str, outdir: Path) -> None:
    repo_root = _repo_root()
    template_dir = repo_root / "templates" / "module"
    if not template_dir.exists():
        raise SystemExit(f"Missing templates directory: {template_dir}")

    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty outdir: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    template_paths = sorted([p for p in template_dir.iterdir() if p.is_file()], key=lambda p: p.name)
    if not template_paths:
        raise SystemExit(f"No template files found in: {template_dir}")

    for template_path in template_paths:
        rendered = _render_template(_read_text(template_path), module_id=module_id, intent=intent)
        _write_text(outdir / template_path.name, rendered)

    registry_entry_path = outdir / "registry_entry.json"
    entry_text = _read_text(registry_entry_path).rstrip() + "\n"
    patch_text = (
        "# REGISTRY PATCH SUGGESTION (DO NOT AUTO-APPLY)\n"
        "#\n"
        "# Add the following JSON object to: registry/registry.v1.json\n"
        "# under the top-level \"modules\" array.\n"
        "#\n\n"
        + entry_text
    )
    _write_text(outdir / "REGISTRY_PATCH.txt", patch_text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module-id", required=True)
    ap.add_argument("--intent", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    module_id = str(args.module_id).strip()
    intent = str(args.intent).strip()
    outdir = Path(args.outdir)

    _validate_inputs(module_id=module_id, intent=intent)
    generate_module_kit(module_id=module_id, intent=intent, outdir=outdir)
    print(f"OK: generated module kit at {outdir}")


if __name__ == "__main__":
    main()

