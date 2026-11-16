#!/usr/bin/env bash
# 用法：t3-last.sh <threadId> [--project <路径或项目 id>] [--messages N]
# 只输出该线程最后一条 assistant 回复正文；t3 的告警日志与 JSON 残行不输出。
# --project 用于把线程 id 缩写成前缀时还原成完整 id（如 `mcp:84354ccf`）。
# 退出码：0 有正文；3 参数、线程或解析错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tid="" project="" msgs="${T3_LAST_MESSAGES:-200}"
while (( $# )); do
  case "$1" in
    --project) [ $# -ge 2 ] || { echo "错误：--project 需要路径或项目 id。" >&2; exit 3; }; project="$2"; shift 2 ;;
    --messages) [ $# -ge 2 ] || { echo "错误：--messages 需要条数。" >&2; exit 3; }; msgs="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "错误：未知参数 $1" >&2; exit 3 ;;
    *) [ -z "$tid" ] || { echo "错误：多余参数 $1" >&2; exit 3; }; tid="$1"; shift ;;
  esac
done
if [ -z "$tid" ] || ! [[ "$msgs" =~ ^[0-9]+$ ]]; then
  echo "用法：t3-last.sh <threadId> [--project <路径或项目 id>] [--messages N]" >&2; exit 3
fi
command -v t3 >/dev/null || { echo "错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }

if [ -n "$project" ]; then
  tid=$(t3 --log-level none thread list --project "$project" --json 2>/dev/null \
    | python3 -I "$here/t3-json.py" thread-id-prefix "$tid") || exit 3
fi

out=$(t3 --log-level none thread show --json --messages "$msgs" "$tid" 2>&1) || {
  echo "错误：读不到线程 ${tid}。" >&2
  printf '%s\n' "$out" | grep -v '^ *at ' | head -3 >&2
  exit 3
}
printf '%s\n' "$out" | python3 -I "$here/t3-json.py" last-assistant
