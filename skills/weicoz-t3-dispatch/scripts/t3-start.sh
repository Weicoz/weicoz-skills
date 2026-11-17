#!/usr/bin/env bash
# 用法：t3-start.sh <worktree> <标题> <任务文件> [--provider <id>] [--model '<模型串>']
#        [--effort <等级，默认 max>] [--project-title <项目名，默认 worktree 目录名>] [--dry-run]
# 环境变量：T3_PROVIDER、T3_MODEL、T3_EFFORT。provider 与 model 必填，取值见本目录 t3-models.sh 与 SKILL.md。
# 步骤：拼分支守卫 → 登记项目（已登记则跳过）→ thread start → 解析 threadId → 设 reasoning_effort → 打印 threadId。
# 分支守卫：把 `git -C <worktree> branch --show-current` 的结果拼成固定开头，与任务文件合并到临时文件再派，不改原任务文件。
# --dry-run：只打印拼接后的任务内容，不登记项目、不起会话。
# stdout：倒数第二行是 threadId，末行是收尾提示（下一步要挂的 t3-wait.sh 命令）。
# 退出码：0 成功；1 起会话或设 effort 失败；3 参数或环境错误。
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=t3-lib.sh
. "$here/t3-lib.sh"

# 给要打印的命令串加安全引号：含空白或 shell 特殊字符时加引号，路径带空格也粘得回来。
# 不用 set -- 拆词，避免 zsh/bash 把含空格的路径拆成多个参数。
shq() {
  local s=$1
  case "$s" in
    *[!A-Za-z0-9/._,+@%:=-]*) : ;;
    *) printf '%s' "$s"; return ;;
  esac
  if [ "${s#*\'}" = "$s" ]; then printf "'%s'" "$s"; return; fi
  printf '"%s"' "$(printf '%s' "$s" | sed 's/[\\"$`]/\\&/g')"
}
wt="" title="" task="" ptitle="" dry=0
provider="${T3_PROVIDER:-}" model="${T3_MODEL:-}" effort="${T3_EFFORT:-max}"
while (( $# )); do
  case "$1" in
    --provider) [ $# -ge 2 ] || { echo "错误：--provider 需要 provider 实例 id。" >&2; exit 3; }; provider="$2"; shift 2 ;;
    --model) [ $# -ge 2 ] || { echo "错误：--model 需要模型串。" >&2; exit 3; }; model="$2"; shift 2 ;;
    --effort) [ $# -ge 2 ] || { echo "错误：--effort 需要等级。" >&2; exit 3; }; effort="$2"; shift 2 ;;
    --project-title) [ $# -ge 2 ] || { echo "错误：--project-title 需要项目名。" >&2; exit 3; }; ptitle="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "错误：未知参数 $1" >&2; exit 3 ;;
    *) if [ -z "$wt" ]; then wt="$1"; elif [ -z "$title" ]; then title="$1"; elif [ -z "$task" ]; then task="$1"; else echo "错误：多余参数 $1" >&2; exit 3; fi; shift ;;
  esac
done
if [ -z "$wt" ] || [ -z "$title" ] || [ -z "$task" ]; then
  echo "用法：t3-start.sh <worktree> <标题> <任务文件> [--provider <id>] [--model '<模型串>'] [--dry-run]" >&2; exit 3
fi
[ -d "$wt" ] || { echo "错误：worktree 目录不存在：$wt" >&2; exit 3; }
[ -f "$task" ] || { echo "错误：找不到任务文件 ${task}。" >&2; exit 3; }
wt="$(cd "$wt" && pwd)"

# 0. 取当前分支拼分支守卫：分支必须在场，否则守卫无从校验，直接拒派
branch=$(git -C "$wt" branch --show-current 2>/dev/null) \
  || { echo "错误：$wt 不是 git worktree，无法取分支名。" >&2; exit 3; }
if [ -z "$branch" ]; then
  echo "错误：$wt 处于 detached HEAD，取不到分支名。先切到任务分支再派单。" >&2; exit 3
fi

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/t3-start.XXXXXX") || { echo "错误：建临时目录失败。" >&2; exit 3; }
trap 'rm -rf "$tmpdir"' EXIT
guard="$tmpdir/guard.md"
merged="$tmpdir/task.md"
cat > "$guard" <<EOF
## 分支守卫（派单脚本自动附加，勿删）

开工先 \`git branch --show-current\`，必须等于 \`$branch\`，不等就停下报告。
所有提交只落在该分支。
\`git add\` 只加具体文件，不用 \`-A\`。

---

EOF
cat "$guard" "$task" > "$merged" || { echo "错误：拼接任务文件失败。" >&2; exit 3; }

if [ "$dry" = 1 ]; then
  echo "分支：$branch" >&2
  echo "合并后任务文件（临时）：$merged" >&2
  echo "--- 以下为将派出的完整提示词 ---" >&2
  cat "$merged"
  exit 0
fi

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
command -v t3 >/dev/null || { echo "错误：找不到 t3 命令，请先安装 T3 Code CLI。" >&2; exit 3; }

# 1. 登记项目：已登记时 thread list 正常返回，跳过 add（重复 add 报 ProjectAlreadyExistsError）
if t3_call_quiet thread list --project "$wt" --json >/dev/null; then
  echo "项目已登记：$wt" >&2
else
  added=$(t3_call project add --title "${ptitle:-$(basename "$wt")}" "$wt") || {
    echo "错误：登记项目失败。" >&2; exit 1; }
  echo "已登记项目：$(printf '%s' "$added" | head -1)" >&2
fi

# 2. 起会话：提示词经 stdin 传入（用拼好守卫的临时文件）
if ! out=$(t3_call thread start --provider "$provider" --model "$model" \
  --title "$title" --json "$wt" - < "$merged"); then
  echo "错误：thread start 失败。" >&2; exit 1
fi
tid=$(printf '%s\n' "$out" | python3 -I "$here/t3-json.py" thread-id) || {
  echo "错误：解析 threadId 失败。" >&2; printf '%s\n' "$out" | tail -5 >&2; exit 1; }
echo "已派 ${tid}（分支守卫：${branch}）" >&2

# 3. 设推理等级：命令行传不了 options
if ! "$here/t3-effort.sh" "$tid" "$provider" "$model" "$effort" >&2; then
  echo "错误：线程已建（${tid}），但设置 reasoning_effort=$effort 失败。" >&2
  echo "$tid"
  exit 1
fi
echo "$tid"
# 收尾提示：末行给可直接照抄的下一步命令，threadId 在上一行
printf '下一步马上执行：%s %s --project %s（后台运行；完成后用 t3-last.sh 读结果并验收，不得只发任务不监测）\n' \
  "$(shq "$here/t3-wait.sh")" "$tid" "$(shq "$wt")"
