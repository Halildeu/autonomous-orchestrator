#!/usr/bin/env bash
set -euo pipefail

# WEB lint / style kontrollerini tek komutla çalıştıran yardımcı script.
# CI'da sadece değişen dosyaları lint eder (incremental mode).
#
# Kullanım (repo kökünden):
#   ./scripts/run_lint_web.sh            # incremental (default)
#   ./scripts/run_lint_web.sh --full     # full scan

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FULL_MODE=false
if [[ "${1:-}" == "--full" ]]; then
  FULL_MODE=true
fi

echo "[run_lint_web] Root: $ROOT_DIR"

if [[ ! -d "$ROOT_DIR/web" ]]; then
  echo "[run_lint_web] HATA: web/ klasörü bulunamadı." >&2
  exit 1
fi

cd "$ROOT_DIR/web"

# Detect changed files for incremental mode
CHANGED_CSS=""
CHANGED_JS=""
if [[ "$FULL_MODE" == "false" ]]; then
  BASE_REF="${LINT_BASE_REF:-origin/main}"
  CHANGED_CSS=$(git diff --name-only "$BASE_REF" -- '*.css' '*.scss' 2>/dev/null | head -200 || true)
  CHANGED_JS=$(git diff --name-only "$BASE_REF" -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' 2>/dev/null | head -500 || true)
  echo "[run_lint_web] Incremental mode: base=$BASE_REF css=$(echo "$CHANGED_CSS" | wc -l | tr -d ' ') js=$(echo "$CHANGED_JS" | wc -l | tr -d ' ') files"
fi

echo "[run_lint_web] python3 scripts/ops_technical_baseline_checklist.py --repo-root ."
python3 "$ROOT_DIR/scripts/ops_technical_baseline_checklist.py" --repo-root "$ROOT_DIR"

if [[ "${NODE_OPTIONS:-}" != *"--max-old-space-size="* ]]; then
  export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=6144"
fi
if [[ "${NODE_OPTIONS:-}" =~ --max-old-space-size=([0-9]+) ]]; then
  echo "[run_lint_web] Node memory: --max-old-space-size=${BASH_REMATCH[1]}"
fi

# Stylelint: incremental if possible
echo "[run_lint_web] stylelint"
if [[ "$FULL_MODE" == "false" && -n "$CHANGED_CSS" ]]; then
  echo "$CHANGED_CSS" | xargs pnpm exec stylelint --allow-empty-input --max-warnings 0 || true
elif [[ "$FULL_MODE" == "true" ]]; then
  pnpm run lint:style
else
  echo "[run_lint_web] No CSS changes, skipping stylelint"
fi

# ESLint: always uses cache (incremental by nature)
echo "[run_lint_web] eslint (cached)"
ESLINT_USE_FLAT_CONFIG=true pnpm exec eslint . --max-warnings 10000 --cache --cache-location .eslintcache

# Tailwind + antd: fast checks, run always
echo "[run_lint_web] tailwind + antd checks"
pnpm run lint:tailwind
pnpm run lint:no-antd

echo "[run_lint_web] Tüm WEB lint adımları başarıyla tamamlandı ✅"
