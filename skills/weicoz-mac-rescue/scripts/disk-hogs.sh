#!/usr/bin/env bash
# 只读：定向统计磁盘大户。带超时保护，避免在快满的盘上做全盘扫描把机器拖死。
#
# 用法：bash scripts/disk-hogs.sh [超时秒数，默认 20]
set -uo pipefail

TIMEOUT=${1:-20}

line() { printf '\n== %s ==\n' "$1"; }

# 便携超时：后台跑 + 到点 TERM
run_timeout() {
  local t=$1; shift
  "$@" & local p=$!
  ( sleep "$t"; kill -TERM "$p" 2>/dev/null ) & local w=$!
  wait "$p" 2>/dev/null
  kill -TERM "$w" 2>/dev/null
  wait "$w" 2>/dev/null
  return 0
}

line "总容量与可用"
df -h /System/Volumes/Data 2>/dev/null | awk 'NR==1 || NR==2'

line "本机快照（本地 Time Machine 快照会占用可用空间）"
run_timeout 10 tmutil listlocalsnapshots / 2>/dev/null | head -10 || printf '查询超时或无快照\n'

line "常见大户目录（各自独立超时 ${TIMEOUT}s）"
candidates=(
  "$HOME/Library/Containers"
  "$HOME/Library/Application Support"
  "$HOME/Library/Caches"
  "$HOME/Library/Developer"
  "$HOME/Library/Logs"
  "$HOME/Downloads"
  "$HOME/.cache"
  "$HOME/.npm"
  "$HOME/.local/state"
)
for d in "${candidates[@]}"; do
  [ -d "$d" ] || continue
  size=$(run_timeout "$TIMEOUT" du -xsh "$d" 2>/dev/null | cut -f1)
  printf '%-52s %s\n' "${d/#$HOME/\~}" "${size:-<超时跳过>}"
done

line "容器与虚拟盘（单项最大）"
for f in \
  "$HOME/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw" \
  "$HOME/.docker/desktop/data/Docker.raw"
do
  [ -e "$f" ] && printf '%-52s 逻辑大小 %s\n' "${f/#$HOME/\~}" "$(ls -lh "$f" 2>/dev/null | awk '{print $5}')"
done

line "下一步"
printf '对最大的那一项再做单层细分，不要一次扫全盘：\n'
printf '  du -xsh "<目录>"/*/ 2>/dev/null | sort -rh | head -10\n'
printf '在快满的盘上优先分批做，必要时放后台。\n'
