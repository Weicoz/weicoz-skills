#!/usr/bin/env bash
# 用法：t3-audit.sh <worktree> [--branch <目标分支>] [--hours N] [--author <匹配串>] [--strict]
# 审计：列出该仓库所有本地分支上、近 N 小时（默认 24）内、署名含 “via DSH” 的提交，
#       凡是不在目标分支上的，报警并列出提交号与所在分支。
# 目标分支默认取 worktree 当前分支。署名匹配覆盖提交正文（含 Co-Authored-By 尾注）、
# 作者与提交者姓名邮箱，因为 DSH 派单的落款在正文尾注里，不在 %an 里。
# --strict：提交虽然落在目标分支，但同时出现在别的分支也报警；默认只在“没落在目标分支”时报警。
# 退出码：0 无异常；1 有异常；3 参数或环境错误。只读，不改仓库。
set -uo pipefail
wt="" target="" hours="${T3_AUDIT_HOURS:-24}" pattern="${T3_AUDIT_AUTHOR:-via DSH}" strict=0
while (( $# )); do
  case "$1" in
    --branch) [ $# -ge 2 ] || { echo "错误：--branch 需要分支名。" >&2; exit 3; }; target="$2"; shift 2 ;;
    --hours) [ $# -ge 2 ] || { echo "错误：--hours 需要小时数。" >&2; exit 3; }; hours="$2"; shift 2 ;;
    --author) [ $# -ge 2 ] || { echo "错误：--author 需要匹配串。" >&2; exit 3; }; pattern="$2"; shift 2 ;;
    --strict) strict=1; shift ;;
    -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "错误：未知参数 $1" >&2; exit 3 ;;
    *) [ -z "$wt" ] || { echo "错误：多余参数 $1" >&2; exit 3; }; wt="$1"; shift ;;
  esac
done
if [ -z "$wt" ] || ! [[ "$hours" =~ ^[0-9]+$ ]] || [ -z "$pattern" ]; then
  echo "用法：t3-audit.sh <worktree> [--branch <目标分支>] [--hours N] [--author <匹配串>] [--strict]" >&2
  exit 3
fi
[ -d "$wt" ] || { echo "错误：worktree 目录不存在：${wt}。" >&2; exit 3; }
git -C "$wt" rev-parse --git-dir >/dev/null 2>&1 || { echo "错误：${wt} 不是 git 仓库。" >&2; exit 3; }
wt="$(cd "$wt" && pwd)"

if [ -z "$target" ]; then
  target=$(git -C "$wt" branch --show-current 2>/dev/null) || target=""
  [ -n "$target" ] || { echo "错误：${wt} 处于 detached HEAD，用 --branch 指定目标分支。" >&2; exit 3; }
fi
git -C "$wt" rev-parse --verify --quiet "refs/heads/${target}" >/dev/null \
  || { echo "错误：没有名为 ${target} 的本地分支。" >&2; exit 3; }

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/t3-audit.XXXXXX") || { echo "错误：建临时目录失败。" >&2; exit 3; }
trap 'rm -rf "$tmpdir"' EXIT
cands="$tmpdir/cands"
: > "$cands"

# 候选提交：每个本地分支各扫一遍，正文 / 作者 / 提交者三处命中取并集
# 逐行读分支名，不靠 set -- 或 IFS 拆词（分支名虽不含空格，也不给 zsh/bash 留歧义）
git -C "$wt" for-each-ref --format='%(refname:short)' refs/heads/ > "$tmpdir/branches" || {
  echo "错误：读不到本地分支列表。" >&2; exit 3; }
while IFS= read -r b; do
  [ -n "$b" ] || continue
  git -C "$wt" log "$b" --since="${hours} hours ago" --format='%H' --grep="$pattern" >> "$cands" 2>/dev/null
  git -C "$wt" log "$b" --since="${hours} hours ago" --format='%H' --author="$pattern" >> "$cands" 2>/dev/null
  git -C "$wt" log "$b" --since="${hours} hours ago" --format='%H' --committer="$pattern" >> "$cands" 2>/dev/null
done < "$tmpdir/branches"
sort -u -o "$cands" "$cands"

total=$(grep -c . "$cands" 2>/dev/null || true)
total=${total:-0}
echo "== 审计：${wt}"
echo "== 目标分支：${target}；窗口：近 ${hours} 小时；署名匹配：“${pattern}”；模式：$([ "$strict" = 1 ] && echo 严格 || echo 默认)"
if [ "$total" -eq 0 ]; then
  echo "结果：窗口内没有署名匹配的提交。"
  exit 0
fi

bad=0
good=0
while IFS= read -r sha; do
  [ -n "$sha" ] || continue
  containing=$(git -C "$wt" branch --contains "$sha" --format='%(refname:short)' 2>/dev/null)
  on_target=0
  printf '%s\n' "$containing" | grep -qxF "$target" && on_target=1
  others=$(printf '%s\n' "$containing" | grep -vxF "$target" | grep . || true)

  alarm=0
  if [ "$on_target" -eq 0 ]; then
    alarm=1
  elif [ "$strict" = 1 ] && [ -n "$others" ]; then
    alarm=1
  fi

  if [ "$alarm" -eq 1 ]; then
    bad=$((bad + 1))
    subject=$(git -C "$wt" log -1 --format='%s' "$sha" 2>/dev/null)
    if [ "$on_target" -eq 1 ]; then
      echo "!! ${sha:0:7} 在 ${target}，但同时出现在：$(printf '%s' "$others" | tr '\n' ' ')"
    else
      listed=$(printf '%s\n' "$containing" | grep . | tr '\n' ' ')
      echo "!! ${sha:0:7} 不在 ${target}，出现在：${listed:-（无任何本地分支，可能已悬空）}"
    fi
    echo "   ${subject}"
    echo "   ${sha}"
  else
    good=$((good + 1))
  fi
done < "$cands"

echo "结果：命中 ${total} 条，落在目标分支 ${good} 条，异常 ${bad} 条。"
[ "$bad" -eq 0 ] || exit 1
exit 0
