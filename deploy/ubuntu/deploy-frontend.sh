#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/halil/platform/repo}"
WEB_DIR="${WEB_DIR:-${REPO_DIR}/web}"
REPO_BRANCH="${REPO_BRANCH:-main}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:?PUBLIC_ORIGIN required}"
AUTH_MODE="${AUTH_MODE:-keycloak}"
KEYCLOAK_PUBLIC_URL="${KEYCLOAK_PUBLIC_URL:-${PUBLIC_ORIGIN}}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-serban}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-frontend}"
WEB_RELEASES_DIR="${WEB_RELEASES_DIR:-/home/halil/platform/web/releases}"
WEB_CURRENT_LINK="${WEB_CURRENT_LINK:-/home/halil/platform/web/current}"
STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
CURRENT_RELEASE_FILE="${CURRENT_RELEASE_FILE:-${STATE_DIR}/web.current-release}"
PREVIOUS_RELEASE_FILE="${PREVIOUS_RELEASE_FILE:-${STATE_DIR}/web.previous-release}"
BUILD_SCRIPT="${BUILD_SCRIPT:-build:ubuntu:single-domain}"
NGINX_CONTAINER_ENABLED="${NGINX_CONTAINER_ENABLED:-false}"
NGINX_CONTAINER_SCRIPT="${NGINX_CONTAINER_SCRIPT:-${REPO_DIR}/deploy/ubuntu/run-frontend-nginx-container.sh}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

sync_repo() {
  if [[ -d "${REPO_DIR}/.git" ]]; then
    git -C "${REPO_DIR}" fetch origin "${REPO_BRANCH}"
    git -C "${REPO_DIR}" checkout "${REPO_BRANCH}"
    git -C "${REPO_DIR}" pull --ff-only origin "${REPO_BRANCH}"
    return 0
  fi

  if [[ -z "${GIT_REMOTE_URL}" ]]; then
    echo "[error] repo missing at ${REPO_DIR} and GIT_REMOTE_URL is empty." >&2
    exit 1
  fi

  mkdir -p "$(dirname "${REPO_DIR}")"
  git clone --branch "${REPO_BRANCH}" --depth 1 "${GIT_REMOTE_URL}" "${REPO_DIR}"
}

main() {
  require_cmd git
  require_cmd pnpm

  sync_repo
  mkdir -p "${STATE_DIR}" "${WEB_RELEASES_DIR}"

  if [[ -L "${WEB_CURRENT_LINK}" ]]; then
    readlink "${WEB_CURRENT_LINK}" > "${PREVIOUS_RELEASE_FILE}" || true
  fi

  (
    cd "${WEB_DIR}"
    pnpm install --frozen-lockfile
    WEB_PUBLIC_ORIGIN="${PUBLIC_ORIGIN}" \
    VITE_FRONTEND_PUBLIC_ORIGIN="${PUBLIC_ORIGIN}" \
    FRONTEND_PUBLIC_ORIGIN="${PUBLIC_ORIGIN}" \
    VITE_AUTH_MODE="${AUTH_MODE}" \
    AUTH_MODE="${AUTH_MODE}" \
    VITE_KEYCLOAK_URL="${KEYCLOAK_PUBLIC_URL}" \
    KEYCLOAK_URL="${KEYCLOAK_PUBLIC_URL}" \
    VITE_KEYCLOAK_REALM="${KEYCLOAK_REALM}" \
    KEYCLOAK_REALM="${KEYCLOAK_REALM}" \
    VITE_KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID}" \
    KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID}" \
    pnpm run "${BUILD_SCRIPT}"
  )

  local short_sha
  local release_dir
  short_sha="$(git -C "${REPO_DIR}" rev-parse --short HEAD)"
  release_dir="${WEB_RELEASES_DIR}/${short_sha}"

  rm -rf "${release_dir}"
  mkdir -p "${release_dir}"
  cp -R "${WEB_DIR}/dist/ubuntu-single-domain/." "${release_dir}/"

  ln -sfn "${release_dir}" "${WEB_CURRENT_LINK}"
  printf '%s\n' "${release_dir}" > "${CURRENT_RELEASE_FILE}"

  if [[ "${NGINX_CONTAINER_ENABLED}" == "true" ]]; then
    if [[ ! -x "${NGINX_CONTAINER_SCRIPT}" ]]; then
      echo "[error] nginx container script missing or not executable: ${NGINX_CONTAINER_SCRIPT}" >&2
      exit 1
    fi
    "${NGINX_CONTAINER_SCRIPT}"
  fi

  echo "[deploy] frontend release=${release_dir}"
  printf '%s\n' "${short_sha}"
}

main "$@"
