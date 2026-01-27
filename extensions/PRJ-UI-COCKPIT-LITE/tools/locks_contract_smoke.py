from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _import_server():
    here = Path(__file__).resolve()
    server_dir = here.parents[1]
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    import server  # noqa: WPS433

    return server


def main() -> int:
    server = _import_server()
    payload = {
        "lock_state": "LOCKED",
        "expires_at": datetime.now(timezone.utc),
        "claims_active_sample": [
            {
                "owner_tag": "smoke",
                "expires_at": datetime.now(timezone.utc),
                "ttl_seconds": 60,
            }
        ],
        "bytes_field": b"lock-smoke",
        "set_field": {"a", "b"},
        "tuple_field": ("x", "y"),
    }
    try:
        normalized = server._normalize_jsonable(payload)
        json.dumps(normalized)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL reason_code=LOCKS_SERIALIZE_FAIL detail={exc}")
        return 2
    print("PASS reason_code=LOCKS_SERIALIZE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
