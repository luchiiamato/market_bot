#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

MODE="${MARKET_BOT_RUNTIME_MODE:-local}"
LOCAL_HOST="${MARKET_BOT_LOCAL_BACKEND_HOST:-127.0.0.1}"
LOCAL_PORT="${MARKET_BOT_LOCAL_BACKEND_PORT:-8000}"
FRONTEND_PORT="${MARKET_BOT_LOCAL_FRONTEND_PORT:-4173}"

"$ROOT_DIR/scripts/render_runtime_config.sh" "$ENV_FILE"

cd "$ROOT_DIR"

case "$MODE" in
  local)
    echo "[workspace] mode=local"
    echo "[workspace] backend: http://${LOCAL_HOST}:${LOCAL_PORT}"
    echo "[workspace] frontend: http://${LOCAL_HOST}:${LOCAL_PORT}/app/"
    exec python3 -m uvicorn services.api.app:app --host "$LOCAL_HOST" --port "$LOCAL_PORT" --reload
    ;;
  host)
    if [[ -z "${MARKET_BOT_HOSTED_API_BASE:-}" ]]; then
      echo "[workspace] MARKET_BOT_HOSTED_API_BASE is required when MARKET_BOT_RUNTIME_MODE=host" >&2
      exit 1
    fi
    echo "[workspace] mode=host"
    echo "[workspace] frontend local: http://${LOCAL_HOST}:${FRONTEND_PORT}"
    echo "[workspace] backend remoto: ${MARKET_BOT_HOSTED_API_BASE}"
    cd "$ROOT_DIR/apps/web/prototype"
    exec python3 -m http.server "$FRONTEND_PORT" --bind "$LOCAL_HOST"
    ;;
  *)
    echo "[workspace] invalid MARKET_BOT_RUNTIME_MODE=$MODE (expected: local | host)" >&2
    exit 1
    ;;
esac
