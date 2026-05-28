#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[preflight] repo: $ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[preflight] missing: python3" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[preflight] missing: node" >&2
  exit 1
fi

echo "[preflight] python: $(python3 --version 2>&1)"
echo "[preflight] node: $(node --version 2>&1)"

echo "[preflight] pytest"
python3 -m pytest -q

echo "[preflight] py_compile"
python3 -m py_compile \
  services/api/app.py \
  services/api/logging_config.py \
  packages/identity/src/market_identity/store.py

echo "[preflight] frontend syntax"
node --check apps/web/prototype/app.js

echo "[preflight] frontend build"
node apps/web/prototype/build.js

echo "[preflight] done"
echo "[preflight] next manual steps:"
echo "  1. flyctl auth login"
echo "  2. flyctl apps create market-bot-api"
echo "  3. flyctl volumes create market_bot_data --app market-bot-api --region gru --size 1"
echo "  4. flyctl secrets set MARKET_BOT_DB_PATH=/data/market_bot.db --app market-bot-api"
echo "  5. flyctl deploy --app market-bot-api"
echo "  6. vercel link apps/web/prototype"
echo "  7. set MARKET_BOT_API_BASE in Vercel"
echo "  8. vercel --prod"
