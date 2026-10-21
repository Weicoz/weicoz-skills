#!/usr/bin/env bash
# 把本仓库的 weicoz-* Skill 软链到各 harness 的 skills 目录，并检查漂移。
#
# 用法：
#   ./scripts/sync-skills.sh                    # 只检查，有漂移则 exit 1
#   ./scripts/sync-skills.sh --apply            # 修复：重指漂移的软链、补齐在用的挂载
#   ./scripts/sync-skills.sh --apply --skill weicoz-feishu-task-tracker
#   ./scripts/sync-skills.sh --quiet            # 干净时不输出
#
# 行为约定：
#   - 只管理 weicoz-* 条目，不碰其他 Skill。
#   - --apply 只重指已漂移的软链，并把「已被任一 harness 挂载」的 Skill 补齐到其余 harness。
#   - 任何 harness 都没挂过的 Skill（例如被新版取代的旧目录）不会被自动挂上；
#     确需挂载时用 --skill <name> 显式点名。
#   - 实体目录（非软链）不自动处理，只报告，交人工确认。
#
# 环境变量：
#   WEICOZ_SKILL_HARNESS_DIRS  覆盖 harness 目录列表（冒号分隔）

set -uo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd -P)"
root="$repo/skills"

mode="check"
only_skill=""
quiet=0
fail=0
fixed=0

while (( $# > 0 )); do
  case "$1" in
    --apply) mode="apply" ;;
    --check) mode="check" ;;
    --quiet) quiet=1 ;;
    --skill)
      shift
      [[ $# -gt 0 ]] || { printf '--skill 缺少参数\n' >&2; exit 2; }
      only_skill="$1"
      ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      printf '未知参数: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -n "${WEICOZ_SKILL_HARNESS_DIRS:-}" ]]; then
  IFS=':' read -r -a harness_dirs <<< "${WEICOZ_SKILL_HARNESS_DIRS}"
else
  harness_dirs=(
    "$HOME/.agents/skills"
    "$HOME/.dsh/skills"
    "$HOME/.codex/skills"
    "$HOME/.claude/skills"
    "$HOME/.kimi-code/skills"
    "$HOME/.gemini/config/skills"
  )
fi

# 解析软链链到最终绝对路径（纯 bash，兼容 macOS bash 3.2，无 realpath）
resolve() {
  local p="$1"
  while [[ -L "$p" ]]; do
    local t
    t="$(readlink "$p")"
    case "$t" in
      /*) p="$t" ;;
      *)  p="$(dirname "$p")/$t" ;;
    esac
  done
  printf '%s\n' "$p"
}

expected_target() { printf '%s/skills/%s\n' "$repo" "$1"; }

say() { (( quiet )) || printf '%s\n' "$*"; }

existing_harnesses=()
for h in "${harness_dirs[@]}"; do
  [[ -d "$h" ]] && existing_harnesses+=("$h")
done

if (( ${#existing_harnesses[@]} == 0 )); then
  say '未发现任何 harness skills 目录，跳过软链检查。'
  say '可用 WEICOZ_SKILL_HARNESS_DIRS 指定，例如：'
  say '  WEICOZ_SKILL_HARNESS_DIRS="$HOME/.agents/skills" ./scripts/sync-skills.sh'
  exit 0
fi

skills=()
while IFS= read -r -d '' d; do
  name="$(basename "$d")"
  if [[ -n "$only_skill" && "$name" != "$only_skill" ]]; then
    continue
  fi
  skills+=("$name")
done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -name 'weicoz-*' -print0 | sort -z)

if (( ${#skills[@]} == 0 )); then
  printf '未找到 skill（检查 --skill 参数）\n' >&2
  exit 2
fi

# 预扫描：哪些 Skill 已被至少一个 harness 挂载（= 在用）
in_use_file="$(mktemp)"
trap 'rm -f "$in_use_file"' EXIT
for h in "${existing_harnesses[@]}"; do
  for entry in "$h"/weicoz-*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    basename "$entry" >> "$in_use_file"
  done
done
sort -u -o "$in_use_file" "$in_use_file"

is_in_use() { grep -qxF "$1" "$in_use_file"; }

mount_count=0

for name in "${skills[@]}"; do
  want="$(expected_target "$name")"
  mounted_here=0

  for h in "${existing_harnesses[@]}"; do
    entry="$h/$name"

    if [[ -L "$entry" ]]; then
      got="$(resolve "$entry")"
      if [[ "$got" == "$want" ]]; then
        mounted_here=1
        continue
      fi
      if [[ "$mode" == "apply" ]]; then
        if rm -f "$entry" && ln -s "$want" "$entry"; then
          say "重指 $name -> $want"
          fixed=$((fixed + 1))
          mounted_here=1
        fi
        continue
      fi
      printf '软链漂移: %s\n  指向 %s\n  应为 %s\n' "$entry" "$got" "$want" >&2
      fail=1
      mounted_here=1
      continue
    fi

    if [[ -e "$entry" ]]; then
      printf '实体目录（不自动处理，请手工确认）: %s\n' "$entry" >&2
      fail=1
      mounted_here=1
      continue
    fi

    # 未挂载：只有「在用」的 Skill 或显式点名的 Skill 才自动补
    if [[ -n "$only_skill" ]] || is_in_use "$name"; then
      if [[ "$mode" == "apply" ]]; then
        if ln -s "$want" "$entry"; then
          say "新增挂载 $name -> $entry"
          fixed=$((fixed + 1))
          mounted_here=1
        fi
        continue
      fi
      printf '未挂载: %s\n' "$entry" >&2
      fail=1
    fi
  done

  (( mounted_here )) && mount_count=$((mount_count + 1))
done

# 反向检查：harness 里有 weicoz-* 但本仓库已无同名目录
for h in "${existing_harnesses[@]}"; do
  for entry in "$h"/weicoz-*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    name="$(basename "$entry")"
    if [[ -n "$only_skill" && "$name" != "$only_skill" ]]; then
      continue
    fi
    if [[ ! -d "$root/$name" ]]; then
      printf '孤立挂载（本仓库无此 skill）: %s\n' "$entry" >&2
      fail=1
    fi
  done
done

# 孤儿提示：本仓库有、但任何 harness 都没挂
for name in "${skills[@]}"; do
  if ! is_in_use "$name"; then
    say "提示：$name 未被任何 harness 挂载（要挂载用 --skill $name --apply）"
  fi
done

if [[ "$mode" == "apply" ]]; then
  if (( fixed > 0 )); then
    printf 'SYNC OK — 修复 %s 处，%s 个 skill 已对齐 %s 个 harness 目录\n' \
      "$fixed" "${#skills[@]}" "${#existing_harnesses[@]}"
  else
    printf 'SYNC OK — 无漂移，%s 个 skill 已对齐 %s 个 harness 目录\n' \
      "${#skills[@]}" "${#existing_harnesses[@]}"
  fi
  (( fail == 0 ))
  exit $?
fi

if (( fail == 0 )); then
  say "LINK OK — ${#skills[@]} 个 skill 在 ${#existing_harnesses[@]} 个 harness 目录指向本仓库"
  exit 0
fi

printf '\n修复：./scripts/sync-skills.sh --apply\n' >&2
exit 1
