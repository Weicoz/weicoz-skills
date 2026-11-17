#!/usr/bin/env bash
# 给 T3 线程发消息，默认立即生效：空闲线程直接开跑，运行中的线程当轮引导（steer）改向。
# 用法：t3-send.sh <threadId> <消息|-> [--queue | --restart | --interrupt]
#   默认          空闲则起新一轮；运行中则显式 steer，引导当前轮（方向变化、纠偏、补条件）。
#                 MCP 的 auto 在运行中的线程上可能只排队，所以脚本先读状态，运行中直接用 steer。
#   --queue       有意排到下一轮，不打断当前轮（补充材料、非紧急的后续）。
#   --restart     中断当前轮并以本消息重开（任务安排不合理、要截停重来）。
#   --interrupt   只中断当前轮，不发新消息（消息参数仍需给一个原因）。
# 内部签 5 分钟 full-access MCP 令牌（线程默认 full-access，发送权限不能低于目标），用完立即吊销。
# 输出首词：SENT <mode> / ERROR。退出码：0 成功；1 调用失败；3 参数错误。
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=t3-lib.sh
. "$here/t3-lib.sh"
tid="${1:-}" msg="${2:-}" mode=auto interrupt=0
[ -n "$tid" ] && [ -n "$msg" ] || { echo "ERROR 用法：t3-send.sh <threadId> <消息|-> [--queue|--restart|--interrupt]" >&2; exit 3; }
shift 2
for a in "$@"; do
  case "$a" in
    --queue) mode=queue ;; --restart) mode=restart ;; --interrupt) interrupt=1 ;;
    *) echo "ERROR 未知参数 $a" >&2; exit 3 ;;
  esac
done
[ "$msg" = - ] && msg="$(cat)"
export T3_MCP_TOKEN="$(T3_MCP_ACCESS=full-access "$here/t3-mcp.py" login)"
revoke() {
  unset T3_MCP_TOKEN
  t3_call_quiet auth session list | grep -B4 'client: t3-dispatch' | grep -E '^[0-9a-f-]{36}$' | while read -r id; do t3_call_quiet auth session revoke "$id" >/dev/null 2>&1 || true; done
}
trap revoke EXIT
if [ "$interrupt" = 1 ]; then
  body=$(python3 -c 'import json,sys; print(json.dumps({"threadId":sys.argv[1],"reason":sys.argv[2][:2000]}))' "$tid" "$msg")
  "$here/t3-mcp.py" call t3_thread_interrupt "$body" >/dev/null || { echo "ERROR 中断失败" >&2; exit 1; }
  echo "SENT interrupt"; exit 0
fi
if [ "$mode" = auto ]; then
  st=$("$here/t3-mcp.py" call t3_thread_read "{\"threadId\":\"$tid\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["thread"]["status"])') || { echo "ERROR 读线程状态失败" >&2; exit 1; }
  [ "$st" = running ] && mode=steer
fi
body=$(python3 -c 'import json,sys; print(json.dumps({"threadId":sys.argv[1],"message":sys.argv[2],"mode":sys.argv[3]}))' "$tid" "$msg" "$mode")
out=$("$here/t3-mcp.py" call t3_thread_send "$body") || { echo "ERROR 发送失败" >&2; exit 1; }
echo "SENT $mode"
printf '%s\n' "$out" | python3 -c 'import json,sys
try: d=json.load(sys.stdin); print({k:d.get(k) for k in ("disposition","status","mode","runId") if k in d})
except Exception: pass' 2>/dev/null || true
