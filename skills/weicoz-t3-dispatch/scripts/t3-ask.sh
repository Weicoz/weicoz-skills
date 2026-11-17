#!/usr/bin/env bash
# 用法：t3-ask.sh <threadId> <消息文件> [超时秒，默认 5400] [--project <路径或项目 id>]
# send → wait → last 一次完成：发出消息，等到线程不再 running，打印最后一条 assistant 正文。
# `t3 thread send` 输出 Sent.（空闲线程立刻开跑）或 Queued.（忙时排到下一轮），两者都算发出成功。
# stdout：STATUS=<状态> 一行 + 回复正文。退出码同 t3-wait.sh：0 完成；1 失败或等待输入；2 超时；3 参数或环境错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=t3-lib.sh
. "$here/t3-lib.sh"
tid="" file="" limit="" project=""
while (( $# )); do
  case "$1" in
    --project) [ $# -ge 2 ] || { echo "错误：--project 需要路径或项目 id。" >&2; exit 3; }; project="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "错误：未知参数 $1" >&2; exit 3 ;;
    *) if [ -z "$tid" ]; then tid="$1"; elif [ -z "$file" ]; then file="$1"; elif [ -z "$limit" ]; then limit="$1"; else echo "错误：多余参数 $1" >&2; exit 3; fi; shift ;;
  esac
done
if [ -z "$tid" ] || [ -z "$file" ] || ! [[ "${limit:-1}" =~ ^[0-9]+$ ]]; then
  echo "用法：t3-ask.sh <threadId> <消息文件> [超时秒] [--project <路径或项目 id>]" >&2; exit 3
fi
[ -f "$file" ] || { echo "错误：找不到消息文件 ${file}。" >&2; exit 3; }
command -v t3 >/dev/null || { echo "错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }

sent=$(t3_call thread send "$tid" - < "$file") || true
case "$sent" in
  *Sent.*|*Queued.*) echo "发送：（$(printf '%s' "$sent" | head -1)）" >&2 ;;
  *) echo "错误：发送失败。" >&2; printf '%s\n' "$sent" | head -5 >&2; exit 3 ;;
esac

"$here/t3-wait.sh" "$tid" ${limit:+"$limit"} ${project:+--project "$project"} || exit $?
"$here/t3-last.sh" "$tid" ${project:+--project "$project"}
