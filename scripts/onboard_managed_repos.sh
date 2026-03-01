#!/usr/bin/env bash
# shellcheck shell=bash

set -euo pipefail

usage() {
  cat <<'EOF'
Kullanım:
  ./scripts/onboard_managed_repos.sh "<repo1,repo2,...>" [workspace_root_prefix]
  ./scripts/onboard_managed_repos.sh --input-file <repos.txt> [workspace_root_prefix]

Örnek:
  ./scripts/onboard_managed_repos.sh "/Users/halilkocoglu/Documents/autonomous-orchestrator,/Users/halilkocoglu/Documents/dev"
  ./scripts/onboard_managed_repos.sh --input-file /Users/halilkocoglu/Documents/dev/repos.txt

Not:
  workspace_root_prefix belirtilmezse WORKSPACE_ROOT_PREFIX env varı veya
  /Users/halilkocoglu/Documents/autonomous-orchestrator/.cache/ws_customer_default_multi2 kullanılır.
  GIT_DIRTY_TREE_MODE (ignore|allow|error) env ile override yapılabilir (default ignore).
  MANAGED_REPO_CRITICAL env ile override edilebilir (default true).
  Varsayılan olarak manifestte repo girdilerine critical=true yazılır.
  NETWORK_ENABLED, LIVE_GATE_ENABLED, LIVE_GATE_REQUIRE_ENV_KEY env'leri de bool olarak ayarlanabilir.
  repos.txt satır başına bir repo, virgül/; ile ayrılmış liste ya da boşluk içermeyen kombinasyonlar alabilir.
  Her çalıştırmada .cache/managed_repos.v1.json manifesti de güncellenir.
EOF
}

REPO_INPUT=""
REPO_INPUT_FILE=""
WORKSPACE_PREFIX="${WORKSPACE_ROOT_PREFIX:-/Users/halilkocoglu/Documents/autonomous-orchestrator/.cache/ws_customer_default_multi2}"
DIRTY_TREE_MODE="${GIT_DIRTY_TREE_MODE:-ignore}"
NETWORK_ENABLED="${NETWORK_ENABLED:-true}"
LIVE_GATE_ENABLED="${LIVE_GATE_ENABLED:-true}"
LIVE_GATE_REQUIRE_ENV_KEY="${LIVE_GATE_REQUIRE_ENV_KEY:-false}"
MANAGED_REPO_CRITICAL="${MANAGED_REPO_CRITICAL:-true}"
POSITIONALS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --input-file)
      shift
      if [ "$#" -eq 0 ]; then
        echo "HATA: --input-file için dosya yolu eksik."
        exit 1
      fi
      REPO_INPUT_FILE="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      echo "HATA: bilinmeyen seçenek: $1"
      usage
      exit 1
      ;;
    *)
      POSITIONALS+=("$1")
      ;;
  esac
  shift
done

if [ "${#POSITIONALS[@]}" -gt 2 ]; then
  echo "HATA: argüman formatı geçersiz. En fazla 2 konumsal argüman bekleniyor."
  usage
  exit 1
fi

if [ -z "$REPO_INPUT_FILE" ]; then
  if [ "${#POSITIONALS[@]}" -eq 0 ]; then
    echo "HATA: repo listesi veya --input-file belirtilmedi."
    usage
    exit 1
  fi
  REPO_INPUT="${POSITIONALS[0]}"
  if [ "${#POSITIONALS[@]}" -eq 2 ]; then
    WORKSPACE_PREFIX="${POSITIONALS[1]}"
  fi
else
  if [ "${#POSITIONALS[@]}" -eq 1 ]; then
    WORKSPACE_PREFIX="${POSITIONALS[0]}"
  elif [ "${#POSITIONALS[@]}" -gt 1 ]; then
    echo "HATA: --input-file ile aynı anda en fazla 1 konumsal argüman (workspace prefix) kullanılabilir."
    usage
    exit 1
  fi
fi

case "$DIRTY_TREE_MODE" in
  ignore|allow|error)
    ;;
  *)
    echo "HATA: GIT_DIRTY_TREE_MODE sadece ignore|allow|error olabilir."
    exit 2
    ;;
esac

REPO_LIST=()
REPO_SEEN_LIST=""

repo_is_seen() {
  local value="$1"
  local item
  if [ -z "${REPO_SEEN_LIST:-}" ]; then
    return 1
  fi
  while IFS= read -r item || [ -n "$item" ]; do
    if [ "$item" = "$value" ]; then
      return 0
    fi
  done <<EOF
${REPO_SEEN_LIST}
EOF
  return 1
}

trim() {
  printf '%s' "$1" | awk '{gsub(/^[ \t\r\n]+|[ \t\r\n]+$/, ""); print}'
}

add_repos_from_spec() {
  local spec="$1"
  while IFS= read -r repo || [ -n "$repo" ]; do
    repo="$(trim "$repo")"
    if [ -z "$repo" ]; then
      continue
    fi
    case "$repo" in
      \#*)
        continue
        ;;
    esac
    if repo_is_seen "$repo"; then
      continue
    fi
    if [ -n "${REPO_SEEN_LIST:-}" ]; then
      REPO_SEEN_LIST="${REPO_SEEN_LIST}
${repo}"
    else
      REPO_SEEN_LIST="${repo}"
    fi
    REPO_LIST+=("$repo")
  done < <(printf '%s' "$spec" | tr ';,' '\n')
}

if [ -n "$REPO_INPUT" ]; then
  add_repos_from_spec "$REPO_INPUT"
fi

if [ -n "$REPO_INPUT_FILE" ]; then
  if [ ! -f "$REPO_INPUT_FILE" ]; then
    echo "HATA: input dosyası bulunamadı => $REPO_INPUT_FILE"
    exit 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    add_repos_from_spec "$line"
  done < "$REPO_INPUT_FILE"
fi

if [ "${#REPO_LIST[@]}" -eq 0 ]; then
  echo "HATA: repo listesi boş."
  exit 2
fi

mkdir -p "$WORKSPACE_PREFIX"

REPO_ID=0
CREATED=0
RECORD_FILE="$(mktemp)"
RECORDS=0
trap 'rm -f "$RECORD_FILE"' EXIT

for repo in "${REPO_LIST[@]}"; do
  REPO_ID=$((REPO_ID + 1))
  if [ -z "$repo" ]; then
    continue
  fi
  if ! REPO_ABS="$(python3 - "$repo" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1]).expanduser().resolve()
print(str(repo))
PY
)"; then
    echo "HATA: repo okunamadı => $repo"
    continue
  fi

  if [ ! -d "$REPO_ABS" ]; then
    echo "UYARI: repo yolu bulunamadı veya klasör değil => $REPO_ABS"
    continue
  fi

  read -r REPO_SLUG REPO_HASH < <(python3 - "$REPO_ABS" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
slug = re.sub(r"[^a-z0-9._-]", "-", repo.name.lower().strip())
slug = re.sub(r"-{2,}", "-", slug).strip("-._") or "repo"
h = hashlib.sha1(str(repo).encode("utf-8")).hexdigest()[:8]
print(f"{slug} {h}")
PY
)

  WORKSPACE_ROOT="${WORKSPACE_PREFIX}/repo-${REPO_ID}-${REPO_SLUG}-${REPO_HASH}"
  OUT_FILE="${WORKSPACE_ROOT}/.cache/policy_overrides/policy_github_ops.override.v1.json"
  mkdir -p "$(dirname "$OUT_FILE")"

  python3 - "$OUT_FILE" "$DIRTY_TREE_MODE" "$NETWORK_ENABLED" "$LIVE_GATE_ENABLED" "$LIVE_GATE_REQUIRE_ENV_KEY" <<'PY'
import json
import sys

path = sys.argv[1]
dirty_tree_mode = sys.argv[2]

def to_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

payload = {
  "network_enabled": to_bool(sys.argv[3]),
  "live_gate": {
    "network_enabled": to_bool(sys.argv[3]),
    "enabled": to_bool(sys.argv[4]),
    "require_env_key_present": to_bool(sys.argv[5]),
  },
  "git_state_policy": {
    "dirty_tree": {
      "mode": dirty_tree_mode,
    }
  },
  "notes": ["repo-onboarding-playbook-v1"],
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY

  python3 - "$REPO_ABS" "$WORKSPACE_ROOT" "$REPO_SLUG" "$REPO_HASH" "$MANAGED_REPO_CRITICAL" >> "$RECORD_FILE" <<'PY'
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
workspace_root = Path(sys.argv[2]).resolve()
repo_slug = sys.argv[3]
repo_hash = sys.argv[4]
managed_repo_critical = str(sys.argv[5]).strip().lower() in {"1", "true", "yes", "y", "on"}

payload = {
    "repo_root": str(repo_root),
    "workspace_root": str(workspace_root),
    "repo_slug": repo_slug,
    "repo_id": repo_hash,
    "critical": managed_repo_critical,
}
print(json.dumps(payload, ensure_ascii=False))
PY

  echo "OK: $REPO_ABS -> $OUT_FILE"
  RECORDS=$((RECORDS + 1))
  CREATED=$((CREATED + 1))
done

python3 - "$WORKSPACE_PREFIX" "$RECORD_FILE" <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

workspace_prefix = Path(sys.argv[1]).expanduser().resolve()
record_path = Path(sys.argv[2]).expanduser().resolve()
manifest_path = workspace_prefix / ".cache" / "managed_repos.v1.json"

repos = []
if record_path.exists():
    for raw in record_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if isinstance(item, dict):
            repos.append(item)

manifest_payload = {
    "version": "v1",
    "kind": "managed-repos-manifest",
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "repos": repos,
    "meta": {
        "count": len(repos),
        "source": "onboard_managed_repos.sh",
    },
}

manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "Tamam: $CREATED repo için override üretildi. Manifest: ${WORKSPACE_PREFIX}/.cache/managed_repos.v1.json"
