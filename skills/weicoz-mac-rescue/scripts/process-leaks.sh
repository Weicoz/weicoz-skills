#!/usr/bin/env bash
# 只读：找进程泄漏、孤儿进程、僵尸进程，以及暴露在命令行里的凭据。
#
# 看四件事：
#   1. 同一类命令行出现十几次 → MCP / 子进程泄漏
#   2. 某个父进程挂了十几个孩子 → 该守护进程在反复拉起
#   3. 父进程为 1 的用户进程 / <defunct> → 孤儿与僵尸
#   4. 密钥写进 argv → 本机任何进程都能看到
#
# 用法：bash scripts/process-leaks.sh
set -uo pipefail

line() { printf '\n== %s ==\n' "$1"; }

line "进程总数 / 线程总数"
ps -Axo pid 2>/dev/null | tail -n +2 | wc -l | awk '{print "进程: "$1}'
top -l 1 -n 0 2>/dev/null | grep -E '^Processes' | sed 's/^/线程: /'

line "同一类命令行出现最多的（>3 次基本就是泄漏）"
ps -Ao command= 2>/dev/null | awk '
  /(^|\/)(node|python[0-9.]*|bun|deno|ruby|java)( |$)/ {
    n=$0
    sub(/^(.*\/)?(node|python[0-9.]*|bun|deno|ruby|java) /, "", n)
    split(n, p, " "); k=p[1]; sub(/.*\//, "", k)
    if (k != "") print k
  }' | sort | uniq -c | sort -rn | head -18

line "可执行文件名重复度"
ps -Ao comm= 2>/dev/null | sed 's|.*/||' | sort | uniq -c | sort -rn | head -12

line "子进程最多的父进程（>10 说明在反复拉起）"
ps -Ao ppid= 2>/dev/null | awk 'NF' | sort | uniq -c | sort -rn | head -10 | while read -r cnt ppid; do
  [ "$cnt" -lt 6 ] && continue
  cmd=$(ps -o command= -p "$ppid" 2>/dev/null | cut -c1-90)
  printf '%4s 个孩子  PID %-7s %s\n' "$cnt" "$ppid" "${cmd:-<父进程已退出>}"
done

line "孤儿：父进程为 1 的当前用户进程（主程序退出后遗留）"
me=$(id -un)
ps -Ao pid=,ppid=,user=,etime=,rss=,command= 2>/dev/null | \
  awk -v me="$me" '$2==1 && $3==me {printf "%7s %10s %6.0fMB %s\n",$1,$4,$5/1024,substr($0,index($0,$6))}' | \
  head -15 | cut -c1-130

line "僵尸进程（<defunct>：已退出但父进程没回收）"
defunct=$(ps -Ao stat= 2>/dev/null | grep -c '^Z')
printf '数量: %s\n' "$defunct"
if [ "$defunct" -gt 0 ]; then
  ps -Ao pid=,ppid=,command= 2>/dev/null | awk '$3 ~ /<defunct>/ {print "  PID "$1" 父进程 "$2" "$3}' | head -8
  printf '长期不消失说明父进程不处理 SIGCHLD，去看父进程而不是杀僵尸本身。\n'
fi

line "命令行里疑似凭据（已打码；本机任何进程都能读到 argv）"
ps -Ao pid=,command= 2>/dev/null \
  | awk '{n=$0; sub(/^[0-9]+[ ]+/,"",n); split(n,p," "); b=p[1]; sub(/.*\//,"",b);
          if (b=="grep"||b=="sed"||b=="awk"||b=="rg"||b=="bash"||b=="sh") next; print}' \
  | grep -E -- '--(api-key|apikey|token|password|secret)|ghp_|github_pat_|sk-[A-Za-z0-9_-]{16}|xox[baprs]-' \
  | sed -E 's/(ghp_|github_pat_|sk-|xox[baprs]-)[A-Za-z0-9_-]+/\1<REDACTED>/g; s/(--(api-key|apikey|token|password|secret))[= ]+[^ ]+/\1 <REDACTED>/g' \
  | head -8 | cut -c1-140

line "处理建议"
printf '先确认来源与 etime，再决定是否 TERM。\n'
printf '有的会话正在编译或跑任务时不要批量杀 node / rustc / cargo。\n'
printf '杀完要回头收敛各 harness 的 MCP 配置，否则下个会话继续漏。\n'
printf '凭据出现在命令行里，应改为环境变量或凭据文件，并轮换该密钥。\n'
