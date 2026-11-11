#!/usr/bin/env bash
# 只执行无交互签到和额度回读；不登录、不打开网页、不安装客户端。
set -uo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MAGPIE_BIN="${WEICOZ_FREE_TOKEN_MAGPIE:-}"
if [[ -z "$MAGPIE_BIN" ]]; then
  MAGPIE_BIN="$(command -v magpie 2>/dev/null || true)"
fi
if [[ -z "$MAGPIE_BIN" || ! -x "$MAGPIE_BIN" ]]; then
  echo "错误：未找到 magpie。请先安装并在 PATH 中提供 magpie。" >&2
  exit 127
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "错误：未找到 jq，无法回读签到与额度状态。" >&2
  exit 127
fi

TODAY="$(date '+%Y-%m-%d')"
NOW_HM="$(date '+%H%M')"
STATE_FILE="${WEICOZ_FREE_TOKEN_CHECKIN_STATE:-$HOME/.config/magpie/plugin-checkin.json}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/weicoz-free-token-checkin.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "## 免费额度签到 $TODAY"
if (( 10#$NOW_HM < 1005 )); then
  echo "提示：Qoder CN 每天 10:00 后才可领取，当前尚未到稳定领取时间。"
fi

echo
echo "### Magpie 签到"
"$MAGPIE_BIN" accounts checkin 2>&1 | tee "$TMP_DIR/checkin.out"
CHECKIN_RC=${PIPESTATUS[0]}

echo
echo "### 今日状态"
if [[ -f "$STATE_FILE" ]]; then
  jq -r --arg day "$TODAY" '
    to_entries[]
    | select(.value.day == $day)
    | [
        .key,
        (.value.outcome // "unknown"),
        (if .value.credit != null then "+" + (.value.credit|tostring) else "" end),
        (if .value.streak != null then ((.value.streak|tostring) + " 天") else "" end),
        (.value.msg // "")
      ]
    | @tsv
  ' "$STATE_FILE" 2>/dev/null |
  while IFS=$'\t' read -r key outcome credit streak message; do
    printf -- '- %s: %s' "$key" "$outcome"
    [[ -n "$credit" ]] && printf ' %s' "$credit"
    [[ -n "$streak" ]] && printf '，连续 %s' "$streak"
    [[ -n "$message" ]] && printf '，%s' "$message"
    printf '\n'
  done
else
  echo "- 未找到 $STATE_FILE"
fi

echo
echo "### 额度"
PROVIDERS="${WEICOZ_FREE_TOKEN_QUOTA_PROVIDERS:-workbuddy modelscope-plugin cloudflare-workers-ai-plugin amd-token-factory-plugin newapi-plugin opencode-go}"
read -r -a PROVIDER_LIST <<< "$PROVIDERS"
QUOTA_RC=0
"$MAGPIE_BIN" quota "${PROVIDER_LIST[@]}" --json > "$TMP_DIR/quota.json" 2>"$TMP_DIR/quota.err" || QUOTA_RC=$?

if [[ -s "$TMP_DIR/quota.json" ]]; then
  jq -r '
    .[]
    | .provider as $provider
    | .name as $name
    | if .error then
        "- \($provider) \($name): 不可读 — \(.error)"
      else
        ([.windows[]? | .display // (if .unlimited then "无限制" else ((.remaining // 0)|tostring) + "% 剩余" end)]
          | if length == 0 then empty else "- \($provider) \($name): " + join("; ") end),
        (if (.windows|length) == 0 and .balance then "- \($provider) \($name): \(.balance)" else empty end)
      end
  ' "$TMP_DIR/quota.json"
else
  echo "- 额度读取失败（退出码 $QUOTA_RC）"
  sed -n '1,3p' "$TMP_DIR/quota.err"
fi

echo
echo "网页和客户端签到项目见 references/daily-checkins.md。"
exit "$CHECKIN_RC"
