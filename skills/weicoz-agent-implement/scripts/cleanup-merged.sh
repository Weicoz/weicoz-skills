#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' '用法：cleanup-merged.sh --repo 仓库路径 --into 目标分支 --prefix 名称前缀 [--prefix 名称前缀]... [--dry-run]' \
    '移除 <仓库>/.worktrees/ 下名称以指定前缀开头、工作区干净、HEAD 已合入目标分支且无 codex 会话占用的 worktree；分支保留。' \
    '前缀必填：只清理本次任务创建的 worktree，不碰同仓库其他会话的 worktree。汇总按实际可用空间差报告释放量（du 会重复计数 APFS 克隆）。'
}
die() { printf '错误：%s\n' "$*" >&2; exit 1; }
value() { [[ $# -ge 2 && -n $2 ]] || die "$1 缺少参数值。"; }
repo= into= dry_run=0
prefixes=()
while (( $# )); do
  case "$1" in
    --repo) value "$@"; repo=$2; shift 2 ;;
    --into) value "$@"; into=$2; shift 2 ;;
    --prefix) value "$@"; prefixes+=("$2"); shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "未知参数：$1；用 --help 查看用法。" ;;
  esac
done
[[ -n $repo && -n $into && ${#prefixes[@]} -gt 0 ]] || { usage >&2; die '请填写 --repo、--into 与至少一个 --prefix。'; }
repo=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || die "仓库不可访问：$repo"
git -C "$repo" rev-parse --verify --end-of-options "$into^{commit}" >/dev/null 2>&1 || die "目标分支不存在：$into"

free_kb() { df -Pk -- "$repo" | awk 'NR == 2 { print $4 }'; }
in_use() {
  ps -axo command= 2>/dev/null | awk -v dir="$1" '$0 ~ /codex/ && / exec / { for (i = 1; i < NF; i++) if ($i == "-C" && index($(i + 1), dir) == 1) found = 1 } END { exit !found }'
}
before=$(free_kb)
removed=0 kept=0
while IFS= read -r path; do
  [[ $path == "$repo/.worktrees/"* ]] || continue
  name=${path#"$repo/.worktrees/"}
  [[ $name != */* ]] || continue
  match=0
  for prefix in "${prefixes[@]}"; do [[ $name == "$prefix"* ]] && match=1; done
  (( match )) || continue
  reason=
  if [[ -n $(git -C "$path" status --porcelain 2>/dev/null) ]]; then reason='有未提交改动'
  elif ! git -C "$repo" merge-base --is-ancestor "$(git -C "$path" rev-parse HEAD)" "$into"; then reason="未合入 $into"
  elif in_use "$path"; then reason='有 codex 会话占用'
  fi
  if [[ -n $reason ]]; then
    printf '保留 %s：%s\n' "$name" "$reason"; kept=$((kept + 1)); continue
  fi
  if (( dry_run )); then
    printf '将移除 %s（%s）\n' "$name" "$(git -C "$path" rev-parse --abbrev-ref HEAD)"
  else
    git -C "$repo" worktree remove -- "$path" && printf '已移除 %s\n' "$name"
  fi
  removed=$((removed + 1))
done < <(git -C "$repo" worktree list --porcelain | awk '/^worktree /{ sub(/^worktree /, ""); print }')
(( dry_run )) || git -C "$repo" worktree prune
after=$(free_kb)
printf '汇总：%s %s 个，保留 %s 个，实际释放约 %s MB\n' "$( (( dry_run )) && echo 计划移除 || echo 已移除)" "$removed" "$kept" "$(( (after - before) / 1024 ))"
