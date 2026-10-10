#!/usr/bin/env bash
# 浏览器解析库（被 run-local.sh 与 doctor.sh 共用；只定义函数，source 时无副作用）。
#
# 目标：ego 优先，没有 ego 就退到任意 Chromium 系浏览器（Chrome → Edge → Brave →
# Chromium → Vivaldi → Arc → Opera …），最后才是 9222 上的老式自动化端点。
#
# 三档可用性（每档都尽量"不打扰用户已在用的浏览器"）：
#   1. real   —— 该浏览器真实 profile 已带 CDP 端点（用户级远程调试开关打开 + 进程在跑）
#                → 登录态、cookie、插件都在，agent 动作落在用户窗口的后台标签页
#   2. toggle —— 真实 profile 的用户级开关已打开但进程没跑（或没写端点）
#                → 正常启动它，它自己就会写 DevToolsActivePort，仍是 real profile = 登录态
#   3. fresh  —— 开关没开 / 启不动 → 用独立 profile 拉起一个专门给 agent 用的实例
#                → 能用，但没有登录态（脚本会明确提示怎么升级到 real）
#
# 环境变量：
#   JEV_BROWSER=ego|chrome|edge|brave|chromium|vivaldi|arc|opera|comet|dia|cdp9222|auto
#       指定品牌（强制定向，失败即报错，不再往下退）；auto/未设 = 按优先级自动解析
#   JEV_PROFILE_ROOT=$HOME/.cache/jev-browser   fresh 模式的独立 profile 根目录
#   JEV_LAUNCH_TIMEOUT=25   等待浏览器写出 DevToolsActivePort 的秒数
#   JEV_DRY_RUN=1           只报告会选谁，不启动任何东西（doctor.sh 默认用）
#   BU_CDP_WS=ws://…        直接给定端点，跳过全部解析（最高优先级）
#
# 解析结果放在这几个全局变量里：
#   JEV_WS          选中的 CDP WebSocket 端点
#   JEV_BRAND       品牌键（ego/chrome/edge/…/cdp9222）
#   JEV_MODE        real | toggle | fresh | forced | env | dry
#   JEV_LOGIN_STATE yes | no
#   JEV_APP         命中的 app 路径
#   JEV_PROFILE     该品牌真实 profile 目录

# 品牌表：优先级顺序即数组顺序。
JEV_BRANDS=(ego chrome edge brave chromium vivaldi arc opera comet dia)
JEV_LAST_RESORT=cdp9222

jev_browser_app() {  # $1=brand → app 路径（不存在则空）
  case "$1" in
    ego)      echo "/Applications/ego lite.app" ;;
    chrome)   echo "/Applications/Google Chrome.app" ;;
    chrome-canary) echo "/Applications/Google Chrome Canary.app" ;;
    edge)     echo "/Applications/Microsoft Edge.app" ;;
    brave)    echo "/Applications/Brave Browser.app" ;;
    chromium) echo "/Applications/Chromium.app" ;;
    vivaldi)  echo "/Applications/Vivaldi.app" ;;
    arc)      echo "/Applications/Arc.app" ;;
    opera)    echo "/Applications/Opera.app" ;;
    comet)    echo "/Applications/Comet.app" ;;
    dia)      echo "/Applications/Dia.app" ;;
    *)        echo "" ;;
  esac
}

jev_browser_profile() {  # $1=brand → 真实 profile 目录
  case "$1" in
    ego)      echo "$HOME/Library/Application Support/Citro Labs/ego lite" ;;
    chrome)   echo "$HOME/Library/Application Support/Google/Chrome" ;;
    chrome-canary) echo "$HOME/Library/Application Support/Google/Chrome Canary" ;;
    edge)     echo "$HOME/Library/Application Support/Microsoft Edge" ;;
    brave)    echo "$HOME/Library/Application Support/BraveSoftware/Brave-Browser" ;;
    chromium) echo "$HOME/Library/Application Support/Chromium" ;;
    vivaldi)  echo "$HOME/Library/Application Support/Vivaldi" ;;
    arc)      echo "$HOME/Library/Application Support/Arc/User Data" ;;
    opera)    echo "$HOME/Library/Application Support/com.operasoftware.Opera" ;;
    comet)    echo "$HOME/Library/Application Support/Comet" ;;
    dia)      echo "$HOME/Library/Application Support/Dia/User Data" ;;
    *)        echo "" ;;
  esac
}

jev_browser_exe() {  # $1=brand → 可执行文件（app 内），用于 fresh 模式直接拉起
  local app exe
  app="$(jev_browser_app "$1")"
  [ -n "${app}" ] || { echo ""; return; }
  exe="$(defaults read "${app}/Contents/Info.plist" CFBundleExecutable 2>/dev/null || true)"
  [ -n "${exe}" ] || exe="$(basename "${app}" .app)"
  echo "${app}/Contents/MacOS/${exe}"
}

jev_port_alive() {  # $1=port
  [ -n "${1:-}" ] || return 1
  python3 -c "import socket,sys
s=socket.socket(); s.settimeout(2)
sys.exit(0 if s.connect_ex(('127.0.0.1',int(sys.argv[1])))==0 else 1)" "$1" 2>/dev/null
}

jev_ws_from_dp() {  # $1=DevToolsActivePort 路径 → 端口活着才打印 ws://…
  local dp="$1" port path
  [ -f "${dp}" ] || return 1
  port="$(head -1 "${dp}" 2>/dev/null | tr -d '[:space:]')"
  path="$(sed -n 2p "${dp}" 2>/dev/null | tr -d '[:space:]')"
  [ -n "${port}" ] && [ -n "${path}" ] || return 1
  jev_port_alive "${port}" || return 1
  echo "ws://127.0.0.1:${port}${path}"
}

jev_browser_toggle_on() {  # $1=brand → 真实 profile 的用户级远程调试开关是否打开（0=打开）
  local prof
  prof="$(jev_browser_profile "$1")"
  [ -f "${prof}/Local State" ] || return 1
  python3 - "${prof}/Local State" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
v = (d.get("devtools") or {}).get("remote_debugging") or {}
sys.exit(0 if v.get("user-enabled") is True else 1)
PY
}

jev_is_running() {  # $1=brand → **该品牌真实 profile** 的实例是否在跑
  # 不能只看"同名进程存在"：别的工具（bb-browser 等）会用同一个浏览器二进制 + 自己的
  # user-data-dir 在跑（踩过：被误判成"用户的 Chrome 正在跑"，于是白白退到 fresh 无登录态档）。
  local app prof pid cmd
  app="$(jev_browser_app "$1")"; prof="$(jev_browser_profile "$1")"
  [ -n "${app}" ] || return 1
  for pid in $(pgrep -f "${app}/Contents/MacOS/" 2>/dev/null); do
    cmd="$(ps -o command= -p "${pid}" 2>/dev/null)" || continue
    case "${cmd}" in
      *"--user-data-dir=${prof}"*) return 0 ;;   # 正是这个真实 profile
      *"--user-data-dir="*) ;;                   # 别的 profile（例如别人的自动化实例）
      *) return 0 ;;                             # 没带 --user-data-dir = 默认 profile
    esac
  done
  return 1
}

jev_http_probe() {  # $1=port → 200 说明带 HTTP 发现接口（--remote-debugging-port 模式）
  curl -q -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$1/json/version" 2>/dev/null || echo 000
}

# 用独立 profile 拉起一个 Chromium 系实例（fresh 档）。
# 打印 ws URL；失败打印空。注意：绝不动真实 profile。
jev_launch_fresh() {  # $1=brand
  local brand="$1" app exe root prof dp log i timeout ws
  app="$(jev_browser_app "${brand}")"; exe="$(jev_browser_exe "${brand}")"
  [ -n "${app}" ] && [ -d "${app}" ] && [ -x "${exe}" ] || return 1
  root="${JEV_PROFILE_ROOT:-$HOME/.cache/jev-browser}"
  prof="${root}/${brand}-profile"
  dp="${prof}/DevToolsActivePort"
  log="${root}/${brand}.log"
  timeout="${JEV_LAUNCH_TIMEOUT:-25}"
  mkdir -p "${prof}" "${root}"
  # 这个 profile 的实例已经在跑且端点活着 → 直接复用（不要删端点文件：删了它反而
  # 拿不到已在运行的实例的端点，得等它重启——踩过）。
  ws="$(jev_ws_from_dp "${dp}")" && { echo "${ws}"; return 0; }
  # shellcheck disable=SC2086
  nohup "${exe}" --user-data-dir="${prof}" --remote-debugging-port=0 \
        --no-first-run --no-default-browser-check --disable-features=Translate \
        about:blank >"${log}" 2>&1 &
  disown 2>/dev/null || true
  for i in $(seq 1 "${timeout}"); do
    ws="$(jev_ws_from_dp "${dp}")" && { echo "${ws}"; return 0; }
    sleep 1
  done
  return 1
}

# 依赖用户级开关的"正常启动"路径（仍是真实 profile → 保留登录态）。
jev_launch_toggle() {  # $1=brand
  local brand="$1" app exe prof dp timeout i ws
  app="$(jev_browser_app "${brand}")"; exe="$(jev_browser_exe "${brand}")"
  prof="$(jev_browser_profile "${brand}")"
  dp="${prof}/DevToolsActivePort"
  timeout="${JEV_LAUNCH_TIMEOUT:-25}"
  [ -d "${app}" ] && [ -x "${exe}" ] || return 1
  [ -d "${prof}" ] || return 1
  jev_browser_toggle_on "${brand}" || return 1
  # 真实 profile 已在跑却没有端点 = 它是开关打开之前启动的，只能重启才生效；不强闯用户浏览器
  jev_is_running "${brand}" && return 1
  # 用二进制 + 显式 --user-data-dir 启动：不用 `open -a`，因为同二进制若已有别的
  # user-data-dir 实例在跑（例如别的工具自己的自动化 Chrome），open 只会把它激活，
  # 起不了这个真实 profile 的进程（踩过：Chrome 被判成 fresh 档）。
  # 这里不删陈旧的 DevToolsActivePort：新进程启动时会重写它，而删了只会多一个坑。
  nohup "${exe}" --user-data-dir="${prof}" --no-first-run --no-default-browser-check \
        about:blank >/dev/null 2>&1 &
  disown 2>/dev/null || true
  for i in $(seq 1 "${timeout}"); do
    ws="$(jev_ws_from_dp "${dp}")" && { echo "${ws}"; return 0; }
    sleep 1
  done
  return 1
}

jev_legacy_9222() {  # 老式固定端口端点（上一代兜底路线）
  curl -q -s --max-time 3 http://127.0.0.1:9222/json/version \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["webSocketDebuggerUrl"])' 2>/dev/null || true
}

jev_ws_brand() {  # $1=brand → 该品牌当前可用 ws（只查，不启动）
  local brand="$1" prof dp ws
  case "${brand}" in
    cdp9222) jev_legacy_9222; return ;;
  esac
  prof="$(jev_browser_profile "${brand}")"
  dp="${prof}/DevToolsActivePort"
  ws="$(jev_ws_from_dp "${dp}")" && { echo "${ws}"; return 0; }
  return 1
}

# 主入口。成功 0（已设置 JEV_WS/JEV_BRAND/JEV_MODE/JEV_LOGIN_STATE），失败 1。
jev_resolve_browser() {
  local forced="${JEV_BROWSER:-auto}"
  local dry="${JEV_DRY_RUN:-0}"
  local brand ws app

  JEV_WS=""; JEV_BRAND=""; JEV_MODE=""; JEV_LOGIN_STATE="no"; JEV_APP=""; JEV_PROFILE=""

  # 0) 显式端点优先
  if [ -n "${BU_CDP_WS:-}" ]; then
    JEV_WS="${BU_CDP_WS}"; JEV_BRAND="(env)"; JEV_MODE="env"; JEV_LOGIN_STATE="unknown"
    echo "[browser] 用环境变量 BU_CDP_WS 指定的端点：${JEV_WS}" >&2
    return 0
  fi

  # 1) 强制定向：只试这一个品牌，失败就失败（不偷偷换）
  if [ "${forced}" != "auto" ] && [ -n "${forced}" ]; then
    case "${forced}" in
      cdp9222) ws="$(jev_legacy_9222)"; [ -n "${ws}" ] || return 1
               JEV_WS="${ws}"; JEV_BRAND="cdp9222"; JEV_MODE="forced"; JEV_LOGIN_STATE="no"
               echo "[browser] 强制定向：9222 自动化端点" >&2; return 0 ;;
    esac
    app="$(jev_browser_app "${forced}")"
    [ -d "${app}" ] || { echo "[browser] JEV_BROWSER=${forced}：没装（${app}）" >&2; return 1; }
    # 定向品牌内部也按 real → toggle（保住登录态）→ fresh 三档试
    ws="$(jev_ws_brand "${forced}")" && {
      JEV_WS="${ws}"; JEV_BRAND="${forced}"; JEV_MODE="forced"; JEV_LOGIN_STATE="$(jev_browser_toggle_on "${forced}" && echo yes || echo no)"
      echo "[browser] 强制定向：${forced}（真实 profile，登录态=${JEV_LOGIN_STATE}）" >&2; return 0; }
    if [ "${dry}" = "1" ]; then
      JEV_BRAND="${forced}"; JEV_MODE="toggle"; JEV_APP="${app}"
      echo "[browser] 拟启动 ${forced}（真实 profile，登录态在）" >&2; return 0
    fi
    ws="$(jev_launch_toggle "${forced}")" && {
      JEV_WS="${ws}"; JEV_BRAND="${forced}"; JEV_MODE="toggle"; JEV_LOGIN_STATE="yes"
      JEV_APP="${app}"; JEV_PROFILE="$(jev_browser_profile "${forced}")"
      echo "[browser] 强制定向并已启动：${forced}（真实 profile，登录态在）" >&2; return 0; }
    ws="$(jev_launch_fresh "${forced}")" && {
      JEV_WS="${ws}"; JEV_BRAND="${forced}"; JEV_MODE="fresh"; JEV_LOGIN_STATE="no"
      JEV_APP="${app}"
      echo "[browser] 强制定向：${forced}（独立 profile，无登录态）" >&2; return 0; }
    echo "[browser] JEV_BROWSER=${forced}：装是装了，但拿不到 CDP 端点（可能它正在普通模式下运行，需退出重开）" >&2
    return 1
  fi

  # 2) 优先级链：先找"已经在跑且带端点"的（最省事，登录态在）
  for brand in "${JEV_BRANDS[@]}"; do
    ws="$(jev_ws_brand "${brand}")" || continue
    JEV_WS="${ws}"; JEV_BRAND="${brand}"; JEV_MODE="real"
    JEV_LOGIN_STATE="yes"; JEV_APP="$(jev_browser_app "${brand}")"; JEV_PROFILE="$(jev_browser_profile "${brand}")"
    echo "[browser] 用正在运行的 ${brand}（真实 profile，端口 $(echo "${ws}" | sed -E 's|ws://127.0.0.1:([0-9]+)/.*|\1|')，登录态在）" >&2
    [ "${brand}" = "ego" ] && [ "$(jev_http_probe "$(head -1 "${JEV_PROFILE}/DevToolsActivePort" | tr -d '[:space:]')")" != "200" ] \
      && echo "[browser] 注：首次连接 ego 会弹 \"Allow remote debugging?\"，点一次 Allow 即可（同一次启动内会记住）" >&2
    return 0
  done

  # 3) 没人在跑：挑一个"开关已打开"的品牌，正常启动它（还是真实 profile）
  for brand in "${JEV_BRANDS[@]}"; do
    app="$(jev_browser_app "${brand}")"
    [ -d "${app}" ] || continue
    jev_browser_toggle_on "${brand}" || continue
    [ "${dry}" = "1" ] && { JEV_BRAND="${brand}"; JEV_MODE="toggle"; JEV_LOGIN_STATE="yes"; JEV_APP="${app}"
      echo "[browser] 拟启动 ${brand}（开关已开，真实 profile，登录态在）" >&2; return 0; }
    ws="$(jev_launch_toggle "${brand}")" && {
      JEV_WS="${ws}"; JEV_BRAND="${brand}"; JEV_MODE="toggle"; JEV_LOGIN_STATE="yes"
      JEV_APP="${app}"; JEV_PROFILE="$(jev_browser_profile "${brand}")"
      echo "[browser] 已启动 ${brand}（真实 profile，登录态在）" >&2; return 0; }
    echo "[browser] ${brand} 开关已开但启动后仍没端点（可能是开关打开前就在跑），试下一个" >&2
  done

  # 4) 都没有：用独立 profile 拉一个 Chromium 系实例（能用，但没有登录态）
  for brand in "${JEV_BRANDS[@]}"; do
    app="$(jev_browser_app "${brand}")"
    [ -d "${app}" ] || continue
    [ "${dry}" = "1" ] && { JEV_BRAND="${brand}"; JEV_MODE="fresh"; JEV_APP="${app}"
      echo "[browser] 拟启动 ${brand}（独立 profile，无登录态）" >&2; return 0; }
    ws="$(jev_launch_fresh "${brand}")" && {
      JEV_WS="${ws}"; JEV_BRAND="${brand}"; JEV_MODE="fresh"; JEV_LOGIN_STATE="no"; JEV_APP="${app}"
      echo "[browser] 已启动 ${brand}（独立 profile，无登录态）" >&2; return 0; }
    echo "[browser] ${brand} 拉不起来，试下一个" >&2
  done

  # 5) 最后：老式 9222 端点
  ws="$(jev_legacy_9222)"
  if [ -n "${ws}" ]; then
    JEV_WS="${ws}"; JEV_BRAND="cdp9222"; JEV_MODE="real"; JEV_LOGIN_STATE="no"
    echo "[browser] 用 9222 上的自动化端点（无登录态）" >&2; return 0
  fi

  return 1
}

# 已有 daemon 若绑的不是本次解析出的端点，先停掉：ensure_daemon 会带着
# 继承的环境（含 BU_CDP_WS）重开一个，否则 agent 会对话到上一个浏览器。
jev_daemon_rebind() {  # $1=目标 ws
  local want="$1" cur i
  # 末尾必须带 `|| true`：没有 daemon 时 grep 返回 1，而调用方（run-local.sh）
  # 开了 set -euo pipefail，赋值语句的非零退出码会直接把整个脚本带走
  # （踩过：daemon 不在跑时 run-local.sh 静默 exit 1，agent 一步都没跑）。
  cur="$(ps eww -A -o command= 2>/dev/null | grep -F 'browser_harness.daemon' | grep -v grep \
        | sed -n 's/.*BU_CDP_WS=\([^ ]*\).*/\1/p' | head -1 || true)"
  [ -n "${cur}" ] || return 0
  if [ "${cur}" = "${want}" ]; then
    echo "[browser] daemon 已绑在同一端点上，沿用" >&2
    return 0
  fi
  echo "[browser] daemon 绑的是旧端点 ${cur}，重启它以切到新端点" >&2
  pkill -f 'browser_harness.daemon' 2>/dev/null || true
  for i in $(seq 1 10); do
    if ! ps eww -A -o command= 2>/dev/null | grep -F 'browser_harness.daemon' | grep -qv grep; then
      break
    fi
    sleep 0.5
  done
  rm -f "$HOME/.config/browser-harness/runtime/bu-default.sock" 2>/dev/null || true
  return 0
}

# 人类可读的一行摘要（doctor.sh 用）
jev_browser_summary() {
  case "${JEV_MODE}" in
    real)   echo "${JEV_BRAND}（在运行，真实 profile，登录态在）" ;;
    toggle) echo "${JEV_BRAND}（已用开关正常启动，真实 profile，登录态在）" ;;
    fresh)  echo "${JEV_BRAND}（独立 profile，无登录态——要登录态就给它开用户级远程调试开关）" ;;
    forced) echo "${JEV_BRAND}（JEV_BROWSER 定向，登录态=${JEV_LOGIN_STATE}）" ;;
    env)    echo "BU_CDP_WS 指定：${JEV_WS}" ;;
    *)      echo "未解析" ;;
  esac
}
