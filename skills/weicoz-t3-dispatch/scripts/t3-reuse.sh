#!/usr/bin/env bash
# 用法：t3-reuse.sh --project <路径或项目 id> [--keyword <词>[,<词>…]] [--model '<模型串>']
# 列出项目里的线程，按“可续用”条件打分，末行给出建议：`续用 <threadId>` 或 `新开`。
# 条件（全满足才可续用）：状态不是 running；距上次活动 ≤ T3_CACHE_MIN 分钟（默认 60）；
#   条目数 ≤ T3_MAX_ITEMS（默认 150，越长每轮越贵）；给了 --model 时模型串一致；给了 --keyword 时标题含任一词。
# 同一工作目录才可续用：线程的 cwd 固定，换 worktree 请直接新开（用项目路径区分）。
# 退出码：0 有结论；3 参数或环境错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=t3-lib.sh
. "$here/t3-lib.sh"
project="" kw="" model=""
while (( $# )); do
  case "$1" in
    --project) project="${2:-}"; shift 2 ;;
    --keyword) kw="${2:-}"; shift 2 ;;
    --model) model="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "ERROR 未知参数 $1" >&2; exit 3 ;;
  esac
done
[ -n "$project" ] || { echo "ERROR 需要 --project <路径或项目 id>" >&2; exit 3; }
command -v t3 >/dev/null || { echo "ERROR 找不到 t3 命令" >&2; exit 3; }
t3_call thread list --project "$project" --json | KW="$kw" MODEL="$model" CACHE="${T3_CACHE_MIN:-60}" MAXI="${T3_MAX_ITEMS:-150}" python3 -I -c '
import json, os, sys, datetime
data = None
for line in sys.stdin:
    s = line.strip()
    if s.startswith(("[", "{")):
        try: data = json.loads(s)
        except json.JSONDecodeError: pass
if data is None:
    sys.exit("ERROR 读不到线程列表")
rows = data if isinstance(data, list) else data.get("threads", [])
kws = [k for k in os.environ["KW"].split(",") if k]
model = os.environ["MODEL"]; cache = int(os.environ["CACHE"]); maxi = int(os.environ["MAXI"])
now = datetime.datetime.now(datetime.timezone.utc)
best = None
print("%-40s %-10s %6s %5s  %s" % ("threadId", "状态", "空闲分", "条目", "标题"))
for t in rows:
    upd = datetime.datetime.fromisoformat(t["updatedAt"].replace("Z", "+00:00"))
    idle = int((now - upd).total_seconds() / 60)
    why = []
    if t["status"] == "running": why.append("运行中")
    if idle > cache: why.append("缓存可能过期")
    if t.get("itemCount", 0) > maxi: why.append("上下文过长")
    if model and t.get("model") != model: why.append("模型不同")
    if kws and not any(k in t["title"] for k in kws): why.append("标题无关")
    mark = "可续用" if not why else "不可：" + "、".join(why)
    print("%-40s %-10s %6d %5d  %s  [%s]" % (t["threadId"], t["status"], idle, t.get("itemCount", 0), t["title"], mark))
    if not why and (best is None or idle < best[0]): best = (idle, t["threadId"])
print("续用 " + best[1] if best else "新开")
'
