#!/usr/bin/env bash
# 给已派出的 T3 会话设推理等级（t3 thread start 命令行传不了 options）。
# 用法：t3-effort.sh <threadId> <providerInstanceId> '<模型串>' [max|high|low|off]
# 会话默认 full-access，改配置需同等权限：内部签 5 分钟 full-access MCP 令牌，设置并读回校验后立即吊销。
set -euo pipefail
tid="$1"; provider="$2"; model="$3"; effort="${4:-max}"
here="$(cd "$(dirname "$0")" && pwd)"
export T3_MCP_TOKEN="$(T3_MCP_ACCESS=full-access "$here/t3-mcp.py" login)"
revoke() {
  unset T3_MCP_TOKEN
  # 吊销本脚本签出的 t3-dispatch 令牌（只在进程环境里出现过）
  t3 auth session list 2>/dev/null | grep -B4 'client: t3-dispatch' | grep -E '^[0-9a-f-]{36}$' | while read -r id; do t3 auth session revoke "$id" >/dev/null 2>&1 || true; done
}
trap revoke EXIT
sel=$(python3 -c 'import json,sys; print(json.dumps({"threadId":sys.argv[1],"modelSelection":{"instanceId":sys.argv[2],"model":sys.argv[3],"options":[{"id":"reasoning_effort","value":sys.argv[4]}]}}))' "$tid" "$provider" "$model" "$effort")
"$here/t3-mcp.py" call t3_thread_configure "$sel" >/dev/null
got=$("$here/t3-mcp.py" call t3_thread_configure "{\"threadId\":\"$tid\"}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((o["value"] for o in d["modelSelection"].get("options",[]) if o["id"]=="reasoning_effort"),"未设置"))')
echo "reasoning_effort=$got"
[ "$got" = "$effort" ]
