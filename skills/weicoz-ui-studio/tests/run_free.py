#!/usr/bin/env python3
"""让锁定 Free 的原有用例直接检查当前运行层，浏览器保持可见。"""
import argparse
import importlib.util
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import threading
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def visible_probe(case, result_id="i18n-result", profile="chrome-probe"):
    """保留上游注入的 DOM 探针和全部断言，仅替换本机不稳定的 pipe 启动层。"""
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    cli = shutil.which("playwright-cli")
    if not cli:
        raise RuntimeError("可见对比页回归需要已安装的 playwright-cli")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(case.folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    session = "ui-free-probe-" + uuid.uuid4().hex[:8]
    def run(*arguments):
        return subprocess.run([cli, "-s=" + session, *arguments], capture_output=True, text=True, timeout=30, cwd=case.folder)
    try:
        relative = case.output.relative_to(case.folder).as_posix()
        opened = run("open", "--headed")
        if opened.returncode or "### Error" in opened.stdout:
            return subprocess.CompletedProcess([], 1, "", opened.stdout + opened.stderr)
        selector = json.dumps("#" + result_id)
        address = json.dumps(f"http://127.0.0.1:{server.server_port}/{relative}")
        script = f"async page => {{ await page.emulateMedia({{reducedMotion:'reduce'}}); await page.goto({address}); await page.waitForFunction(() => document.querySelector({selector})?.textContent); return await page.evaluate(() => document.querySelector({selector}).textContent); }}"
        result = run("run-code", script)
        match = re.search(r"### Result\n([^\n]+)", result.stdout)
        if result.returncode or not match:
            return subprocess.CompletedProcess([], 1, "", result.stdout + result.stderr)
        return subprocess.CompletedProcess([], 0, json.loads(match.group(1)) + "\n", "")
    finally:
        run("close")
        server.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["all", "build", "media", "shoot"], default="all")
    parser.add_argument("--test", help="只运行本套中的指定 Class.method，定位失败时使用")
    args = parser.parse_args()
    suite = unittest.TestSuite()
    original_run = subprocess.run

    def visible_run(arguments, *positional, **keywords):
        # 只适配上游内联浏览器探针的启动标志；所有断言、数据和协议保持原样。
        if isinstance(arguments, (list, tuple)) and "-e" in arguments:
            arguments = list(arguments)
            index = arguments.index("-e") + 1
            if index < len(arguments) and isinstance(arguments[index], str):
                arguments[index] = arguments[index].replace("'--headless=new',", "").replace('"--headless=new",', "")
        return original_run(arguments, *positional, **keywords)

    subprocess.run = visible_run
    try:
        choices = {"build": "test_build_explorer.py", "media": "test_curate_media.py", "shoot": "test_shoot.py"}
        for key, filename in choices.items():
            if args.suite not in ("all", key):
                continue
            module = load("free_" + key, ROOT / "upstream/oil-ui/tests" / filename)
            module.ROOT = ROOT
            if key == "build":
                module.builder = load("studio_full_explorer", ROOT / "scripts/build_explorer.py")
                module.ExplorerBuildTests.run_browser_probe = visible_probe
            else:
                module.SCRIPT = ROOT / "scripts" / ("curate-media.mjs" if key == "media" else "shoot.mjs")
            if args.test:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromName(args.test, module))
            else:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        print(json.dumps({"suite": args.suite, "tests": result.testsRun, "failures": len(result.failures),
                          "errors": len(result.errors), "skipped": len(result.skipped), "passed": result.wasSuccessful()}, ensure_ascii=False))
        return 0 if result.wasSuccessful() else 1
    finally:
        subprocess.run = original_run


if __name__ == "__main__":
    raise SystemExit(main())
