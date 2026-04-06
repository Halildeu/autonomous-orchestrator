#!/usr/bin/env bash
set -euo pipefail

WEB_CURRENT_LINK="${WEB_CURRENT_LINK:-/home/halil/platform/web/current}"
NGINX_RUNTIME_DIR="${NGINX_RUNTIME_DIR:-/home/halil/platform/web/nginx}"
NGINX_CONTAINER_NAME="${NGINX_CONTAINER_NAME:-platform-web-nginx}"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.27-alpine}"
NGINX_CONFIG_PATH="${NGINX_CONFIG_PATH:-${NGINX_RUNTIME_DIR}/default.conf}"
NGINX_PORT="${NGINX_PORT:-5544}"
NGINX_GATEWAY_UPSTREAM="${NGINX_GATEWAY_UPSTREAM:-http://127.0.0.1:8080}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

main() {
  require_cmd docker
  require_cmd readlink

  if [[ ! -e "${WEB_CURRENT_LINK}" ]]; then
    echo "[error] current frontend release not found: ${WEB_CURRENT_LINK}" >&2
    exit 1
  fi

  local resolved_root
  resolved_root="$(readlink -f "${WEB_CURRENT_LINK}")"
  if [[ -z "${resolved_root}" || ! -d "${resolved_root}" ]]; then
    echo "[error] failed to resolve frontend release directory from ${WEB_CURRENT_LINK}" >&2
    exit 1
  fi

  mkdir -p "${NGINX_RUNTIME_DIR}"

  cat > "${NGINX_CONFIG_PATH}" <<EOF
server {
  listen ${NGINX_PORT};
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  location = /nginx-healthz {
    access_log off;
    add_header Content-Type text/plain;
    return 200 'ok';
  }

  location /assets/ {
    try_files \$uri =404;
    access_log off;
    expires 1h;
    add_header Cache-Control "public, max-age=3600, immutable";
  }

  location /remotes/ {
    try_files \$uri =404;
    access_log off;
    expires 1h;
    add_header Cache-Control "public, max-age=3600, immutable";
  }

  location /api/ {
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_pass ${NGINX_GATEWAY_UPSTREAM};
  }

  location / {
    try_files \$uri \$uri/ /index.html;
  }
}
EOF

  docker pull "${NGINX_IMAGE}" >/dev/null
  docker rm -f "${NGINX_CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${NGINX_CONTAINER_NAME}" \
    --restart unless-stopped \
    --network host \
    -v "${resolved_root}:/usr/share/nginx/html:ro" \
    -v "${NGINX_CONFIG_PATH}:/etc/nginx/conf.d/default.conf:ro" \
    "${NGINX_IMAGE}" >/dev/null

  echo "[nginx] container=${NGINX_CONTAINER_NAME} root=${resolved_root} port=${NGINX_PORT}"
}

main "$@"
