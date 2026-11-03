#!/usr/bin/env python3
"""录制真实接口响应，存为解析测试的样例。

用法：record_fixtures.py [--q "water bottle"] [--per 3]
读：环境变量 PEXELS_API_KEY / PIXABAY_API_KEY / UNSPLASH_ACCESS_KEY（没设的来源跳过；Wikimedia 不需要）。
写：tests/fixtures/recorded/<source>_<kind>.json（原始响应体，不含请求地址与 Key；响应里出现 Key 值则拒绝写入）。
退出码：0 完成；1 有来源失败。
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("media_source", HERE.parent / "media-source.py")
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)

OUT = HERE / "fixtures" / "recorded"
PLAN = [("pexels", "photo"), ("pexels", "video"), ("pixabay", "photo"), ("pixabay", "video"),
        ("unsplash", "photo"), ("wikimedia", "photo"), ("wikimedia", "video")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", default="water bottle")
    ap.add_argument("--per", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = {}
    real = ms.http_json
    ms.http_json = lambda url, headers=None: raw.setdefault("body", real(url, headers))
    bad = 0
    for src, kind in PLAN:
        raw.clear()
        try:
            ms.api_search(src, a.q, kind, None, a.per)
        except ms.Usage:
            print(f"跳过 {src}_{kind}：未配置 Key")
            continue
        except ms.Fail as e:
            print(f"失败 {src}_{kind}：{e}")
            bad += 1
            continue
        text = json.dumps(raw["body"], ensure_ascii=False, indent=1)
        key = ms.os.environ.get(ms.KEY_ENV[src], "").strip() if src in ms.KEY_ENV else ""
        if key and key in text:
            print(f"拒绝写入 {src}_{kind}：响应里含 Key")
            bad += 1
            continue
        (OUT / f"{src}_{kind}.json").write_text(text, encoding="utf-8")
        print(f"已录制 {src}_{kind}.json")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
