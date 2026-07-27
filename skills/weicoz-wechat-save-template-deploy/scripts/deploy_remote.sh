#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${WEICOZ_WECHAT_SAVE_REPO_ROOT:?set WEICOZ_WECHAT_SAVE_REPO_ROOT}"
SSH_TARGET="${WEICOZ_WECHAT_SAVE_SSH_TARGET:?set WEICOZ_WECHAT_SAVE_SSH_TARGET}"
SSH_KEY="${WEICOZ_WECHAT_SAVE_SSH_KEY:?set WEICOZ_WECHAT_SAVE_SSH_KEY}"
REMOTE_DIR="${WEICOZ_WECHAT_SAVE_REMOTE_DIR:?set WEICOZ_WECHAT_SAVE_REMOTE_DIR}"
PM2_APP="${WEICOZ_WECHAT_SAVE_PM2_APP:?set WEICOZ_WECHAT_SAVE_PM2_APP}"
REMOTE_PORT="${WEICOZ_WECHAT_SAVE_REMOTE_PORT:?set WEICOZ_WECHAT_SAVE_REMOTE_PORT}"
REMOTE_NAME="${REMOTE_NAME:-origin}"

cd "$REPO_ROOT"

CURRENT_BRANCH="${CURRENT_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"

echo "[deploy-remote] remote git pull $REMOTE_NAME/$CURRENT_BRANCH"
ssh -i "$SSH_KEY" "$SSH_TARGET" "set -euo pipefail; git config --global --add safe.directory '$REMOTE_DIR'; cd '$REMOTE_DIR'; git fetch '$REMOTE_NAME' --prune; git checkout '$CURRENT_BRANCH'; git pull --ff-only '$REMOTE_NAME' '$CURRENT_BRANCH'; set -a; source .env.production; set +a; pnpm install --frozen-lockfile --prod=false; bash scripts/setup-wecom-sdk.sh '$REMOTE_DIR'; pnpm build; pnpm db:migrate; if ! pm2 describe '$PM2_APP' >/dev/null 2>&1; then pm2 resurrect || true; fi; if ! pm2 describe '$PM2_APP' >/dev/null 2>&1; then pm2 start /usr/bin/bash --name '$PM2_APP' -- -lc 'cd \"$REMOTE_DIR\" && pnpm start'; fi; pm2 restart '$PM2_APP' --update-env; pm2 save; sleep 3; curl -I -m 10 'http://127.0.0.1:$REMOTE_PORT'"

echo "[deploy-remote] done"
