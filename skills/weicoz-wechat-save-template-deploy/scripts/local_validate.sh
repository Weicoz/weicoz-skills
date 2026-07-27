#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${WEICOZ_WECHAT_SAVE_REPO_ROOT:?set WEICOZ_WECHAT_SAVE_REPO_ROOT}"
LOCAL_DB_URL="${WEICOZ_WECHAT_SAVE_LOCAL_DB_URL:?set WEICOZ_WECHAT_SAVE_LOCAL_DB_URL}"
LOCAL_DB_NAME="${WEICOZ_WECHAT_SAVE_LOCAL_DB_NAME:?set WEICOZ_WECHAT_SAVE_LOCAL_DB_NAME}"
LOCAL_PG_CONTAINER="${WEICOZ_WECHAT_SAVE_LOCAL_PG_CONTAINER:?set WEICOZ_WECHAT_SAVE_LOCAL_PG_CONTAINER}"

cd "$REPO_ROOT"

echo "[local-validate] ensure local db: $LOCAL_DB_NAME"
if ! docker exec "$LOCAL_PG_CONTAINER" psql -U root -d root -At -c "select 1 from pg_database where datname='${LOCAL_DB_NAME}'" | grep -q 1; then
  docker exec "$LOCAL_PG_CONTAINER" psql -U root -d root -c "create database \"$LOCAL_DB_NAME\";"
fi

echo "[local-validate] run migration"
DATABASE_URL="$LOCAL_DB_URL" pnpm db:migrate

echo "[local-validate] build app"
pnpm build

echo "[local-validate] callback + mock archive ingest"
DATABASE_URL="$LOCAL_DB_URL" pnpm exec tsx scripts/test-wecom-archive-callback.ts

echo "[local-validate] done"
