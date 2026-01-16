from __future__ import annotations

from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    html_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "web" / "index.html"
    js_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "web" / "assets" / "app.js"

    html = html_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")

    required_html = [
        'id="sidebar"',
        'class="topbar"',
        'id="toast-container"',
        'id="action-log"',
        'id="evidence-tree"',
        'id="evidence-viewer"',
        'id="confirm-modal"',
    ]
    for token in required_html:
        if token not in html:
            raise SystemExit(f"ui_render_smoke_contract_test missing html token: {token}")

    required_js = [
        "setupNav",
        "setupOps",
        "setupStream",
        "renderTable",
    ]
    for token in required_js:
        if token not in js:
            raise SystemExit(f"ui_render_smoke_contract_test missing js token: {token}")


if __name__ == "__main__":
    main()
