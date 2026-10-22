#!/usr/bin/env python3
"""按状态清单截图，可选录屏；仅使用已有 playwright-cli。"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def prepare(manifest, output):
    spec = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not isinstance(spec.get("cases"), list) or not spec["cases"]:
        raise ValueError("cases 必须为非空数组")
    seen = set()
    root = (manifest.parent / spec.get("root", ".")).resolve()
    for i, case in enumerate(spec["cases"]):
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in seen:
            raise ValueError("每个状态必须有不重复的非空 id")
        seen.add(case["id"])
        if ("path" in case) == ("url" in case):
            raise ValueError("每个状态恰好提供 path 或 url")
        if "url" in case:
            url = urlsplit(case["url"])
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("url 必须为无凭据 HTTP(S) 地址")
        else:
            path = (root / case["path"]).resolve()
            if not path.is_file() or not path.is_relative_to(root):
                raise ValueError("path 必须为 root 内的真实文件")
            case["relative_url"] = quote(str(path.relative_to(root)).replace("\\", "/"), safe="/")
        viewport = case.get("viewport", {"width": 1440, "height": 1000})
        if not isinstance(viewport, dict) or any(type(viewport.get(k)) is not int or not 200 <= viewport[k] <= 5000 for k in ["width", "height"]):
            raise ValueError("视口 width/height 必须为 200–5000 的整数")
        case["viewport"] = viewport
        if not isinstance(case.get("actions", []), list):
            raise ValueError("actions 必须为数组")
        for action in case.get("actions", []):
            if not isinstance(action, dict) or action.get("type") not in {"click", "fill", "select", "press", "scroll", "wait", "drag"}:
                raise ValueError("动作支持 click/fill/select/press/scroll/wait/drag")
        case["screenshot"] = str(output / f"state-{i + 1:02d}.png")
    return spec, root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    server = None
    cli = shutil.which("playwright-cli")
    session = "ui-capture-" + uuid.uuid4().hex[:10]
    try:
        if not cli:
            raise ValueError("未找到 playwright-cli，请使用当前宿主截图工具")
        spec, root = prepare(args.manifest.resolve(), output)
        output.mkdir(parents=True, exist_ok=False)
        if any("path" in c for c in spec["cases"]):
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            for case in spec["cases"]:
                if "relative_url" in case:
                    case["url"] = f"http://127.0.0.1:{server.server_port}/" + case["relative_url"]
        def run(*arguments):
            result = subprocess.run([cli, "-s=" + session, *arguments], cwd=output, capture_output=True, text=True, encoding="utf-8", timeout=300)
            if result.returncode or "### Error" in result.stdout:
                raise ValueError(result.stdout + result.stderr)
            return result.stdout
        try:
            run("open", "--headed")
            if args.record:
                run("video-start", str(output / "walkthrough.webm"))
            template = (ROOT / "scripts/capture-browser.js").read_text(encoding="utf-8")
            script = output / "capture-run.js"
            script.write_text(template.replace("/*SPEC*/null", json.dumps(spec, ensure_ascii=False)), encoding="utf-8")
            transcript = run("run-code", "--filename=" + str(script))
            (output / "capture-transcript.txt").write_text(transcript, encoding="utf-8")
            match = re.search(r"### Result\n([^\n]+)", transcript)
            if not match:
                raise ValueError("没有截图回执")
            report = json.loads(match.group(1))
            (output / "capture.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if args.record:
                run("video-stop")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["captured"] else 1
        finally:
            run("close")
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as error:
        print(f"截图失败：{error}")
        return 2
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
