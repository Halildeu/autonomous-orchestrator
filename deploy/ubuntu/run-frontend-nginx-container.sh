#!/usr/bin/env bash
set -euo pipefail

WEB_CURRENT_LINK="${WEB_CURRENT_LINK:-/home/halil/platform/web/current}"
NGINX_RUNTIME_DIR="${NGINX_RUNTIME_DIR:-/home/halil/platform/web/nginx}"
NGINX_CONTAINER_NAME="${NGINX_CONTAINER_NAME:-platform-web-nginx}"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.27-alpine}"
NGINX_CONFIG_PATH="${NGINX_CONFIG_PATH:-${NGINX_RUNTIME_DIR}/default.conf}"
NGINX_PORT="${NGINX_PORT:-5544}"
NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"
NGINX_HTTPS_PORT="${NGINX_HTTPS_PORT:-443}"
NGINX_SERVER_NAME="${NGINX_SERVER_NAME:-_}"
NGINX_TLS_ENABLED="${NGINX_TLS_ENABLED:-false}"
NGINX_TLS_CERT_PATH="${NGINX_TLS_CERT_PATH:-}"
NGINX_TLS_KEY_PATH="${NGINX_TLS_KEY_PATH:-}"
NGINX_GATEWAY_UPSTREAM="${NGINX_GATEWAY_UPSTREAM:-http://127.0.0.1:8080}"
NGINX_KEYCLOAK_UPSTREAM="${NGINX_KEYCLOAK_UPSTREAM:-http://127.0.0.1:8080}"

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

  local tls_enabled
  local docker_args=()
  local redirect_port_suffix=""
  tls_enabled="$(printf '%s' "${NGINX_TLS_ENABLED}" | tr '[:upper:]' '[:lower:]')"

  if [[ "${tls_enabled}" == "true" ]]; then
    if [[ -z "${NGINX_TLS_CERT_PATH}" || -z "${NGINX_TLS_KEY_PATH}" ]]; then
      echo "[error] NGINX_TLS_ENABLED=true but cert/key paths are missing." >&2
      exit 1
    fi
    if [[ ! -f "${NGINX_TLS_CERT_PATH}" ]]; then
      echo "[error] TLS certificate not found: ${NGINX_TLS_CERT_PATH}" >&2
      exit 1
    fi
    if [[ ! -f "${NGINX_TLS_KEY_PATH}" ]]; then
      echo "[error] TLS key not found: ${NGINX_TLS_KEY_PATH}" >&2
      exit 1
    fi

    if [[ "${NGINX_HTTPS_PORT}" != "443" ]]; then
      redirect_port_suffix=":${NGINX_HTTPS_PORT}"
    fi

    cat > "${NGINX_CONFIG_PATH}" <<EOF
server {
  listen ${NGINX_HTTP_PORT};
  server_name ${NGINX_SERVER_NAME};

  location = /nginx-healthz {
    access_log off;
    add_header Content-Type text/plain;
    return 200 'ok';
  }

  location / {
    return 301 https://\$host${redirect_port_suffix}\$request_uri;
  }
}

server {
  listen ${NGINX_HTTPS_PORT} ssl;
  server_name ${NGINX_SERVER_NAME};

  ssl_certificate /etc/nginx/tls/tls.crt;
  ssl_certificate_key /etc/nginx/tls/tls.key;

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
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Port \$server_port;
    proxy_pass ${NGINX_GATEWAY_UPSTREAM};
  }

  location /realms/ {
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Port \$server_port;
    proxy_pass ${NGINX_KEYCLOAK_UPSTREAM};
  }

  location /resources/ {
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Port \$server_port;
    proxy_pass ${NGINX_KEYCLOAK_UPSTREAM};
  }

  location / {
    try_files \$uri \$uri/ /index.html;
  }
}
EOF

    docker_args+=(
      -v "${NGINX_TLS_CERT_PATH}:/etc/nginx/tls/tls.crt:ro"
      -v "${NGINX_TLS_KEY_PATH}:/etc/nginx/tls/tls.key:ro"
    )
  else
    cat > "${NGINX_CONFIG_PATH}" <<EOF
server {
  listen ${NGINX_PORT};
  server_name ${NGINX_SERVER_NAME};

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
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_pass ${NGINX_GATEWAY_UPSTREAM};
  }

  location /realms/ {
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_pass ${NGINX_KEYCLOAK_UPSTREAM};
  }

  location /resources/ {
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_pass ${NGINX_KEYCLOAK_UPSTREAM};
  }

  location / {
    try_files \$uri \$uri/ /index.html;
  }
}
EOF
  fi

  docker pull "${NGINX_IMAGE}" >/dev/null
  docker rm -f "${NGINX_CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${NGINX_CONTAINER_NAME}" \
    --restart unless-stopped \
    --network host \
    -v "${resolved_root}:/usr/share/nginx/html:ro" \
    -v "${NGINX_CONFIG_PATH}:/etc/nginx/conf.d/default.conf:ro" \
    "${docker_args[@]}" \
    "${NGINX_IMAGE}" >/dev/null

  if [[ "${tls_enabled}" == "true" ]]; then
    echo "[nginx] container=${NGINX_CONTAINER_NAME} root=${resolved_root} http=${NGINX_HTTP_PORT} https=${NGINX_HTTPS_PORT} server_name=${NGINX_SERVER_NAME} tls=true"
  else
    echo "[nginx] container=${NGINX_CONTAINER_NAME} root=${resolved_root} port=${NGINX_PORT} server_name=${NGINX_SERVER_NAME} tls=false"
  fi
}

main "$@"
