#!/usr/bin/env python3
"""一次性、可见浏览器回归；测试结束关闭自建服务与浏览器。"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
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
    session = "ui-studio-" + uuid.uuid4().hex[:10]
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "assets/gallery")))
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
        run("open", f"http://127.0.0.1:{server.server_port}/index.html", "--headed")
        result = run("run-code", "--filename=" + str(ROOT / "tests/browser.js"))
        (output / "browser-result.txt").write_text(result, encoding="utf-8")
        if not re.search(r'"passed"\s*:\s*true', result):
            raise RuntimeError("未收到真实任务通过回执")
    finally:
        try:
            run("close", timeout=20)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
