#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="${CODEX_DIR:-${WEICOZ_CODEX_ROOT:?WEICOZ_CODEX_ROOT is required}}"
CONFIG_FILE="${CODEX_CONFIG_FILE:-$CODEX_DIR/config.toml}"
BACKUP_DIR="$CODEX_DIR/backups/codex-context-window-override"
BACKUP_FILE="${1:-}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command codex
require_command jq

if [ -z "$BACKUP_FILE" ]; then
  if [ ! -d "$BACKUP_DIR" ]; then
    echo "Backup directory not found: $BACKUP_DIR" >&2
    exit 1
  fi
  BACKUP_FILE="$(find "$BACKUP_DIR" -type f -name 'config.toml.*.bak' -print | sort | tail -n 1)"
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found. Pass an explicit backup path or run apply.sh first." >&2
  exit 1
fi

cp "$BACKUP_FILE" "$CONFIG_FILE"

echo "Rolled back Codex config"
echo "restored=$BACKUP_FILE"
echo "config=$CONFIG_FILE"
echo
echo "Current config markers:"
if command -v rg >/dev/null 2>&1; then
  rg -n 'model_catalog_json|model_context_window|model_auto_compact_token_limit|^model =' "$CONFIG_FILE" || true
else
  grep -nE 'model_catalog_json|model_context_window|model_auto_compact_token_limit|^model =' "$CONFIG_FILE" || true
fi
echo
echo "Current gpt-5.5 catalog:"
if [ "$CONFIG_FILE" = "$WEICOZ_CODEX_ROOT/config.toml" ]; then
  codex debug models | jq '.models[] | select(.slug == "gpt-5.5") | {slug,context_window,max_context_window,effective_context_window_percent}'
else
  catalog_path="$(awk -F' = ' '/^model_catalog_json/ {gsub(/"/, "", $2); print $2; exit}' "$CONFIG_FILE")"
  if [ -n "$catalog_path" ] && [ -f "$catalog_path" ]; then
    codex debug models -c "model_catalog_json=\"$catalog_path\"" | jq '.models[] | select(.slug == "gpt-5.5") | {slug,context_window,max_context_window,effective_context_window_percent}'
  else
    echo "Skipped codex debug verification for non-default CODEX_DIR without model_catalog_json."
  fi
fi
