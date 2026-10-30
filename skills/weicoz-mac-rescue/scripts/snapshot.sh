#!/usr/bin/env bash
# 只读：输出一次性 macOS 资源快照。不修改任何系统状态。
#
# 用法：bash scripts/snapshot.sh
set -uo pipefail

line() { printf '\n== %s ==\n' "$1"; }

line "采集时间"
date '+%Y-%m-%d %H:%M:%S'

line "磁盘"
df -h /System/Volumes/Data 2>/dev/null | awk 'NR==1 || NR==2'

line "swap"
sysctl -n vm.swapusage 2>/dev/null
swapfiles=$(ls /System/Volumes/VM/swapfile* 2>/dev/null | wc -l | tr -d ' ')
printf 'swapfile 个数: %s（每个约 1 GB，直接占盘）\n' "$swapfiles"
vm_used=$(du -sh /System/Volumes/VM 2>/dev/null | cut -f1)
[ -n "${vm_used:-}" ] && printf '/System/Volumes/VM 实占: %s\n' "$vm_used"

line "内存"
vm_stat 2>/dev/null | grep -E 'Pages free|Pages wired down|occupied by compressor|Pages stored in compressor'
printf '物理内存: %s GB\n' "$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.1f", $1/1073741824}')"

line "负载"
printf '核数: %s\n' "$(sysctl -n hw.ncpu 2>/dev/null)"
uptime

line "进程 / 线程 / CPU 汇总"
top -l 1 -n 0 -stats pid 2>/dev/null | grep -E '^Processes|^Load Avg|^CPU usage|^PhysMem'

line "CPU 排行（pcpu 为滚动均值，与活动监视器可能不同步）"
ps -Ao pid,pcpu,rss,etime,comm -r 2>/dev/null | head -11 | \
  awk 'NR==1{print "   PID    CPU%     RSS  运行时长  命令"} NR>1{printf "%6s %6s%% %6.0fMB %10s  %s\n",$1,$2,$3/1024,$4,$5}'

line "按应用聚合内存"
ps -Ao rss=,command= 2>/dev/null | awk '
{
  n=$0; sub(/^[0-9]+[ ]+/, "", n)
  if (match(n, /\/Applications\/[^\/]+\.app/))            a=substr(n,RSTART+14,RLENGTH-18)
  else if (match(n, /\/Library\/Containers\/[^\/]+\//))    a=substr(n,RSTART+20,RLENGTH-21)
  else { split(n,p," "); a=p[1]; sub(/.*\//,"",a) }
  s[a]+=$1; c[a]++
}
END { for (k in s) printf "%8.0fMB %4d个进程  %s\n", s[k]/1024, c[k], k }
' | sort -rn | head -15

line "前 10 名 RSS 合计"
ps -Ao rss= 2>/dev/null | sort -rn | head -10 | awk '{s+=$1} END{printf "%.1f GB\n", s/1048576}'

printf '\n判读阈值见 SKILL.md「第一步：取证」表格。\n'
