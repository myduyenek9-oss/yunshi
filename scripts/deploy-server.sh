#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/fortune-reminder}"
REPO_URL="${REPO_URL:-https://github.com/myduyenek9-oss/yunshi.git}"
BRANCH="${BRANCH:-main}"
ENV_BACKUP="/root/fortune-reminder.env.backup"

echo "[deploy] app dir: ${APP_DIR}"
mkdir -p "${APP_DIR}"

if [[ -f "${APP_DIR}/.env" ]]; then
  install -m 600 "${APP_DIR}/.env" "${ENV_BACKUP}"
fi

if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" remote set-url origin "${REPO_URL}"
  git -C "${APP_DIR}" fetch --prune origin "${BRANCH}"
  git -C "${APP_DIR}" checkout -B "${BRANCH}" "origin/${BRANCH}"
else
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT
  git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${tmp_dir}/repo"
  find "${APP_DIR}" -mindepth 1 -maxdepth 1 ! -name '.env' ! -name 'data' -exec rm -rf {} +
  cp -a "${tmp_dir}/repo/." "${APP_DIR}/"
fi

if [[ -f "${ENV_BACKUP}" ]]; then
  install -m 600 "${ENV_BACKUP}" "${APP_DIR}/.env"
fi

if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "[deploy] ERROR: ${APP_DIR}/.env is missing" >&2
  exit 1
fi


# Non-secret compatibility default for the current OpenAI-compatible relay.
# Keeps the app working if the primary model returns an empty SSE response.
if ! grep -q '^OPENAI_FALLBACK_MODELS=' "${APP_DIR}/.env"; then
  if grep -Fq 'ai.yxkl.cloud' "${APP_DIR}/.env"; then
    printf '\nOPENAI_FALLBACK_MODELS=gpt-5.4,gpt-5.6-luna,gpt-5.6-terra\n' >> "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"
    echo "[deploy] added OPENAI_FALLBACK_MODELS for relay compatibility"
  fi
fi

mkdir -p "${APP_DIR}/data"
cd "${APP_DIR}"

echo "[deploy] rebuilding container"
docker compose up -d --build
docker compose ps

for i in {1..12}; do
  if curl -fsS "http://127.0.0.1:${APP_PORT:-8088}/health" >/tmp/fortune-health.json; then
    cat /tmp/fortune-health.json
    echo
    echo "[deploy] success"
    exit 0
  fi
  sleep 5
done

echo "[deploy] health check failed" >&2
docker compose logs --tail=120 fortune-reminder >&2 || true
exit 1