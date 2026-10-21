#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd -P)"
root="$repo/skills"
fail=0
check_links=1

while (( $# > 0 )); do
  case "$1" in
    --no-links) check_links=0 ;;
    -h|--help)
      printf '用法: %s [--no-links]\n  --no-links  跳过 harness 软链指向校验（只查仓库内容）\n' "$(basename "$0")"
      exit 0
      ;;
    *)
      printf '未知参数: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

while IFS= read -r -d '' dir; do
  name="$(basename "$dir")"
  skill="$dir/SKILL.md"
  if [[ ! -f "$skill" ]]; then
    printf '缺少 SKILL.md: %s\n' "$name" >&2
    fail=1
    continue
  fi
  front_name="$(awk 'BEGIN{in_front=0} /^---$/{in_front=!in_front; next} in_front && /^name:[[:space:]]*/{sub(/^name:[[:space:]]*/, ""); print; exit}' "$skill")"
  if [[ "$front_name" != "$name" ]]; then
    printf 'name 不匹配: %s -> %s\n' "$name" "${front_name:-<empty>}" >&2
    fail=1
  fi
  front_version="$(awk 'BEGIN{in_front=0} /^---$/{in_front=!in_front; next} in_front && /^version:[[:space:]]*/{sub(/^version:[[:space:]]*/, ""); print; exit}' "$skill")"
  if [[ -z "$front_version" ]]; then
    printf '缺少 version: %s\n' "$name" >&2
    fail=1
  elif [[ ! "$front_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'version 格式错误（须为 X.Y.Z）: %s -> %s\n' "$name" "$front_version" >&2
    fail=1
  elif ! grep -qF "skills/$name/" "$repo/README.md" 2>/dev/null; then
    printf 'README 未收录: %s\n' "$name" >&2
    fail=1
  fi
  if rg -n -I -- '-----BEGIN .*PRIVATE KEY-----|\b(sk-|ghp_|github_pat_|xox[baprs]-|AIza|AKIA)[A-Za-z0-9_-]{16,}' "$dir" >/dev/null; then
    printf '疑似硬编码凭据: %s\n' "$name" >&2
    fail=1
  fi
done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -name 'weicoz-*' -print0 | sort -z)

if find "$root" -type f \( -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' \) -print -quit | grep -q .; then
  echo '发现不应进入仓库的私密文件' >&2
  fail=1
fi

# 软链指向校验：各 harness 目录里的 weicoz-* 必须指向本仓库，而不是历史备份库。
# 未发现任何 harness 目录时（例如 CI 或新克隆），sync-skills.sh 自行跳过，不影响结果。
if (( check_links )) && [[ -x "$repo/scripts/sync-skills.sh" ]]; then
  link_out="$("$repo/scripts/sync-skills.sh" --check 2>&1)" || {
    printf '\n%s\n' "$link_out" >&2
    printf '软链校验未通过。修复：./scripts/sync-skills.sh --apply\n' >&2
    fail=1
  }
fi

if (( fail == 0 )); then
  printf 'VALIDATE OK — %s 个 skill 通过\n' "$(find "$root" -mindepth 1 -maxdepth 1 -type d -name 'weicoz-*' | wc -l | tr -d ' ')"
fi

(( fail == 0 ))