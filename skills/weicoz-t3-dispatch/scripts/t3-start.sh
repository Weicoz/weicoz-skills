#!/usr/bin/env bash
# 用法：t3-start.sh <worktree> <标题> <任务文件> [--provider <id>] [--model '<模型串>']
#        [--effort <等级，默认 max>] [--project-title <项目名，默认 worktree 目录名>]
# 环境变量：T3_PROVIDER、T3_MODEL、T3_EFFORT。provider 与 model 必填，取值见本目录 t3-models.sh 与 SKILL.md。
# 步骤：登记项目（已登记则跳过）→ thread start → 解析 threadId → 设 reasoning_effort → 打印 threadId。
# stdout 最后一行是 threadId。退出码：0 成功；1 起会话或设 effort 失败；3 参数或环境错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
wt="" title="" task="" ptitle=""
provider="${T3_PROVIDER:-}" model="${T3_MODEL:-}" effort="${T3_EFFORT:-max}"
while (( $# )); do
  case "$1" in
    --provider) [ $# -ge 2 ] || { echo "错误：--provider 需要 provider 实例 id。" >&2; exit 3; }; provider="$2"; shift 2 ;;
    --model) [ $# -ge 2 ] || { echo "错误：--model 需要模型串。" >&2; exit 3; }; model="$2"; shift 2 ;;
    --effort) [ $# -ge 2 ] || { echo "错误：--effort 需要等级。" >&2; exit 3; }; effort="$2"; shift 2 ;;
    --project-title) [ $# -ge 2 ] || { echo "错误：--project-title 需要项目名。" >&2; exit 3; }; ptitle="$2"; shift 2 ;;
    -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "错误：未知参数 $1" >&2; exit 3 ;;
    *) if [ -z "$wt" ]; then wt="$1"; elif [ -z "$title" ]; then title="$1"; elif [ -z "$task" ]; then task="$1"; else echo "错误：多余参数 $1" >&2; exit 3; fi; shift ;;
  esac
done
if [ -z "$wt" ] || [ -z "$title" ] || [ -z "$task" ]; then
  echo "用法：t3-start.sh <worktree> <标题> <任务文件> [--provider <id>] [--model '<模型串>']" >&2; exit 3
fi
command -v t3 >/dev/null || { echo "错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }
[ -d "$wt" ] || { echo "错误：worktree 目录不存在：$wt" >&2; exit 3; }
[ -f "$task" ] || { echo "错误：找不到任务文件 ${task}。" >&2; exit 3; }
wt="$(cd "$wt" && pwd)"
if [ -z "$provider" ] || [ -z "$model" ]; then
  cat >&2 <<'EOF'
错误：未指定 provider 与 model。
配置方式（任选其一）：
  export T3_PROVIDER=<provider 实例 id>
  export T3_MODEL='<模型串>'
  t3-start.sh <worktree> <标题> <任务文件> --provider <id> --model '<模型串>'
取值：scripts/t3-models.sh 列出本机 provider 实例与用过的模型串；DSH 默认值见 SKILL.md「派单流程」。
EOF
  exit 3
fi

# 1. 登记项目：已登记时 thread list 正常返回，跳过 add（重复 add 报 ProjectAlreadyExistsError）
if t3 --log-level none thread list --project "$wt" --json >/dev/null 2>&1; then
  echo "项目已登记：$wt" >&2
else
  added=$(t3 --log-level none project add --title "${ptitle:-$(basename "$wt")}" "$wt" 2>&1) || {
    echo "错误：登记项目失败。" >&2; printf '%s\n' "$added" | head -5 >&2; exit 1; }
  echo "已登记项目：$(printf '%s' "$added" | head -1)" >&2
fi

# 2. 起会话：提示词经 stdin 传入
if ! out=$(t3 --log-level none thread start --provider "$provider" --model "$model" \
  --title "$title" --json "$wt" - < "$task" 2>&1); then
  echo "错误：thread start 失败。" >&2; printf '%s\n' "$out" | tail -5 >&2; exit 1
fi
tid=$(printf '%s\n' "$out" | python3 -I "$here/t3-json.py" thread-id) || {
  echo "错误：解析 threadId 失败。" >&2; printf '%s\n' "$out" | tail -5 >&2; exit 1; }

# 3. 设推理等级：命令行传不了 options
if ! "$here/t3-effort.sh" "$tid" "$provider" "$model" "$effort" >&2; then
  echo "错误：线程已建（${tid}），但设置 reasoning_effort=$effort 失败。" >&2
  echo "$tid"
  exit 1
fi
echo "$tid"
