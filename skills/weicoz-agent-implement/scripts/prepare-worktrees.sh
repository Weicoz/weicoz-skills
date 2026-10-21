#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' '用法：prepare-worktrees.sh --branch 票据分支 --base 基线分支 --ticket 票名 --repo 简称=仓库路径 [--repo 简称=仓库路径]... --log-dir 目录 [--root 目录]' \
    '默认放在各仓库根目录 .worktrees/<票名>，未被忽略时写入该仓库 .git/info/exclude；指定 --root 时放在 <root>/<票名>-<简称>。'
}
die() { printf '错误：%s\n' "$*" >&2; exit 1; }
value() { [[ $# -ge 2 && -n $2 ]] || die "$1 缺少参数值。"; }
branch= base= root= ticket= log_dir=
repos=()
while (( $# )); do
  case "$1" in
    --branch) value "$@"; branch=$2; shift 2 ;;
    --base) value "$@"; base=$2; shift 2 ;;
    --root) value "$@"; root=$2; shift 2 ;;
    --ticket) value "$@"; ticket=$2; shift 2 ;;
    --repo) value "$@"; repos+=("$2"); shift 2 ;;
    --log-dir) value "$@"; log_dir=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "未知参数：$1；用 --help 查看用法。" ;;
  esac
done
[[ -n $branch && -n $base && -n $ticket && -n $log_dir && ${#repos[@]} -gt 0 ]] || { usage >&2; die '请填写全部必需参数，至少指定一个 --repo。'; }
[[ $ticket != . && $ticket != .. && $ticket != *[![:alnum:]_.-]* ]] || die '票名仅使用字母、数字、下划线、点或连字符。'
command -v git >/dev/null 2>&1 || die '未找到 git；请先安装 Git。'
git check-ref-format --branch "$branch" >/dev/null 2>&1 || die "分支名无效：$branch"

# 相对 --root 按调用目录解析；目录在全部预检通过后才创建。
[[ -z $root || $root == /* ]] || root="$PWD/$root"
names=()
paths=()
commons=()
targets=()
# 全部仓库预检通过后才创建，避免后一个目标冲突时已改动前一个仓库。
for entry in "${repos[@]}"; do
  [[ $entry == *=* ]] || die "--repo 格式应为 简称=仓库路径：$entry"
  name=${entry%%=*}
  path=${entry#*=}
  [[ -n $name && $name != . && $name != .. && $name != *[![:alnum:]_.-]* ]] || die "仓库简称无效：$name"
  path=$(git -C "$path" rev-parse --show-toplevel 2>/dev/null) || die "仓库不可访问：$path"
  common=$(git -C "$path" rev-parse --git-common-dir)
  [[ $common == /* ]] || common="$path/$common"
  common=$(cd -- "$common" && pwd -P)
  for existing in "${commons[@]+"${commons[@]}"}"; do
    [[ $existing != "$common" ]] || die "同一仓库重复指定：$name"
  done
  for existing in "${names[@]+"${names[@]}"}"; do
    [[ $existing != "$name" ]] || die "仓库简称重复：$name"
  done
  if [[ -n $root ]]; then
    target="$root/$ticket-$name"
  else
    target="$path/.worktrees/$ticket"
  fi
  [[ ! -e $target && ! -L $target ]] || die "目标目录已存在，保留原目录：$target"
  if git -C "$path" show-ref --verify --quiet "refs/heads/$branch"; then
    die "票据分支已存在，保留原分支：$name / $branch"
  fi
  git -C "$path" rev-parse --verify --end-of-options "$base^{commit}" >/dev/null 2>&1 || die "基线不存在：$name / $base"
  names+=("$name")
  paths+=("$path")
  commons+=("$common")
  targets+=("$target")
done
mkdir -p -- "$log_dir" || die '无法创建日志目录。'
for (( i=0; i<${#names[@]}; i++ )); do
  mkdir -p -- "$(dirname -- "${targets[$i]}")" || die "无法创建 worktree 根目录：${targets[$i]}"
  if [[ -z $root ]] && ! git -C "${paths[$i]}" check-ignore -q ".worktrees/$ticket"; then
    mkdir -p -- "${commons[$i]}/info"
    printf '/.worktrees/\n' >>"${commons[$i]}/info/exclude"
  fi
done
log_dir=$(cd -- "$log_dir" && pwd -P)
status=0
summaries=()
for (( i=0; i<${#names[@]}; i++ )); do
  name=${names[$i]}
  target=${targets[$i]}
  log="$log_dir/install-$ticket-$name.txt"
  git -C "${paths[$i]}" worktree add -b "$branch" -- "$target" "$base" >"$log" 2>&1 || die "创建 worktree 失败；已建目录保留，详情：$log"
  installs=()
  if [[ -f $target/pnpm-lock.yaml ]]; then
    installs+=(pnpm)
  elif [[ -f $target/package-lock.json ]]; then
    installs+=(npm)
  fi
  [[ ! -f $target/uv.lock ]] || installs+=(uv)
  summary='跳过（无支持的锁文件）'
  for manager in "${installs[@]+"${installs[@]}"}"; do
    case "$manager" in
      pnpm) install_args=(pnpm install --frozen-lockfile) ;;
      npm) install_args=(npm ci) ;;
      uv) install_args=(uv sync --frozen) ;;
    esac
    code=0
    if command -v "$manager" >/dev/null 2>&1; then
      (cd -- "$target" && "${install_args[@]}") >>"$log" 2>&1 || code=$?
    else
      printf '错误：未找到 %s；请安装后在该 worktree 重跑锁定安装。\n' "$manager" >>"$log"
      code=127
    fi
    [[ $summary != 跳过* ]] || summary=
    summary="${summary}${summary:+; }$manager exit=$code"
    (( code == 0 )) || status=1
  done
  summaries+=("worktree=$target install=$summary log=$log")
done
printf '%s\n' "${summaries[@]}"
exit "$status"
