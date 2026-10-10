#!/usr/bin/env bash
# jev-ultrafast 环境体检。只读探测；--fix 时按 ego → Chrome → Edge → … 解析并拉起浏览器。
# 执行层默认一律用**用户自己的 profile（带登录态）**：在跑的就直接用，没跑的正常启动它，
# 开关没开就自动打开它（会重启它一次）；无登录态的独立 profile 只有 JEV_ALLOW_FRESH=1 才用。
#   bash doctor.sh                    # 体检（报告执行层会选哪个，不启动任何东西、不改任何文件）
#   bash doctor.sh --fix              # 缺什么起什么（浏览器 → daemon → inspector）
#   bash doctor.sh --fix-browser edge # 给指定浏览器打开"用户级远程调试"（会重启它，登录态保留）
#   bash doctor.sh --fix-ego          # 等价于 --fix-browser ego
#   bash doctor.sh --net              # 额外打一次真实网络，验证两个 key 活着
# 退出码：0 = 全绿（含 --fix 后修好），1 = 仍有阻塞项。
set -uo pipefail

PROJ="${JEV_PROJ:-$HOME/File/git/jev-ultrafast}"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="${JEV_BROWSER_LIB:-$SELF_DIR/lib/browser.sh}"
CDP_PORT=9222
INSPECT_PORT=8766
SOCK="$HOME/.config/browser-harness/runtime/bu-default.sock"
BU_LOG="$HOME/.config/browser-harness/tmp/bu-default.log"
FIX=0
FIX_BROWSER=""
NET=0
for a in "$@"; do
  case "$a" in
    --fix) FIX=1 ;;
    --fix-ego) FIX_BROWSER="ego" ;;
    --fix-browser) FIX_BROWSER="__next__" ;;
    --net) NET=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) if [ "$FIX_BROWSER" = "__next__" ]; then FIX_BROWSER="$a"; else echo "未知参数: $a" >&2; exit 2; fi ;;
  esac
done
if [ "$FIX_BROWSER" = "__next__" ]; then
  echo "--fix-browser 需要一个品牌名：ego | chrome | edge | brave | chromium | vivaldi | arc | opera" >&2
  exit 2
fi

ok()   { printf '  ✅ %s\n' "$1"; }
bad()  { printf '  ❌ %s\n' "$1"; [ -n "${2:-}" ] && printf '     → %s\n' "$2"; }
warn() { printf '  ⚠️  %s\n' "$1"; }
hint() { printf '     → %s\n' "$1"; }

# 变量名统一用 ${var} 形式：后面紧跟全角标点时 bash 会把标点字节吃进变量名
# （踩过：$ego_port；→ "ego_port；: unbound variable"）。

port_alive() {
  python3 -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('127.0.0.1',int(sys.argv[1])))==0 else 1)" "$1" 2>/dev/null
}

fail_count=0
WS=""          # 最终选定的 CDP 端点
WS_KIND=""     # ego | chrome

echo "jev-ultrafast 体检（项目: ${PROJ}）"

# ---------- 1. 项目本体 ----------
echo
echo "[1/6] 项目与运行时"
if [ -d "$PROJ" ]; then
  ok "项目目录存在"
else
  bad "项目目录不存在" "git clone https://github.com/browser-use/jev-ultrafast ${PROJ}"
  echo; echo "结论：缺项目本体，后续检查跳过。"; exit 1
fi
if [ -x "$PROJ/.venv/bin/python" ]; then
  ok "虚拟环境 $( "$PROJ/.venv/bin/python" -c 'import sys;print("Python %d.%d.%d"%sys.version_info[:3])' 2>/dev/null )"
else
  bad "缺 .venv" "cd ${PROJ} && uv sync"
  fail_count=$((fail_count+1))
fi
[ -f "$PROJ/.env" ] && ok ".env 存在" || { bad "缺 .env" "cd ${PROJ} && cp .env.example .env，再填底座与文本层"; fail_count=$((fail_count+1)); }
[ -x "$PROJ/run-local.sh" ] && ok "run-local.sh 可执行" || warn "run-local.sh 缺失或不可执行（--url 路径会不可用）"

# ---------- 2. 执行层：浏览器解析链 ----------
echo
echo "[2/6] 执行层：浏览器解析链（ego → Chrome → Edge → Brave → Chromium → …）"
echo "  策略：一律用用户自己的 profile（登录态在）；无登录态的独立 profile 只在 JEV_ALLOW_FRESH=1 时使用"
echo "  可调：JEV_AUTO_ENABLE=0 禁止自动开调试开关；JEV_ALLOW_RESTART=1 允许为开开关而重启浏览器"

if [ ! -f "$LIB" ]; then
  bad "找不到浏览器解析库 ${LIB}" "确认 skill 的 bin/lib/browser.sh 完整，或用 JEV_BROWSER_LIB=<路径> 指过去"
  fail_count=$((fail_count+1))
else
  # shellcheck disable=SC1090
  . "$LIB"

  printf '  %-9s %-6s %-8s %-22s %s\n' 品牌 安装 调试开关 当前档位 端点
  for b in "${JEV_BRANDS[@]}"; do
    b_app="$(jev_browser_app "$b")"
    [ -d "$b_app" ] || continue
    if jev_browser_toggle_on "$b"; then b_toggle="已开"; else b_toggle="未开"; fi
    case "$(jev_tier_for_brand "$b")" in
      real)    b_tier="real（在跑）" ;;
      toggle)  b_tier="toggle（可启动）" ;;
      enable)  b_tier="enable（能自动开开关）" ;;
      restart) b_tier="restart（需退出重开）" ;;
      fresh)   b_tier="fresh（无登录态）" ;;
      *)       b_tier="—" ;;
    esac
    b_ws="$(jev_ws_brand "$b" 2>/dev/null || true)"
    if [ -n "${b_ws}" ]; then
      b_ep="✅ 活着（端口 $(jev_ws_port "$b_ws")）"
    elif [ -f "$(jev_browser_profile "$b")/DevToolsActivePort" ]; then
      b_ep="⚠️ 端点文件过期（进程没带 CDP）"
    else
      b_ep="—"
    fi
    printf '  %-9s %-6s %-8s %-22s %s\n' "$b" "yes" "$b_toggle" "$b_tier" "$b_ep"
  done
  if [ -n "$(jev_legacy_9222)" ]; then
    printf '  %-9s %-6s %-8s %-22s %s\n' "9222" "yes" "—" "—" "✅ 老式自动化端点在线（无登录态）"
  fi

  echo
  if [ "$FIX" = 1 ]; then
    if jev_resolve_browser; then
      WS="$JEV_WS"; WS_KIND="$JEV_BRAND"
      ok "执行层：$(jev_browser_summary)"
      [ "$JEV_MODE" = "fresh" ] && hint "这一档没有登录态；要登录态：bash $0 --fix-browser ${JEV_BRAND}（会重启它一次）"    else
      bad "没有任何可用浏览器（ego / Chrome / Edge … 都没解析出 CDP 端点）" "装任意一个 Chromium 系浏览器后重跑"
      fail_count=$((fail_count+1))
    fi
  else
    if JEV_DRY_RUN=1 jev_resolve_browser; then
      ok "执行层（只报告，没启动任何东西）：$(jev_browser_summary)"
      case "${JEV_MODE}" in
        real)    hint "它已经在跑且带 CDP 端点，直接用（登录态在）" ;;
        toggle)  hint "真启动：bash $0 --fix（run-local.sh 也会自己拉起）" ;;
        enable)  hint "真启动：bash $0 --fix —— 会先给它打开用户级远程调试开关（一次性），登录态保留" ;;
        fresh)   hint "这一档没有登录态（JEV_ALLOW_FRESH=1 的代价）；要登录态：bash $0 --fix-browser ${JEV_BRAND}" ;;
      esac
    else
      bad "没有可用的执行层（没装任何 Chromium 系浏览器？）" "装 ego lite / Chrome / Edge 任意一个即可"
      fail_count=$((fail_count+1))
    fi
  fi
fi

# --- --fix-browser <brand>：给该浏览器的真实 profile 打开用户级远程调试 ---
# 通用实现：Chromium 系共用 <user-data-dir>/Local State 与 devtools.remote_debugging 首选项，
# ego 只是其中一个品牌。必须先退出该浏览器——Chromium 退出时会用内存里的旧设置覆盖回写。
if [ -n "$FIX_BROWSER" ]; then
  echo
  echo "  … --fix-browser ${FIX_BROWSER}：打开它的用户级远程调试（会重启它一次，登录态保留）"
  b_app="$(jev_browser_app "$FIX_BROWSER")"
  b_prof="$(jev_browser_profile "$FIX_BROWSER")"
  b_name="$(basename "${b_app%.app}" 2>/dev/null || echo "$FIX_BROWSER")"
  if [ ! -d "$b_app" ]; then
    bad "没装 ${FIX_BROWSER}（${b_app}）" ""
    fail_count=$((fail_count+1))
  elif [ ! -f "$b_prof/Local State" ]; then
    bad "找不到 ${b_prof}/Local State" "先手动正常启动一次 ${b_name}，让它生成 profile"
    fail_count=$((fail_count+1))
  else
    b_ws="$(jev_ws_brand "$FIX_BROWSER" 2>/dev/null || true)"
    if [ -n "${b_ws}" ] && jev_browser_toggle_on "$FIX_BROWSER"; then
      WS="$b_ws"; WS_KIND="$FIX_BROWSER"; JEV_MODE="real"; JEV_LOGIN_STATE="yes"
      ok "${b_name} 本来就在带 CDP 跑（端口 $(jev_ws_port "$b_ws")），不用重启"
    else
      rc=0
      jev_toggle_enable "$FIX_BROWSER" 1 || rc=$?    # 允许退出它一次：这是用户显式点名的修复动作
      if [ "${rc}" != "0" ]; then
        bad "写调试开关失败（退出码 ${rc}）" "确认 ${b_prof}/Local State 可写、${b_name} 已完全退出"
        fail_count=$((fail_count+1))
      else
        b_ws="$(jev_launch_toggle "$FIX_BROWSER" 2>/dev/null || true)"
        if [ -n "${b_ws}" ]; then
          WS="$b_ws"; WS_KIND="$FIX_BROWSER"; JEV_MODE="toggle"; JEV_LOGIN_STATE="yes"
          ok "${b_name} 已带 CDP 启动（端口 $(jev_ws_port "$b_ws")）"
          hint "它若弹 \"Allow remote debugging?\"，点一次 Allow（同一次启动内会记住）"
        else
          bad "${b_name} 起来了但没出可用的 DevToolsActivePort" "看它是否弹了别的窗口；或再手动启动一次 ${b_name}"
          fail_count=$((fail_count+1))
        fi
      fi
    fi
  fi
fi

# ---------- 3. browser-harness daemon ----------
echo
echo "[3/6] 执行层：browser-harness daemon"
daemon_pids="$(pgrep -f "browser_harness.daemon" 2>/dev/null | tr '\n' ' ' || true)"
daemon_ws=""
if [ -n "${daemon_pids}" ]; then
  daemon_ws="$(ps eww -p "$(pgrep -f browser_harness.daemon | head -1)" 2>/dev/null | grep -o 'BU_CDP_WS=[^ ]*' | head -1 | cut -d= -f2- || true)"
  if [ -n "${daemon_ws}" ]; then
    ok "daemon 在跑（pid ${daemon_pids}），绑定 ${daemon_ws}"
  else
    warn "daemon 在跑（pid ${daemon_pids}），但读不到它的 BU_CDP_WS（可能是自动发现模式）"
  fi
fi
stale_daemon=0
if [ -n "${daemon_ws}" ] && [ -n "${WS}" ] && [ "${daemon_ws}" != "${WS}" ]; then
  stale_daemon=1
  bad "daemon 绑的还是旧端点（ego 重启后端口会变）" "pkill -f browser_harness.daemon，再重跑本脚本"
  fail_count=$((fail_count+1))
fi
if grep -qs "listening on" "$BU_LOG" 2>/dev/null && [ -S "$SOCK" ]; then
  ok "daemon socket 就绪：${SOCK}"
elif [ -n "${daemon_pids}" ]; then
  warn "daemon 在跑但 socket 没就绪（首次连接时可能还在握手中）"
else
  warn "daemon 没在跑（跑 agent 时会自动拉起：BU_CDP_WS 会被子进程继承）"
fi
if [ "$FIX" = 1 ] && [ -n "${WS}" ] && { [ -z "${daemon_pids}" ] || [ "$stale_daemon" = 1 ]; }; then
  echo "  … --fix：用 BU_CDP_WS 启动 daemon（端点类型：${WS_KIND}）"
  [ -n "${daemon_pids}" ] && { pkill -f "browser_harness.daemon" 2>/dev/null; sleep 2; }
  BU_CDP_WS="$WS" nohup "$PROJ/.venv/bin/python" -m browser_harness.daemon > /tmp/bh-daemon.log 2>&1 &
  for _ in $(seq 1 10); do
    sleep 2
    grep -qs "listening on" "$BU_LOG" 2>/dev/null && [ -S "$SOCK" ] && break
  done
  if grep -qs "listening on" "$BU_LOG" 2>/dev/null && [ -S "$SOCK" ]; then
    ok "daemon 已就绪（${WS_KIND}）"
    [ "$stale_daemon" = 1 ] && fail_count=$((fail_count-1))
  else
    warn "起不来，看 $( [ -f /tmp/bh-daemon.log ] && echo /tmp/bh-daemon.log || echo "$BU_LOG" ) 最后几行"
  fi
fi

# ---------- 4. 决策层 key ----------
echo
echo "[4/6] 决策层：OpenRouter Jev"
key_val=""
if [ -f "$HOME/.zsh_secrets" ]; then
  key_val="$(sed -n 's/^export OPENROUTER_API_KEY="\(.*\)"$/\1/p' "$HOME/.zsh_secrets" | head -1)"
  key_len="${#key_val}"
  if [ -z "${key_val}" ]; then
    bad "~/.zsh_secrets 里没有 OPENROUTER_API_KEY" "加一行 export OPENROUTER_API_KEY=\"sk-or-v1…\""
    fail_count=$((fail_count+1))
  elif printf '%s' "$key_val" | grep -qE '你的|占位|placeholder'; then
    bad "OPENROUTER_API_KEY 还是占位符（长度 ${key_len}）" "填真实值"
    fail_count=$((fail_count+1))
  else
    ok "OPENROUTER_API_KEY 已配置（长度 ${key_len}，不打印内容）"
  fi
else
  bad "找不到 ~/.zsh_secrets" "run-local.sh 靠它导出 OPENROUTER_API_KEY"
  fail_count=$((fail_count+1))
fi
if [ "$NET" = 1 ] && [ -n "${key_val}" ]; then
  code="$(curl -q -s -o /dev/null -w '%{http_code}' --max-time 20 \
    -H "Authorization: Bearer ${key_val}" https://openrouter.ai/api/v1/models 2>/dev/null || echo 000)"
  case "$code" in
    200) ok "OpenRouter key 真实可用（HTTP 200）" ;;
    401) bad "OpenRouter 返回 401" "key 过期或写错"
         fail_count=$((fail_count+1)) ;;
    000) warn "OpenRouter 请求超时/网络不通（HTTP ${code}）" ;;
    *)   warn "OpenRouter 返回 HTTP ${code}" ;;
  esac
fi

# ---------- 5. 文本层配置 ----------
echo
echo "[5/6] 文本层（打字用的小模型）"
if [ -f "$PROJ/.env" ]; then
  for k in TEXT_MODEL TEXT_MODEL_BASE_URL TEXT_MODEL_API_KEY; do
    v="$(sed -n "s/^${k}=//p" "$PROJ/.env" | head -1)"
    if [ -z "${v}" ]; then
      warn ".env 缺 ${k}"
    elif [ "$k" = "TEXT_MODEL_API_KEY" ]; then
      ok "${k} 已配置（长度 ${#v}）"
    else
      ok "${k}=${v}"
    fi
  done
  grep -q 'TYPESAFE_BASE_URL=https://openrouter.ai' "$PROJ/.env" \
    && ok "TYPESAFE_BASE_URL 指向 OpenRouter" \
    || warn ".env 的 TYPESAFE_BASE_URL 不是 https://openrouter.ai/api"
  grep -q '^TYPESAFE_API_KEY=\${' "$PROJ/.env" \
    && warn '.env 里 TYPESAFE_API_KEY=${OPENROUTER_API_KEY} 是字面量，不会自动展开——必须靠 run-local.sh 注入真实环境变量' \
    || true
else
  bad "没有 .env，文本层无从配置" ""
  fail_count=$((fail_count+1))
fi
if [ "$NET" = 1 ] && [ -f "$PROJ/.env" ]; then
  base="$(sed -n 's/^TEXT_MODEL_BASE_URL=//p' "$PROJ/.env" | head -1)"
  tk="$(sed -n 's/^TEXT_MODEL_API_KEY=//p' "$PROJ/.env" | head -1)"
  tm="$(sed -n 's/^TEXT_MODEL=//p' "$PROJ/.env" | head -1)"
  if [ -n "${base}" ] && [ -n "${tk}" ]; then
    code="$(curl -q -s -o /dev/null -w '%{http_code}' --max-time 60 \
      -H "Authorization: Bearer ${tk}" -H 'Content-Type: application/json' \
      -d "{\"model\":\"${tm}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}" \
      "${base}/chat/completions" 2>/dev/null || echo 000)"
    case "$code" in
      200) ok "文本层真实可用（HTTP 200，model=${tm}）" ;;
      401) bad "文本层返回 401" "网关令牌失效，换一把"
           fail_count=$((fail_count+1)) ;;
      503) warn "文本层 503：网关没给这个模型分配渠道" ;;
      *)   warn "文本层返回 HTTP ${code}" ;;
    esac
  fi
fi

# ---------- 6. inspector ----------
echo
echo "[6/6] inspector"
if curl -q -s -o /dev/null --max-time 3 "http://127.0.0.1:${INSPECT_PORT}/" 2>/dev/null; then
  ok "inspector 在跑：http://127.0.0.1:${INSPECT_PORT}"
else
  warn "inspector 没在跑（不是阻塞项；要演示时再起）"
  hint "cd ${PROJ} && nohup ./run-local.sh > /tmp/jev-inspector.log 2>&1 &"
  if [ "$FIX" = 1 ]; then
    echo "  … --fix：启动 inspector"
    ( cd "$PROJ" && nohup ./run-local.sh > /tmp/jev-inspector.log 2>&1 & )
    for _ in $(seq 1 15); do
      sleep 2
      curl -q -s -o /dev/null --max-time 3 "http://127.0.0.1:${INSPECT_PORT}/" 2>/dev/null && break
    done
    curl -q -s -o /dev/null --max-time 3 "http://127.0.0.1:${INSPECT_PORT}/" 2>/dev/null \
      && ok "inspector 已拉起" \
      || warn "起不来，看 /tmp/jev-inspector.log"
  fi
fi

echo
if [ -n "${WS}" ]; then
  echo "选定的执行层：${WS_KIND} ｜ 档位 ${JEV_MODE:-?} ｜ 登录态 ${JEV_LOGIN_STATE:-unknown}"
  if [ "${JEV_LOGIN_STATE:-no}" = "no" ] && [ -z "${FIX_BROWSER}" ] && [ "${WS_KIND}" != "(env)" ]; then
    echo "  （要登录态：bash $0 --fix-browser ${WS_KIND} —— 给它真实 profile 打开用户级远程调试）"
  fi
fi
if [ "$fail_count" -le 0 ]; then
  echo "结论：阻塞项全绿。下一步跑端到端冒烟（唯一能说\"能用\"的证据）："
  echo "  bash ${SELF_DIR}/smoke.sh"
  exit 0
else
  echo "结论：仍有阻塞项（见上面的 ❌）。先按 → 后面的命令修，或整体跑 bash $0 --fix"
  exit 1
fi
