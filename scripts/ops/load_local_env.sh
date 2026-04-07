#!/usr/bin/env bash
set -euo pipefail

LOCAL_ENV_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -eq 0 ]]; then
  set -- \
    NVD_API_KEY \
    DEPENDENCY_CHECK_VERSION \
    DEPENDENCY_CHECK_FAIL_CVSS \
    DEPENDENCY_CHECK_NVD_API_DELAY_MS \
    DEPENDENCY_CHECK_NVD_MAX_RETRY_COUNT \
    DEPENDENCY_CHECK_NVD_RESULTS_PER_PAGE
fi

exports="$(python3 "${LOCAL_ENV_SCRIPT_DIR}/export_local_env.py" "$@" || true)"
if [[ -n "${exports}" ]]; then
  eval "${exports}"
fi
