#!/usr/bin/env bash
# 用法：t3-wait.sh <threadId> [超时秒，默认 5400]
# 定时查询线程状态；离开 running 后打印状态与最新回复。
# 退出码：0 完成；1 失败或等待输入；2 超时；3 参数或环境错误。
set -uo pipefail
tid="${1:-}"; limit="${2:-5400}"; interval="${T3_WAIT_INTERVAL:-60}"
if [ -z "$tid" ]; then echo "用法：t3-wait.sh <threadId> [超时秒]" >&2; exit 3; fi
command -v t3 >/dev/null || { echo "错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }
start=$SECONDS
while (( SECONDS - start < limit )); do
  # CLI 与服务端版本不一致时会在 stdout 混入 WARN 日志，只取 JSON 行
  st=$(t3 thread show --json --messages 1 "$tid" 2>/dev/null | grep '^{' \
       | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["thread"]["status"])' 2>/dev/null)
  if [ -n "$st" ] && [ "$st" != running ]; then
    echo "STATUS=$st"
    t3 thread show --messages 1 "$tid" 2>/dev/null | grep -v -e WARN -e divergent -e 'unknown to this build' | tail -80
    case "$st" in completed|idle) exit 0;; *) exit 1;; esac
  fi
  sleep "$interval"
done
echo "STATUS=timeout（${limit} 秒）"; exit 2
