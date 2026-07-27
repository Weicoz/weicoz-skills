#!/usr/bin/env python3
"""Outer bridge for official last30days-cn.

Does not modify or import-patch the official skill. Runs it via python3 and adds
diagnostics plus weak public site-search fallback.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

OFFICIAL = Path("/Users/weicoz/.agents/skills/last30days-cn/scripts/last30days.py")
BROWSER_STATE_DIR = Path.home() / ".codex" / "browser-states"

SOURCE_SITE_QUERIES = {
    "weibo": "site:weibo.com OR site:m.weibo.cn",
    "xiaohongshu": "site:xiaohongshu.com/explore",
    "bilibili": "site:bilibili.com/video",
    "zhihu": "site:zhihu.com/question OR site:zhuanlan.zhihu.com/p",
    "douyin": "site:douyin.com/video",
    "wechat": "site:mp.weixin.qq.com",
    "baidu": "",
    "toutiao": "site:toutiao.com",
}

SOURCE_HOSTS = {
    "weibo": ("weibo.com", "m.weibo.cn"),
    "xiaohongshu": ("xiaohongshu.com",),
    "bilibili": ("bilibili.com",),
    "zhihu": ("zhihu.com", "zhuanlan.zhihu.com"),
    "douyin": ("douyin.com",),
    "wechat": ("mp.weixin.qq.com",),
    "baidu": ("baidu.com",),
    "toutiao": ("toutiao.com",),
}


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _official(args: list[str]) -> subprocess.CompletedProcess[str]:
    if not OFFICIAL.exists():
        raise SystemExit(f"official last30days-cn not found: {OFFICIAL}")
    return _run(["python3", str(OFFICIAL), *args])


def diagnose(_: argparse.Namespace) -> int:
    official = _official(["--diagnose"])
    official_json: Any
    try:
        official_json = json.loads(official.stdout)
    except json.JSONDecodeError:
        official_json = {
            "parse_error": True,
            "stdout": official.stdout,
            "stderr": official.stderr,
            "returncode": official.returncode,
        }

    states = {}
    for source in SOURCE_SITE_QUERIES:
        path = BROWSER_STATE_DIR / f"last30days-cn-{source}.json"
        states[source] = str(path) if path.exists() else None

    result = {
        "bridge": {
            "python": shutil.which("python"),
            "python3": shutil.which("python3"),
            "playwright_cli": shutil.which("playwright-cli"),
            "official_script": str(OFFICIAL),
            "official_script_exists": OFFICIAL.exists(),
            "browser_states": states,
        },
        "official": official_json,
        "stderr": official.stderr.strip(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if official.returncode == 0 else official.returncode


def _fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def site_search(topic: str, source: str, limit: int) -> list[dict[str, Any]]:
    site = SOURCE_SITE_QUERIES.get(source, "")
    query = f"{site} {topic}".strip()
    encoded = urllib.parse.quote(query)
    url = f"https://cn.bing.com/search?q={encoded}&setmkt=zh-CN&ensearch=0"
    items: list[dict[str, Any]] = []
    try:
        html = _fetch(url)
    except Exception as exc:
        return [{
            "source": source,
            "source_path": f"bridge:site-search:{source}",
            "error": str(exc),
            "query": query,
        }]

    blocks = re.findall(r'<li class="b_algo"[^>]*>([\s\S]*?)</li>', html)
    seen = set()
    allowed_hosts = SOURCE_HOSTS.get(source, ())
    for block in blocks:
        match = re.search(
            r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>',
            block,
            re.S,
        )
        if not match:
            continue
        href = match.group(1)
        if href in seen:
            continue
        host = urllib.parse.urlparse(href).netloc.lower()
        if allowed_hosts and not any(host == h or host.endswith(f".{h}") for h in allowed_hosts):
            continue
        seen.add(href)
        snippet_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.S)
        items.append({
            "source": source,
            "source_path": f"bridge:site-search:{source}",
            "title": _clean(match.group(2)),
            "url": href,
            "snippet": _clean(snippet_match.group(1)) if snippet_match else "",
            "date": None,
            "date_confidence": "low",
            "engagement_confidence": "none",
            "query": query,
        })
        if len(items) >= limit:
            break
    return items


def fallback(args: argparse.Namespace) -> int:
    sources = [s.strip() for s in args.search.split(",") if s.strip()]
    data = {
        "topic": args.topic,
        "source_path": "bridge:site-search",
        "items": [item for source in sources for item in site_search(args.topic, source, args.limit)],
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def run(args: argparse.Namespace) -> int:
    official_args = [args.topic, "--emit", args.emit]
    if args.search:
        official_args += ["--search", args.search]
    if args.deep:
        official_args.append("--deep")
    if args.quick:
        official_args.append("--quick")
    if args.as_of:
        official_args += ["--as-of", args.as_of]

    proc = _official(official_args)
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")

    if args.no_fallback or not args.search:
        return proc.returncode

    sources = [s.strip() for s in args.search.split(",") if s.strip()]
    fallback_items = [item for source in sources for item in site_search(args.topic, source, args.fallback_limit)]
    if fallback_items:
        print("\n\n## Bridge fallback evidence")
        print("source_path: `bridge:site-search:*`; confidence: weak; use for discovery, not strong claims.\n")
        for item in fallback_items:
            if item.get("error"):
                print(f"- [{item['source']}] fallback failed: `{item['error']}`")
                continue
            print(f"- [{item['source']}] {item.get('title','')} — {item.get('url','')}")
            if item.get("snippet"):
                print(f"  {item['snippet']}")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_diag = sub.add_parser("diagnose")
    p_diag.set_defaults(func=diagnose)

    p_fallback = sub.add_parser("fallback")
    p_fallback.add_argument("topic")
    p_fallback.add_argument("--search", default="xiaohongshu,zhihu,bilibili,wechat")
    p_fallback.add_argument("--limit", type=int, default=5)
    p_fallback.set_defaults(func=fallback)

    p_run = sub.add_parser("run")
    p_run.add_argument("topic")
    p_run.add_argument("--search", default="")
    p_run.add_argument("--emit", default="md")
    p_run.add_argument("--deep", action="store_true")
    p_run.add_argument("--quick", action="store_true")
    p_run.add_argument("--as-of")
    p_run.add_argument("--no-fallback", action="store_true")
    p_run.add_argument("--fallback-limit", type=int, default=3)
    p_run.set_defaults(func=run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
