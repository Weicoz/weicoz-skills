#!/usr/bin/env python3
"""一次性、可见浏览器回归；测试结束关闭自建服务与浏览器。"""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cli = shutil.which("playwright-cli")
    if not cli:
        parser.error("未找到 playwright-cli，请使用宿主可用浏览器执行 tests/browser.js 中的任务")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    site = output / "site"
    shutil.copytree(ROOT / "assets/gallery", site / "gallery")
    manifest = {"project": "整合验证", "round": "test", "candidates": [
        {"id": name, "name": name, "source": "gallery/" + source, "interactive": True, "nativeViewport": viewport}
        for name, source, viewport in [("components", "index.html", "1440x1000"), ("workspace", "workspace.html", "1440x1000"), ("states", "interaction.html", "390x844")]
    ]}
    (site / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/build_explorer.py"), str(site / "manifest.json")], check=True, capture_output=True, text=True)
    session = "ui-studio-" + uuid.uuid4().hex[:10]
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    def run(*arguments, timeout=180):
        result = subprocess.run([cli, "-s=" + session, *arguments], cwd=output, text=True, encoding="utf-8", capture_output=True, timeout=timeout)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
        if result.returncode or "### Error" in result.stdout:
            raise RuntimeError("浏览器命令失败：" + " ".join(arguments))
        return result.stdout
    try:
        run("open", f"http://127.0.0.1:{server.server_port}/gallery/index.html", "--headed")
        result = run("run-code", "--filename=" + str(ROOT / "tests/browser.js"))
        (output / "browser-result.txt").write_text(result, encoding="utf-8")
        if not re.search(r'"passed"\s*:\s*true', result):
            raise RuntimeError("未收到真实任务通过回执")
        run("goto", f"http://127.0.0.1:{server.server_port}/style-explorer.html")
        result = run("run-code", "--filename=" + str(ROOT / "tests/comparison.js"))
        (output / "comparison-result.txt").write_text(result, encoding="utf-8")
        if not re.search(r'"passed"\s*:\s*true', result):
            raise RuntimeError("对比页整合验证未通过")
    finally:
        try:
            run("close", timeout=20)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            # 清理失败要提示，但不覆盖已经得到的验证结论或先前的真实错误。
            print(f"警告：关闭浏览器会话失败，请手动关闭 {session}：{error}", file=sys.stderr)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
