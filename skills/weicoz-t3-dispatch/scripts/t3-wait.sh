#!/usr/bin/env bash
# 用法：t3-wait.sh <threadId> [超时秒，默认 5400] [--project <路径或项目 id>]
# 判据：`t3 thread list --project` 里该线程状态不再是 running 即结束并打印 STATUS。
# 只看状态：回复正文用 t3-last.sh，发消息并等一轮用 t3-ask.sh。
# 退出码：0 完成；1 失败或等待输入；2 超时；3 参数或环境错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=t3-lib.sh
. "$here/t3-lib.sh"
tid="" limit="" project=""
while (( $# )); do
  case "$1" in
    --project) [ $# -ge 2 ] || { echo "ERROR 错误：--project 需要路径或项目 id。" >&2; exit 3; }; project="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "ERROR 错误：未知参数 $1" >&2; exit 3 ;;
    *) if [ -z "$tid" ]; then tid="$1"; elif [ -z "$limit" ]; then limit="$1"; else echo "ERROR 错误：多余参数 $1" >&2; exit 3; fi; shift ;;
  esac
done
limit="${limit:-${T3_WAIT_TIMEOUT:-5400}}"
if [ -z "$tid" ] || ! [[ "$limit" =~ ^[0-9]+$ ]]; then
  echo "ERROR 用法：t3-wait.sh <threadId> [超时秒] [--project <路径或项目 id>]" >&2; exit 3
fi
command -v t3 >/dev/null || { echo "ERROR 错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }

# 未给 --project 时按线程自身所属项目查询（thread list 的 --project 同样接受项目 id）
if [ -z "$project" ]; then
  project=$(t3_call thread show --json --messages 1 "$tid" \
    | python3 -I "$here/t3-json.py" project-id) \
    || { echo "ERROR 错误：读不到线程 $tid 所属项目，用 --project <路径> 指定。" >&2; exit 3; }
fi

interval="${T3_WAIT_INTERVAL:-60}"
start=$SECONDS
while (( SECONDS - start < limit )); do
  # t3-lib.sh 过滤 migration divergent 警告块（不过滤真实报错）；t3-json.py 再按 JSON 行兜底
  st=$(t3_call thread list --project "$project" --json \
    | python3 -I "$here/t3-json.py" list-status "$tid") \
    || { echo "ERROR 错误：查询线程状态失败，确认 --project 指向该线程所属项目。" >&2; exit 3; }
  if [ -n "$st" ] && [ "$st" != running ]; then
    echo "DONE STATUS=$st"
    case "$st" in completed|idle) exit 0 ;; *) exit 1 ;; esac
  fi
  left=$(( limit - (SECONDS - start) ))
  sleep $(( left < interval ? (left > 0 ? left : 1) : interval ))
done
echo "TIMEOUT STATUS=timeout（${limit} 秒）"
exit 2
