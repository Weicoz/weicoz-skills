#!/usr/bin/env bash
# jev-ultrafast 环境体检。只读探测；--fix 时按顺序拉起浏览器 → daemon → inspector。
#   bash doctor.sh            # 体检
#   bash doctor.sh --fix      # 缺什么起什么（不会动正在运行的 ego）
#   bash doctor.sh --fix-ego  # 给 ego lite 打开"用户级远程调试"（会重启 ego，登录态保留）
#   bash doctor.sh --net      # 额外打一次真实网络，验证两个 key 活着
# 退出码：0 = 全绿（含 --fix 后修好），1 = 仍有阻塞项。
set -uo pipefail

PROJ="${JEV_PROJ:-$HOME/File/git/jev-ultrafast}"
EGO_APP="/Applications/ego lite.app"
EGO_PROFILE="${EGO_PROFILE:-$HOME/Library/Application Support/Citro Labs/ego lite}"
EGO_DP="$EGO_PROFILE/DevToolsActivePort"
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_PROFILE="$HOME/.cache/jev-chrome-profile"
CDP_PORT=9222
INSPECT_PORT=8766
SOCK="$HOME/.config/browser-harness/runtime/bu-default.sock"
BU_LOG="$HOME/.config/browser-harness/tmp/bu-default.log"
FIX=0
FIX_EGO=0
NET=0
for a in "$@"; do
  case "$a" in
    --fix) FIX=1 ;;
    --fix-ego) FIX_EGO=1 ;;
    --net) NET=1 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

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

# ---------- 2. 执行层：ego 优先，Chrome 兜底 ----------
echo
echo "[2/6] 执行层：浏览器与 CDP 端点"

# --- ego lite（默认，真实 profile，带登录态）---
ego_enabled=0
if [ -f "$EGO_PROFILE/Local State" ]; then
  ego_enabled="$(python3 - "$EGO_PROFILE/Local State" <<'PY' 2>/dev/null
import json,sys
try:
    d=json.load(open(sys.argv[1]))
except Exception:
    print(0); raise SystemExit
v=(d.get("devtools") or {}).get("remote_debugging") or {}
print(1 if v.get("user-enabled") else 0)
PY
)"
fi

if [ -d "$EGO_APP" ]; then
  ok "ego lite 已安装（${EGO_APP}）"
else
  warn "没装 ego lite（可选：装了就用它，登录态最省心）"
fi

ego_ws=""
if [ "$ego_enabled" = 1 ]; then
  ok "ego 用户级远程调试开关：已打开（devtools.remote_debugging.user-enabled）"
  if [ -f "$EGO_DP" ]; then
    ego_port="$(head -1 "$EGO_DP" 2>/dev/null | tr -d '[:space:]')"
    ego_path="$(sed -n 2p "$EGO_DP" 2>/dev/null | tr -d '[:space:]')"
    if [ -n "${ego_port}" ] && [ -n "${ego_path}" ] && port_alive "${ego_port}"; then
      ego_ws="ws://127.0.0.1:${ego_port}${ego_path}"
      ok "ego 正在跑且 CDP 已就绪（端口 ${ego_port}）"
      http_code="$(curl -q -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:${ego_port}/json/version" 2>/dev/null || echo 000)"
      if [ "${http_code}" = "200" ]; then
        ok "ego 带 HTTP 发现接口（--remote-debugging-port 模式）"
      else
        warn "ego 走的是用户级调试模式（HTTP ${http_code}）：没有 /json/version，只能读 DevToolsActivePort"
        hint "第一次连它会弹 \"Allow remote debugging?\" —— 点一次 Allow（同一次 ego 启动内会记住）"
      fi
    else
      bad "ego 的 DevToolsActivePort 过期或端口不通" "ego 没在跑：open -a \"ego lite\""
      fail_count=$((fail_count+1))
    fi
  else
    bad "ego 开着调试开关但没有 DevToolsActivePort" "open -a \"ego lite\" 启动它；启动后文件才会出现"
    fail_count=$((fail_count+1))
  fi
else
  if [ -d "$EGO_APP" ]; then
    warn "ego 的用户级远程调试开关没打开（当前是普通启动，外界拿不到 CDP）"
    hint "一次性打开（会重启 ego，登录态保留）：bash $0 --fix-ego"
  fi
fi

# --- 兜底：9222 上的自动化 Chrome ---
chrome_ws=""
version_json="$(curl -q -s --max-time 3 "http://127.0.0.1:${CDP_PORT}/json/version" 2>/dev/null || true)"
if [ -n "$version_json" ]; then
  chrome_ws="$(printf '%s' "$version_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["webSocketDebuggerUrl"])' 2>/dev/null || true)"
  product="$(printf '%s' "$version_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Browser","?"))' 2>/dev/null || true)"
  ok "兜底浏览器在线：${CDP_PORT} 上的 ${product}（克隆 profile，无登录态）"
fi

if [ -n "${ego_ws}" ]; then
  WS="$ego_ws"; WS_KIND="ego"
elif [ -n "${chrome_ws}" ]; then
  WS="$chrome_ws"; WS_KIND="chrome"
fi

if [ -z "${WS}" ]; then
  bad "没有任何可用 CDP 端点" "ego 不可用、9222 上也没有自动化 Chrome"
  fail_count=$((fail_count+1))
  if [ "$FIX" = 1 ]; then
    echo "  … --fix：启动兜底 Chrome（真正的推荐路线是 --fix-ego）"
    nohup "$CHROME_APP" --user-data-dir="$CHROME_PROFILE" --remote-debugging-port="$CDP_PORT" --no-first-run --no-default-browser-check about:blank >/dev/null 2>&1 &
    for _ in $(seq 1 15); do
      sleep 2
      version_json="$(curl -q -s --max-time 3 "http://127.0.0.1:${CDP_PORT}/json/version" 2>/dev/null || true)"
      [ -n "$version_json" ] && break
    done
    if [ -n "$version_json" ]; then
      chrome_ws="$(printf '%s' "$version_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["webSocketDebuggerUrl"])' 2>/dev/null || true)"
      WS="$chrome_ws"; WS_KIND="chrome"
      ok "已拉起兜底 Chrome（${CDP_PORT}）"
      fail_count=$((fail_count-1))
    else
      warn "等了 30 秒仍未起来，看 Chrome 是否弹了窗口在等你"
    fi
  fi
fi

# --- --fix-ego：打开 ego 的用户级调试开关（会重启 ego）---
if [ "$FIX_EGO" = 1 ]; then
  echo
  echo "  … --fix-ego：给 ego lite 打开用户级远程调试"
  if [ ! -f "$EGO_PROFILE/Local State" ]; then
    bad "找不到 ${EGO_PROFILE}/Local State" "先手动启动一次 ego lite，让它生成 profile"
  else
    running="$(pgrep -f "ego lite.app/Contents/MacOS/ego lite" | tr '\n' ' ' || true)"
    if [ -n "${running}" ]; then
      echo "    先退出 ego（pid ${running}）——Chrome 退出时会重写 Local State，不退出写进去会被覆盖"
      osascript -e 'tell application "ego lite" to quit' >/dev/null 2>&1 || true
      sleep 3
      pgrep -f "ego lite.app/Contents/MacOS/ego lite" >/dev/null 2>&1 && { pkill -TERM -f "ego lite.app/Contents/MacOS/ego lite"; sleep 4; }
    fi
    cp "$EGO_PROFILE/Local State" "/tmp/Local State.bak-$(date +%Y%m%d-%H%M%S)"
    python3 - "$EGO_PROFILE/Local State" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p))
d.setdefault("devtools",{})["remote_debugging"]={"user-enabled":True,"allowed":True}
json.dump(d,open(p,"w"))
PY
    echo "    已写入 devtools.remote_debugging.user-enabled=true（旧文件备份在 /tmp）"
    open -a "ego lite"
    for _ in $(seq 1 20); do
      sleep 2
      [ -f "$EGO_DP" ] && port_alive "$(head -1 "$EGO_DP" | tr -d '[:space:]')" && break
    done
    if [ -f "$EGO_DP" ] && port_alive "$(head -1 "$EGO_DP" | tr -d '[:space:]')"; then
      WS="ws://127.0.0.1:$(head -1 "$EGO_DP" | tr -d '[:space:]')$(sed -n 2p "$EGO_DP" | tr -d '[:space:]')"
      WS_KIND="ego"
      ok "ego 已带 CDP 启动；点一次 Allow 授权后即可用"
    else
      warn "ego 起来了但没出 DevToolsActivePort，看 ego 是否弹了别的窗口"
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
  echo "选定的执行层：${WS_KIND}（$( [ "$WS_KIND" = ego ] && echo "真实 profile，带登录态" || echo "克隆 profile，无登录态" )）"
fi
if [ "$fail_count" -le 0 ]; then
  echo "结论：阻塞项全绿。下一步跑端到端冒烟（唯一能说\"能用\"的证据）："
  echo "  bash $(cd "$(dirname "$0")" && pwd)/smoke.sh"
  exit 0
else
  echo "结论：仍有阻塞项（见上面的 ❌）。先按 → 后面的命令修，或整体跑 bash $0 --fix"
  [ "$FIX_EGO" = 0 ] && [ "$ego_enabled" = 0 ] && [ -d "$EGO_APP" ] && echo "  （要默认用 ego：bash $0 --fix-ego）"
  exit 1
fi
