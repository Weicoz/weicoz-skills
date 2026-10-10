#!/usr/bin/env bash
# jev-ultrafast 端到端冒烟：真跑一个任务，只看**服务端有没有真的收到提交**。
#   bash smoke.sh                 # 用 run-local.sh（默认 ego 优先）
#   SMOKE_PORT=8899 bash smoke.sh # 换端口
# 退出码：0 = 全链路通过；1 = 失败（含 agent 报 done 但服务端没收到）。
set -uo pipefail

PROJ="${JEV_PROJ:-$HOME/File/git/jev-ultrafast}"
PORT_BASE="${SMOKE_PORT:-8899}"
ROOT="$(mktemp -d)"
LOG="$ROOT/submit.log"
TEXT="${SMOKE_TEXT:-Wei}"
NONCE="$(python3 -c 'import secrets;print(secrets.token_hex(4))')"
: > "$LOG"

port_busy() {  # 端口被占用就返回 0（别人的服务在跑，绝不能拿它的响应当自己就绪）
  python3 -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1',int(sys.argv[1])))==0 else 1)" "$1" 2>/dev/null
}

cleanup() {
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null
  sleep 1
  rm -rf "$ROOT"
}
trap cleanup EXIT

cat > "$ROOT/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>jev smoke</title>
<h1>jev-ultrafast smoke test</h1>
<form id="f" onsubmit="fetch('/__submit?value='+encodeURIComponent(document.querySelector('#fullname').value));return false">
  <label for="fullname">Full name</label>
  <input id="fullname" name="fullname" type="text">
  <button id="submit" type="submit">Submit</button>
</form>
<div style="height:900px"></div>
HTML

cat > "$ROOT/server.py" <<'PY'
import os, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
ROOT, LOG, PORT, NONCE = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)
    def do_GET(self):
        if self.path.startswith("/__ping"):
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(NONCE.encode()); return
        if self.path.startswith("/__submit"):
            from urllib.parse import unquote, urlparse, parse_qs
            v = parse_qs(urlparse(self.path).query).get("value", [""])[0]
            with open(LOG, "a") as f:
                f.write(f"{__import__('datetime').datetime.now():%H:%M:%S} submit value={unquote(v)!r}\n")
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"ok"); return
        return super().do_GET()
    def log_message(self, *a):  # 静默：日志噪音会淹没判定行
        pass

ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
PY

echo "jev-ultrafast 冒烟测试（判定只看服务端日志）"

# 挑一个空闲端口：撞上上一次会话遗留的服务会拿到假的"就绪"（踩过：端口被占，
# 探针服务没起来，就绪检查却对着旧服务的 200 通过，最后判定成一个假失败）
PORT=""
for p in $(seq "$PORT_BASE" $((PORT_BASE + 9))); do
  port_busy "$p" || { PORT="$p"; break; }
done
[ -n "$PORT" ] || { echo "  ❌ ${PORT_BASE}~$((PORT_BASE + 9)) 全被占用，用 SMOKE_PORT= 换一组"; exit 1; }

python3 "$ROOT/server.py" "$ROOT" "$LOG" "$PORT" "$NONCE" >/dev/null 2>&1 &
SRV_PID=$!
disown "$SRV_PID" 2>/dev/null || true   # 免得收尾 kill 时冒出 "[1] Terminated: 15" 噪声

# 就绪判定必须验到"这就是我们的服务"：/__ping 回 nonce
ready=0
for _ in $(seq 1 15); do
  sleep 1
  [ "$(curl -q -s --max-time 2 "http://127.0.0.1:${PORT}/__ping" 2>/dev/null)" = "$NONCE" ] && { ready=1; break; }
done
if [ "$ready" != 1 ]; then
  echo "  ❌ 探针服务没起来（pid ${SRV_PID}，端口 ${PORT}）"; exit 1
fi
echo "  ✅ 探针页已就绪：http://127.0.0.1:${PORT}/"

cd "$PROJ" || { echo "  ❌ 找不到项目目录 ${PROJ}"; exit 1; }
echo
echo "--- agent 运行日志 ---"
out="$(env -u BU_CDP_WS timeout "${SMOKE_TIMEOUT:-300}" ./run-local.sh \
        --url "http://127.0.0.1:${PORT}/" \
        --goal "Type ${TEXT} into the Full name field, then click Submit." 2>&1)"
rc=$?
printf '%s\n' "$out" | sed 's/^/  /'
echo "--- 运行日志结束（退出码 ${rc}）---"
echo

if grep -q "done" <<<"$out" && grep -q "submit value='${TEXT}'" "$LOG"; then
  echo "  ✅ 服务端日志：$(cat "$LOG" | tr -d '\n')"
  echo
  echo "结论：端到端通过——提交真的发生了，不只是模型说 DONE。"
  exit 0
fi

if grep -q "submit value='${TEXT}'" "$LOG"; then
  echo "  ⚠️  服务端收到提交，但 agent 没报 done（可能超时或末步卡住）：$(cat "$LOG" | tr -d '\n')"
else
  echo "  ❌ 服务端没有收到提交 —— DONE 不等于成功，这次没通过。"
  echo "     先跑体检：bash $(cd "$(dirname "$0")" && pwd)/doctor.sh"
fi
exit 1
