#!/usr/bin/env python3
"""T3 Code MCP 客户端封装（无第三方依赖）。

用法：
  t3-mcp.py login                    # 申请 MCP 令牌，只把令牌打印到 stdout，用 export T3_MCP_TOKEN=$(...) 接收
  t3-mcp.py tools                    # 列出工具名
  t3-mcp.py schema <工具名>          # 看某工具的入参
  t3-mcp.py call <工具名> [JSON入参] # 调用工具，输出文本结果

环境变量（均可选，T3_MCP_TOKEN 在 tools/schema/call 时必需）：
  T3_MCP_URL     T3 服务端地址，默认 http://127.0.0.1:3773
  T3_MCP_TOKEN   login 打印的令牌；只放进程环境变量，不写文件
  T3_MCP_ACCESS  login 申请的权限，默认 auto-accept-edits
                 （read-only|approval-required|auto-accept-edits|auto|full-access）
"""
import base64, hashlib, json, os, secrets, subprocess, sys, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get("T3_MCP_URL", "http://127.0.0.1:3773").rstrip("/")


def die(msg):
    sys.exit("错误：" + msg)


def http(path, body, headers=None, form=False):
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    h = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, data, h), timeout=30) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        die("HTTP %s %s" % (e.code, e.read().decode()[:300]))


def t3_json(*args):
    out = subprocess.run(["t3", *args], capture_output=True, text=True).stdout
    start = out.find("{")  # 服务端比 CLI 新时 stdout 会混入 WARN 日志
    if start < 0:
        die("t3 命令没有返回 JSON：" + " ".join(args[:3]))
    return json.JSONDecoder().raw_decode(out[start:])[0]


def login():
    # 1. 用短期管理会话换一个绑定权限等级的一次性配对码；用完立即吊销
    adm = t3_json("auth", "session", "issue", "--scope", "access:write", "--scope", "orchestration:read",
                  "--scope", "orchestration:operate", "--ttl", "5m", "--label", "t3-dispatch-admin", "--json")
    access = os.environ.get("T3_MCP_ACCESS", "auto-accept-edits")
    try:
        code = http("/api/auth/pairing-token", {"label": "t3-dispatch", "access": access},
                    {"Authorization": "Bearer " + adm["token"]})["credential"]
    finally:
        subprocess.run(["t3", "auth", "session", "revoke", adm["sessionId"]], capture_output=True)
    # 2. OAuth：注册客户端 -> 用配对码批准 -> 换令牌（PKCE）
    redir = "http://127.0.0.1:9/cb"
    cid = http("/oauth/mcp/register", {"client_name": "t3-dispatch", "redirect_uris": [redir],
                                       "token_endpoint_auth_method": "none"})["client_id"]
    ver = secrets.token_urlsafe(48)
    chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
    res = BASE + "/mcp"
    auth = {"response_type": "code", "client_id": cid, "redirect_uri": redir, "code_challenge": chal,
            "code_challenge_method": "S256", "state": "s", "resource": res}
    r = http("/oauth/mcp/decision", {"authorization": auth,
                                     "decision": {"_tag": "pairing-code", "access": access, "code": code}})
    c = urllib.parse.parse_qs(urllib.parse.urlparse(r["redirectTo"]).query)["code"][0]
    t = http("/oauth/mcp/token", {"grant_type": "authorization_code", "code": c, "redirect_uri": redir,
                                  "client_id": cid, "code_verifier": ver, "resource": res}, form=True)
    print(t["access_token"])


class Mcp:
    def __init__(self):
        self.tok = os.environ.get("T3_MCP_TOKEN") or die("未设置 T3_MCP_TOKEN。先运行：export T3_MCP_TOKEN=$(t3-mcp.py login)")
        self.sid = None
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "t3-dispatch", "version": "1"}})
        self.rpc("notifications/initialized", notify=True)

    def rpc(self, method, params=None, notify=False):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = 1
        h = {"Authorization": "Bearer " + self.tok, "Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        try:
            f = urllib.request.urlopen(urllib.request.Request(BASE + "/mcp", json.dumps(body).encode(), h), timeout=600)
        except urllib.error.HTTPError as e:
            die("HTTP %s %s" % (e.code, e.read().decode()[:300]))
        self.sid = f.headers.get("Mcp-Session-Id") or self.sid
        raw = f.read().decode()
        if notify or not raw.strip():
            return None
        for line in raw.splitlines():  # 可能是 SSE 帧
            if line.startswith("data:"):
                raw = line[5:]
                break
        d = json.loads(raw)
        if "error" in d:
            die("RPC " + json.dumps(d["error"], ensure_ascii=False)[:500])
        return d["result"]


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("login", "tools", "schema", "call"):
        sys.exit(__doc__)
    if a[0] == "login":
        return login()
    m = Mcp()
    tools = m.rpc("tools/list")["tools"]
    if a[0] == "tools":
        print("\n".join(t["name"] for t in tools))
    elif a[0] == "schema":
        print(json.dumps(next(t for t in tools if t["name"] == a[1]), ensure_ascii=False, indent=1))
    else:
        r = m.rpc("tools/call", {"name": a[1], "arguments": json.loads(a[2]) if len(a) > 2 else {}})
        for c in r.get("content", []):
            print(c.get("text", c))
        sys.exit(1 if r.get("isError") else 0)


main()
