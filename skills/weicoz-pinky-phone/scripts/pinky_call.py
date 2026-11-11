#!/usr/bin/env python3
"""Pinky MCP client over Magpie's hub. Standard library only."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:3425/mcp/magpie/hub/codex"
DEFAULT_ADB = "/Applications/Pinky.app/Contents/Helpers/adb"
DEFAULT_ET_ADB = "10.144.144.10:5555"
APPROVAL_RE = re.compile(r"approval_id:\s*(\S+)")


def sse_data(body):
    values = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    return values[-1] if values else "{}"


def render(result):
    parts = []
    for item in result.get("content") or []:
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
        elif item.get("type") == "image":
            parts.append("[image]")
    return "\n".join(parts)


class Client:
    def __init__(self, url):
        self.url = url
        self.session = None
        self.seq = 0

    def _post(self, payload):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                self.session = response.headers.get("Mcp-Session-Id") or self.session
                body = response.read().decode("utf-8", "replace")
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise SystemExit(
                f"错误：连不上 Magpie hub {self.url}\n{error.reason}\n"
                "请确认 Magpie 在运行，并在 Library → MCP 为 codex 打开 pinky。"
            ) from error
        if not body.strip():
            return {}
        if body.lstrip().startswith("event:") or "text/event-stream" in content_type:
            body = sse_data(body)
        return json.loads(body)

    def initialize(self):
        self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pinky-call", "version": "1.0"},
                },
            }
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def rpc(self, method, params):
        self.seq += 1
        response = self._post(
            {"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params}
        )
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"], ensure_ascii=False))
        return response["result"]

    def tools(self):
        return self.rpc("tools/list", {}).get("tools") or []

    def call(self, name, arguments):
        if not name.startswith("pinky__"):
            name = "pinky__" + name
        return self.rpc("tools/call", {"name": name, "arguments": arguments})


def run_call(client, tool, arguments, wait, timeout):
    deadline = time.time() + timeout
    while True:
        result = client.call(tool, arguments)
        text = render(result)
        approval = APPROVAL_RE.search(text)
        if not (wait and approval and "approval_pending" in text):
            print(text)
            return 1 if result.get("isError") else 0
        if time.time() >= deadline:
            print(text)
            print("错误：等待审批超时。", file=sys.stderr)
            return 2
        print(f"等待审批 {approval.group(1)}…", file=sys.stderr)
        time.sleep(3)
        arguments = dict(arguments, approval_id=approval.group(1))


def adb_devices(adb):
    output = subprocess.run(
        [adb, "devices"], capture_output=True, text=True, timeout=20
    ).stdout
    return [
        line.split()[0]
        for line in output.splitlines()[1:]
        if line.strip().endswith("device")
    ]


def adb_run(adb, *args, timeout=15):
    return subprocess.run(
        [adb, *args], capture_output=True, text=True, timeout=timeout
    )


def adb_shell(adb, device, *args, timeout=15):
    return adb_run(adb, "-s", device, "shell", *args, timeout=timeout).stdout.replace(
        "\r", ""
    ).strip()


def wifi_endpoint(adb, device):
    addresses = adb_shell(adb, device, "ip", "-4", "addr", "show", "wlan0")
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", addresses)
    if not match:
        return None
    port = adb_shell(adb, device, "getprop", "service.adb.tcp.port") or "5555"
    return f"{match.group(1)}:{port if port.isdigit() else '5555'}"


def is_local_route(host):
    result = subprocess.run(
        ["route", "-n", "get", host], capture_output=True, text=True, timeout=10
    )
    match = re.search(r"interface:\s*(\S+)", result.stdout)
    return bool(match and not match.group(1).startswith(("utun", "lo")))


def serial(adb, device):
    return adb_shell(adb, device, "getprop", "ro.serialno")


def restart_adb(adb):
    adb_run(adb, "kill-server", timeout=10)
    adb_run(adb, "start-server", timeout=15)


def connect_adb(adb, endpoint):
    adb_run(adb, "connect", endpoint)
    if endpoint in adb_devices(adb):
        return True
    restart_adb(adb)
    adb_run(adb, "connect", endpoint)
    return endpoint in adb_devices(adb)


def keep_only(adb, endpoint):
    for device in adb_devices(adb):
        if ":" in device and device != endpoint:
            adb_run(adb, "disconnect", device, timeout=10)
    if ":" not in endpoint:
        adb_run(adb, "disconnect", timeout=10)


def pick_channel(adb):
    devices = adb_devices(adb)
    usb = [device for device in devices if ":" not in device]
    if usb:
        keep_only(adb, usb[0])
        return usb[0], "USB"

    fallback = os.environ.get("PINKY_EASYTIER_ADB", DEFAULT_ET_ADB)
    base = next((device for device in devices if ":" in device), None)
    if base is None and connect_adb(adb, fallback):
        base = fallback

    if base:
        base_serial = serial(adb, base)
        wifi = wifi_endpoint(adb, base)
        if wifi:
            host = wifi.rsplit(":", 1)[0]
            if is_local_route(host) and connect_adb(adb, wifi):
                wifi_serial = serial(adb, wifi)
                if wifi_serial and (not base_serial or wifi_serial == base_serial):
                    keep_only(adb, wifi)
                    return wifi, "WiFi"
                adb_run(adb, "disconnect", wifi, timeout=10)

        if base != fallback and connect_adb(adb, fallback):
            base = fallback
        if base in adb_devices(adb):
            keep_only(adb, base)
            return base, "EasyTier" if base == fallback else "adb"

    raise RuntimeError("没有可用 adb 通道：USB、内网 Wi-Fi 和 EasyTier 都不可达")


def doctor(client, adb):
    failed = False
    names = [tool.get("name") for tool in client.tools()]
    if "pinky__phone_connect" in names:
        print(f"hub: {client.url} — OK，{len(names)} 个工具")
    else:
        print(f"hub: {client.url} — 没有 pinky 工具")
        print("修复：Magpie → Library → MCP，为 codex 打开 pinky。")
        failed = True
    try:
        devices = adb_devices(adb)
    except Exception as error:
        print(f"adb: {adb} — 失败：{error}")
        return 1
    if not devices:
        print(f"adb: {adb} — 没有在线设备")
        print("修复：手机打开无线调试并授权本机；或先用 Pinky 添加手机。")
        return 1
    print(f"adb: {len(devices)} 台在线 — {', '.join(devices)}")
    device = devices[0]
    focus = subprocess.run(
        [adb, "-s", device, "shell", "dumpsys", "window"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    for line in focus.splitlines():
        text = line.strip()
        if "mCurrentFocus" in text or "mFocusedApp" in text:
            print(f"前台: {text}")
    packages = subprocess.run(
        [adb, "-s", device, "shell", "pm", "list", "packages", "-3"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    banks = [
        line.split(":", 1)[1]
        for line in packages.splitlines()
        if re.search(r"bank|wallet|pay", line, re.I)
    ]
    if banks:
        print("金融类包名: " + ", ".join(banks[:10]))
    return 1 if failed else 0


def selftest():
    assert APPROVAL_RE.search("approval_pending · X · approval_id: ap_abc").group(1) == "ap_abc"
    assert sse_data('event: message\ndata: {"a": 1}\n') == '{"a": 1}'
    assert render({"content": [{"type": "text", "text": "hi"}]}) == "hi"
    assert render({"content": [{"type": "image"}]}) == "[image]"
    print("selftest ok")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Pinky MCP client over Magpie hub")
    parser.add_argument("--url", default=os.environ.get("MAGPIE_HUB_URL", DEFAULT_URL))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="检查 hub、adb、前台 App 与金融类包名")
    commands.add_parser("list", help="列出 pinky 工具")
    commands.add_parser(
        "pick", help="选择并切换最优 adb 通道（USB > 同网 Wi-Fi > EasyTier）"
    )
    commands.add_parser("selftest", help="离线自检")
    connect = commands.add_parser("connect", help="选路后创建 Pinky 任务")
    connect.add_argument("task")
    connect.add_argument("--read-only", action="store_true")
    connect.add_argument(
        "--wait-approval",
        nargs="?",
        const=900,
        type=int,
        default=0,
        metavar="SECONDS",
    )
    call = commands.add_parser("call", help="调用一个 pinky 工具")
    call.add_argument("tool")
    call.add_argument("arguments", nargs="?", default="{}")
    call.add_argument(
        "--wait-approval",
        nargs="?",
        const=900,
        type=int,
        default=0,
        metavar="SECONDS",
        help="遇 approval_pending 时用 approval_id 重试，默认最多等 900 秒",
    )
    call.add_argument("--json", action="store_true", help="输出完整 JSON")
    args = parser.parse_args()

    if args.command == "selftest":
        return selftest()
    if args.command == "pick":
        try:
            endpoint, reason = pick_channel(os.environ.get("PINKY_ADB", DEFAULT_ADB))
        except Exception as error:
            print(f"错误：{error}", file=sys.stderr)
            return 1
        print(f"{reason}: {endpoint}")
        return 0
    client = Client(args.url)
    if args.command == "doctor":
        client.initialize()
        return doctor(client, os.environ.get("PINKY_ADB", DEFAULT_ADB))
    client.initialize()
    if args.command == "list":
        for tool in client.tools():
            if tool.get("name", "").startswith("pinky__"):
                first = (tool.get("description") or "").splitlines()[0]
                print(f"{tool['name']} :: {first[:140]}")
        return 0
    if args.command == "connect":
        try:
            endpoint, reason = pick_channel(os.environ.get("PINKY_ADB", DEFAULT_ADB))
        except Exception as error:
            print(f"错误：{error}", file=sys.stderr)
            return 1
        print(f"通道: {reason} {endpoint}", file=sys.stderr)
        arguments = {"task": args.task}
        if args.read_only:
            arguments["read_only"] = True
        return run_call(
            client,
            "phone_connect",
            arguments,
            args.wait_approval,
            args.wait_approval,
        )
    try:
        arguments = json.loads(args.arguments)
    except json.JSONDecodeError as error:
        print(f"错误：arguments 不是合法 JSON：{error}", file=sys.stderr)
        return 2
    if args.json:
        result = client.call(args.tool, arguments)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("isError") else 0
    return run_call(
        client, args.tool, arguments, args.wait_approval, args.wait_approval
    )


if __name__ == "__main__":
    sys.exit(main())
