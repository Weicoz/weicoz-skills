#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法：launch-local.sh --name 票名 --prompt 文件 --workdir 目录 --out 目录
  [--add-dir 目录]... [--max-load-per-core 数] [--poll-seconds 数]
  [--max-sessions 数] [--no-wait-load] [--offline] [-- codex附加参数...]
每核负载阈值：命令行 > RD_MAX_LOAD_PER_CORE > 1.5；轮询默认20秒。
本机并发上限：命令行 > WEICOZ_MAX_LOCAL_SESSIONS > 2，按运行中 codex exec 的不同工作目录计数；0 表示不限。
USAGE
}
die() { printf '错误：%s\n' "$*" >&2; exit 1; }
value() { [[ $# -ge 2 && -n $2 ]] || die "$1 缺少参数值。"; }
positive() {
  awk -v n="$1" 'BEGIN { exit !(n ~ /^([0-9]+([.][0-9]*)?|[.][0-9]+)$/ && n > 0) }'
}

name= prompt= workdir= out=
max_load=${RD_MAX_LOAD_PER_CORE:-1.5}
poll=20
max_sessions=${WEICOZ_MAX_LOCAL_SESSIONS:-2}
wait_load=1
network=true
add_dirs=()
extra=()
while (( $# )); do
  case "$1" in
    --name) value "$@"; name=$2; shift 2 ;;
    --prompt) value "$@"; prompt=$2; shift 2 ;;
    --workdir) value "$@"; workdir=$2; shift 2 ;;
    --out) value "$@"; out=$2; shift 2 ;;
    --add-dir) value "$@"; add_dirs+=("$2"); shift 2 ;;
    --max-load-per-core) value "$@"; max_load=$2; shift 2 ;;
    --poll-seconds) value "$@"; poll=$2; shift 2 ;;
    --max-sessions) value "$@"; max_sessions=$2; shift 2 ;;
    --no-wait-load) wait_load=0; shift ;;
    --offline) network=false; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; extra=("$@"); break ;;
    *) die "未知参数：$1；用 --help 查看用法。" ;;
  esac
done
[[ -n $name && -n $prompt && -n $workdir && -n $out ]] || { usage >&2; die '请填写 --name、--prompt、--workdir、--out。'; }
[[ $name != . && $name != .. && $name != *[![:alnum:]_.-]* ]] || die '票名仅使用字母、数字、下划线、点或连字符。'
positive "$max_load" || die '每核负载阈值必须为正数。'
positive "$poll" || die '轮询秒数必须为正数。'
[[ $max_sessions =~ ^[0-9]+$ ]] || die '并发上限必须为非负整数。'
command -v codex >/dev/null 2>&1 || die '未找到 codex；请先安装 Codex CLI 并加入 PATH。'
command -v git >/dev/null 2>&1 || die '未找到 git；请先安装 Git。'
[[ -f $prompt && -r $prompt && -s $prompt ]] || die "提示词文件不存在、不可读或为空：$prompt"
prompt_text=$(cat -- "$prompt")
workdir=$(cd -- "$workdir" 2>/dev/null && pwd -P) || die "工作目录不可访问：$workdir"

writable=()
add_writable() {
  local directory=$1 existing
  for existing in "${writable[@]+"${writable[@]}"}"; do
    [[ $existing != "$directory" ]] || return 0
  done
  writable+=("$directory")
}
for directory in "$workdir" "${add_dirs[@]+"${add_dirs[@]}"}"; do
  directory=$(cd -- "$directory" 2>/dev/null && pwd -P) || die '工作目录或 --add-dir 不可访问。'
  [[ $directory == "$workdir" ]] || add_writable "$directory"
done
mkdir -p -- "$out" || die "无法创建输出目录：$out"
out=$(cd -- "$out" && pwd -P)
result="$out/result-$name.md"
log="$out/log-$name.txt"
[[ ! -e $result && ! -e $log ]] || die '结果或日志已存在；请换票名或输出目录，保留原会话证据。'

running_sessions() {
  ps -axo command= 2>/dev/null | awk '
    $0 ~ /codex/ && / exec / {
      for (i = 1; i < NF; i++) if ($i == "-C") { seen[$(i + 1)] = 1 }
    }
    END { n = 0; for (d in seen) n++; print n }'
}
if (( wait_load )); then
  case "$(uname -s)" in
    Darwin) cores=$(sysctl -n hw.ncpu) || die '无法读取 CPU 核数；请核对运行环境的 sysctl 权限。' ;;
    Linux) cores=$(nproc) || die '无法读取 CPU 核数；请核对 nproc 是否可用。' ;;
    *) die '负载准入仅支持 macOS 与 Linux。' ;;
  esac
  [[ $cores =~ ^[1-9][0-9]*$ ]] || die '无法读取 CPU 核数。'
fi
while (( wait_load || max_sessions > 0 )); do
  ready=1
  if (( max_sessions > 0 )); then
    sessions=$(running_sessions)
    printf '运行中会话 %s，上限 %s\n' "$sessions" "$max_sessions"
    (( sessions < max_sessions )) || ready=0
  fi
  if (( wait_load )); then
    case "$(uname -s)" in
      Darwin) load=$(sysctl -n vm.loadavg | awk '{print $2}') || die '无法读取1分钟负载；请核对运行环境的 sysctl 权限。' ;;
      Linux) load=$(awk '{print $1}' /proc/loadavg) || die '无法读取 /proc/loadavg；请核对运行环境。' ;;
    esac
    [[ $load =~ ^[0-9]+([.][0-9]+)?$ ]] || die '无法读取1分钟负载。'
    per_core=$(awk -v load="$load" -v cores="$cores" 'BEGIN { printf "%.3f", load / cores }')
    printf '负载 %s ÷ %s 核 = 每核 %s，阈值 %s\n' "$load" "$cores" "$per_core" "$max_load"
    awk -v load="$load" -v cores="$cores" -v limit="$max_load" 'BEGIN { exit !(load / cores < limit) }' || ready=0
  fi
  (( ready )) && break
  sleep "$poll"
done

command_args=(codex exec -s workspace-write -C "$workdir")
for directory in "${writable[@]+"${writable[@]}"}"; do
  command_args+=(--add-dir "$directory")
done
command_args+=(-c "sandbox_workspace_write.network_access=$network" -o "$result")
command_args+=("${extra[@]+"${extra[@]}"}" "$prompt_text")

child=
cleanup() {
  if [[ -n $child ]]; then
    kill -TERM -- "-$child" 2>/dev/null || true
    sleep 1
    kill -KILL -- "-$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# 子进程仅用于同时读取日志头；脚本保持前台等待，退出时回收本次进程。
set -m
"${command_args[@]}" </dev/null >"$log" 2>&1 &
child=$!
set +m
deadline=$(( $(date +%s) + 300 ))
header_seen=0
while :; do
  if awk '/^session id:[[:space:]]*[^[:space:]]/ { found=1 } END { exit !found }' "$log"; then
    awk '/^(workdir|model|sandbox|session id):/ && !seen[$1]++ { print; count++ ; if (count == 4) exit }' "$log"
    header_seen=1
    break
  fi
  kill -0 "$child" 2>/dev/null || break
  if (( $(date +%s) >= deadline )); then
    printf '错误：300秒内未出现 session id；日志：%s\n' "$log" >&2
    exit 1
  fi
  sleep 1
done
code=0
wait "$child" || code=$?
child=
if (( ! header_seen )); then
  printf '错误：codex 结束前未输出 session id；日志：%s\n' "$log" >&2
  (( code != 0 )) || code=1
fi
printf 'exit=%s result=%s log=%s\n' "$code" "$result" "$log"
exit "$code"
