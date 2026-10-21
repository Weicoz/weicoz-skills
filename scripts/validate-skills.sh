#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
root="$repo/skills"
fail=0

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

if (( fail == 0 )); then
  printf 'VALIDATE OK — %s 个 skill 通过
' "$(find "$root" -mindepth 1 -maxdepth 1 -type d -name 'weicoz-*' | wc -l | tr -d ' ')"
fi

(( fail == 0 ))