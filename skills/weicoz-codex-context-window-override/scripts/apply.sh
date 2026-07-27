#!/usr/bin/env bash
set -euo pipefail

MODEL_SLUG="${1:-gpt-5.5}"
WINDOW_SIZE="${2:-1000000}"
CODEX_DIR="${CODEX_DIR:-${WEICOZ_CODEX_ROOT:?WEICOZ_CODEX_ROOT is required}}"
CONFIG_FILE="${CODEX_CONFIG_FILE:-$CODEX_DIR/config.toml}"
SOURCE_CATALOG="${CODEX_MODELS_CACHE:-$CODEX_DIR/models_cache.json}"
BACKUP_DIR="$CODEX_DIR/backups/codex-context-window-override"
OVERRIDE_DIR="$CODEX_DIR/model-catalog-overrides"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SAFE_MODEL_SLUG="$(printf '%s' "$MODEL_SLUG" | tr -c '[:alnum:]._-' '-')"
OVERRIDE_FILE="$OVERRIDE_DIR/${SAFE_MODEL_SLUG}-${WINDOW_SIZE}-${TIMESTAMP}.json"
BACKUP_FILE="$BACKUP_DIR/config.toml.${TIMESTAMP}.bak"
CURRENT_CATALOG=""

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command jq
require_command perl
require_command codex

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Codex config not found: $CONFIG_FILE" >&2
  exit 1
fi

if [ ! -f "$SOURCE_CATALOG" ]; then
  echo "Codex model cache not found: $SOURCE_CATALOG" >&2
  exit 1
fi

existing_override="$(awk -F' = ' '/^model_catalog_json/ {gsub(/"/, "", $2); print $2; exit}' "$CONFIG_FILE")"
if [ -n "$existing_override" ] && [ -f "$existing_override" ]; then
  CURRENT_CATALOG="$existing_override"
else
  CURRENT_CATALOG="$SOURCE_CATALOG"
fi

if ! jq -e --arg slug "$MODEL_SLUG" '.models[] | select(.slug == $slug)' "$CURRENT_CATALOG" >/dev/null; then
  echo "Model slug not found in active catalog: $MODEL_SLUG" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR" "$OVERRIDE_DIR"
cp "$CONFIG_FILE" "$BACKUP_FILE"

jq \
  --arg slug "$MODEL_SLUG" \
  --argjson window "$WINDOW_SIZE" \
  '(.models[] | select(.slug == $slug) | .context_window) = $window
   | (.models[] | select(.slug == $slug) | .max_context_window) = $window' \
  "$CURRENT_CATALOG" > "$OVERRIDE_FILE"

export OVERRIDE_FILE
perl -0pi -e '
  my $line = "model_catalog_json = \"$ENV{OVERRIDE_FILE}\"\n";
  if (s/^model_catalog_json\s*=.*\n/$line/m) {
    next;
  }
  if (s/^(model_auto_compact_token_limit\s*=.*\n)/$1$line/m) {
    next;
  }
  s/^(model\s*=.*\n)/$1$line/m;
' "$CONFIG_FILE"

echo "Applied Codex model catalog override"
echo "model=$MODEL_SLUG"
echo "window=$WINDOW_SIZE"
echo "config=$CONFIG_FILE"
echo "backup=$BACKUP_FILE"
echo "override=$OVERRIDE_FILE"
echo "source_catalog=$CURRENT_CATALOG"
echo
echo "Verification:"
if [ "$CONFIG_FILE" = "$WEICOZ_CODEX_ROOT/config.toml" ]; then
  codex debug models | jq --arg slug "$MODEL_SLUG" '.models[] | select(.slug == $slug) | {slug,context_window,max_context_window,effective_context_window_percent}'
else
  codex debug models -c "model_catalog_json=\"$OVERRIDE_FILE\"" | jq --arg slug "$MODEL_SLUG" '.models[] | select(.slug == $slug) | {slug,context_window,max_context_window,effective_context_window_percent}'
fi
echo
echo "Rollback:"
echo "bash \"${BASH_SOURCE[0]%/*}/rollback.sh\""
echo "or: cp \"$BACKUP_FILE\" \"$CONFIG_FILE\""
echo
echo "Warning: this is a client-side catalog override. It does not guarantee server-side long-context support."
