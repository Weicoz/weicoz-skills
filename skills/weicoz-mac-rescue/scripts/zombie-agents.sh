#!/usr/bin/env bash
# 只读：找出「程序已被删除但启动项仍在」的 launchd 任务（僵尸自启动项）。
#
# 判定：launchctl list 里 last exit code 非 0，且 plist 的 ProgramArguments
# 指向的文件已不存在。程序还在的项一律不打印，避免刷屏。
#
# 用法：bash scripts/zombie-agents.sh
set -uo pipefail

uid=$(id -u)
search_dirs=(
  "$HOME/Library/LaunchAgents"
  "/Library/LaunchAgents"
  "/Library/LaunchDaemons"
  "/System/Library/LaunchAgents"
  "/System/Library/LaunchDaemons"
)

find_plist() {
  local label=$1 d
  for d in "${search_dirs[@]}"; do
    [ -f "$d/$label.plist" ] && { printf '%s\n' "$d/$label.plist"; return 0; }
  done
  return 1
}

# 取 ProgramArguments 里以绝对路径或 ~ 开头的参数，用于判断文件是否还在
prog_paths() {
  local plist=$1
  plutil -convert json -o - "$plist" 2>/dev/null |
    python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for a in (d.get("ProgramArguments") or [])[:2]:
    if isinstance(a,str) and (a.startswith("/") or a.startswith("~")):
        print(a)
' 2>/dev/null
}

printf '扫描 launchd 任务...\n'
printf '说明：退出码 -9 是被信号回收，macOS 上按需 XPC 服务常态如此，不算异常。\n\n'

scanned=0
found=0
header=0

while IFS=$'\t' read -r status label; do
  case "$status" in "0"|"-"|"") continue ;; esac
  scanned=$((scanned+1))

  plist=$(find_plist "$label") || continue

  missing=""
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    p="${p/#\~/$HOME}"
    if [ ! -e "$p" ]; then missing="$p"; break; fi
  done < <(prog_paths "$plist")

  [ -z "$missing" ] && continue

  if [ "$header" -eq 0 ]; then
    printf '%-44s %6s %8s %-26s %s\n' "LABEL" "退出码" "runs" "PLIST" "缺失的可执行文件"
    printf '%s\n' "---------------------------------------------------------------------------------------------------"
    header=1
  fi

  runs=$(launchctl print "gui/$uid/$label" 2>/dev/null | awk -F'= ' '/runs = /{print $2; exit}')
  [ -n "${runs:-}" ] || runs=$(launchctl print "system/$label" 2>/dev/null | awk -F'= ' '/runs = /{print $2; exit}')
  keepalive=$(plutil -p "$plist" 2>/dev/null | grep -c '"KeepAlive"')

  printf '%-44s %6s %8s %-26s %s\n' "$label" "$status" "${runs:-?}" "$(basename "$plist")" "$missing"
  if [ "${keepalive:-0}" -gt 0 ]; then
    printf '   KeepAlive 已启用 → 会按节流间隔（默认 10 秒）无限重试\n'
  else
    printf '   KeepAlive 未启用 → 只在登录或手动加载时重试，优先级较低\n'
  fi
  found=$((found+1))
done < <(launchctl list 2>/dev/null | awk 'NR>1 {print $2"\t"$3}')

printf '\n排查 %s 个非 0 退出项。\n' "$scanned"
if [ "$found" -eq 0 ]; then
  printf '未发现僵尸任务。\n'
else
  printf '发现 %s 个候选。按 SKILL.md「僵尸 launchd 任务」处置：\n' "$found"
  printf '  1. launchctl bootout "gui/%s/<label>"\n' "$uid"
  printf '  2. 把 plist 移到 $HOME/.local/state/mac-rescue-disabled/，不要删除\n'
  printf '  3. 验收：对比 StandardErrorPath 日志字节数，隔 20 秒两次取样相等才算停住\n'
fi
