#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
TMP_FILE="/tmp/check_security_backend.$$"
SECRET_ASSIGNMENT_PATTERN='(?i)(password|secret|api[_-]?key|token)\s*[:=]\s*(?!\$\{|\$[A-Z_]+|envVars\.|process\.env\.|__ENV\.)(?!.*(change[-_]?me|placeholder|postgres|admin1234|dev-secret|example|your_))[A-Za-z0-9_./@:+-]{20,}'

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "[check_security_backend] HATA: backend/ klasoru bulunamadi." >&2
  exit 1
fi

COMMON_GLOBS=(
  --glob '!docs/**'
  --glob '!**/legacy/**'
  --glob '!**/target/**'
  --glob '!**/.git/**'
  --glob '!**/node_modules/**'
  --glob '!**/.env'
  --glob '!**/.env.local'
  --glob '!**/.autopilot-tmp/**'
  --glob '!**/src/main/java/**'
  --glob '!**/src/test/**'
  --glob '!**/mvnw'
  --glob '!**/mvnw.cmd'
  --glob '!**/*.example'
  --glob '!**/.env.example'
  --glob '!**/application-local.properties'
  --glob '!**/application-docker.properties'
  --glob '!**/docker-compose*.yml'
  --glob '!**/devops/**'
  --glob '!**/packages/**'
  --glob '!**/scripts/perf/**'
  --glob '!**/scripts/vault/**'
  --glob '!**/scripts/test-users-and-variants.sh'
  --glob '!**/infra/**'
  --glob '!**/test-results/**'
)

run_search_with_python() {
  local pattern="$1"
  python3 - "$pattern" "${BACKEND_DIR}" >"${TMP_FILE}" <<'PY'
import os
import re
import sys

pattern = sys.argv[1]
root = sys.argv[2]

regex = re.compile(pattern)
exclude_dir_names = {"docs", "legacy", "target", ".git", "node_modules", ".autopilot-tmp", "packages", "devops", "infra", "test-results"}
exclude_subpaths = ("src/main/java", "src/test", "scripts/perf", "scripts/vault")
exclude_file_names = {"mvnw", "mvnw.cmd", "test-users-and-variants.sh"}
exclude_suffixes = (".example", ".env.example", "application-local.properties", "application-docker.properties")
    exclude_file_basenames = {".env", ".env.local"}

found = False


def normalize(rel_path: str) -> str:
    if rel_path in ("", "."):
        return ""
    return rel_path.replace(os.sep, "/")


def contains_subpath(rel_path: str, subpath: str) -> bool:
    rel_path = normalize(rel_path)
    subpath = subpath.strip("/")
    if not rel_path:
        return False
    return (
        rel_path == subpath
        or rel_path.startswith(f"{subpath}/")
        or rel_path.endswith(f"/{subpath}")
        or f"/{subpath}/" in rel_path
    )

for dirpath, dirnames, filenames in os.walk(root):
    rel_dir_posix = normalize(os.path.relpath(dirpath, root))

    kept_dirs = []
    for dirname in dirnames:
        rel_path = f"{rel_dir_posix}/{dirname}" if rel_dir_posix else dirname
        if dirname in exclude_dir_names:
            continue
        if any(contains_subpath(rel_path, prefix) for prefix in exclude_subpaths):
            continue
        kept_dirs.append(dirname)
    dirnames[:] = kept_dirs

    for filename in filenames:
        rel_path = f"{rel_dir_posix}/{filename}" if rel_dir_posix else filename
        if filename in exclude_file_names or filename in exclude_file_basenames:
            continue
        if any(contains_subpath(rel_path, prefix) for prefix in exclude_subpaths):
            continue
        if filename.startswith("docker-compose") and filename.endswith(".yml"):
            continue
        if any(rel_path.endswith(suffix) for suffix in exclude_suffixes):
            continue
        full_path = os.path.join(dirpath, filename)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if regex.search(line):
                        print(f"{full_path}:{line_number}:{line.rstrip()}")
                        found = True
        except OSError:
            continue

sys.exit(0 if found else 1)
PY
}

run_search() {
  local label="$1"
  local pattern="$2"
  echo "[check_security_backend] Kontrol: $label"
  if command -v rg >/dev/null 2>&1; then
    rg -n --pcre2 "$pattern" "${BACKEND_DIR}" "${COMMON_GLOBS[@]}" >"${TMP_FILE}" 2>/dev/null
  else
    run_search_with_python "$pattern"
  fi
  local search_status=$?
  if [[ $search_status -eq 0 ]]; then
    echo "[WARN] $label icin potansiyel bulgular:"
    cat "${TMP_FILE}"
    echo
    return 1
  fi
  if [[ $search_status -ne 1 ]]; then
    echo "[check_security_backend] HATA: $label aramasi calistirilamadi." >&2
    return 2
  fi
  echo "[OK]   $label icin supheli satir bulunamadi."
  return 0
}

fail=0
run_search "Private key icerigi" 'BEGIN\s+PRIVATE\s+KEY' || fail=1
run_search "AWS benzeri access key" 'AKIA[0-9A-Z]{16}' || fail=1
run_search "Supheli literal secret assignment" "$SECRET_ASSIGNMENT_PATTERN" || fail=1
rm -f "${TMP_FILE}" 2>/dev/null || true

if [[ $fail -ne 0 ]]; then
  echo "[check_security_backend] Incelenmesi gereken backend security bulgulari var ❌"
  exit 1
fi

echo "[check_security_backend] Backend security lint temiz ✅"
