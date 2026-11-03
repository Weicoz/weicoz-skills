#!/usr/bin/env python3
"""真实素材检查：public/media 与 media/sources.json 对账、许可、编码、署名、盗链。

用法：check-media.py <工程目录> [--fps 30] [--allow-sa]
错误：public/media 下的文件不在 sources.json；许可不合（NC/ND/unknown，SA 未加 --allow-sa）；
      视频不是 H.264 或帧率不等于 --fps；需署名条目但 media/CREDITS.md 缺失或未包含该条目；
      src/ 的 .ts/.tsx 里有 http(s) 图片或视频地址（盗链）；src/ 引用的 media/ 文件不在 sources.json。
警告：条目对应文件缺失（跑 media-source.py fetch）；照片或视频宽度小于 1920。
没有 public/media 也没有 sources.json 时打印「本工程没有真实素材」并退出 0。
退出码：0 通过；1 有错误；2 工程结构不对。
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("media_source", HERE / "media-source.py")
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)

MEDIA_EXT = r"(?:jpe?g|png|webp|gif|avif|mp4|webm|mov|mkv|ogv)"
URL_RE = re.compile(r"https?://[^\s'\"`)<>]+?\." + MEDIA_EXT + r"\b", re.I)
REF_RE = re.compile(r"""['"`(]/?(media/[^'"`)\s$]+?\.""" + MEDIA_EXT + r")\b", re.I)
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".ogv"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--allow-sa", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.project).resolve()
    if not root.is_dir():
        print(f"错误：工程目录不存在：{root}", file=sys.stderr)
        return 2
    pub = root / "public" / "media"
    sj = root / "media" / "sources.json"
    if not pub.exists() and not sj.exists():
        print("本工程没有真实素材")
        return 0
    items = []
    if sj.exists():
        try:
            items = json.loads(sj.read_text(encoding="utf-8"))
            assert isinstance(items, list)
        except (ValueError, AssertionError):
            print(f"错误：sources.json 不是有效的数组：{sj}", file=sys.stderr)
            return 2
    errors, warns = [], []
    files = {e.get("file") for e in items}

    if pub.exists():
        for p in sorted(pub.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(root / "public").as_posix()
                if rel not in files:
                    errors.append(f"{rel} 不在 sources.json（来源不明的素材不能入片）")

    credits = root / "media" / "CREDITS.md"
    ctext = credits.read_text(encoding="utf-8") if credits.exists() else None
    ffok = True
    try:
        ms.need_ff()
    except ms.Usage as e:
        ffok = False
        warns.append(f"跳过编码检查：{e}")
    for e in items:
        f = e.get("file", "?")
        lic = e.get("license", "unknown")
        if not ms.license_ok(lic, a.allow_sa):
            errors.append(f"{f} 许可 {lic} 不合策略" + ("（SA 需 --allow-sa）" if lic.startswith("cc-by-sa") else ""))
        if lic.startswith("cc-by") or lic == "unsplash":
            if ctext is None:
                errors.append(f"{f} 需署名，但 media/CREDITS.md 缺失（跑 media-source.py credits）")
            elif f not in ctext:
                errors.append(f"{f} 需署名，但 media/CREDITS.md 没有包含它（重跑 media-source.py credits）")
        p = root / "public" / f
        if not p.exists():
            warns.append(f"{f} 文件缺失（跑 media-source.py fetch 复原）")
            continue
        if not ffok:
            continue
        try:
            info = ms.probe(p)
        except ms.Fail as ex:
            errors.append(f"{f} 无法读取：{ex}")
            continue
        if p.suffix.lower() in VIDEO_EXT:
            if info["codec"] != "h264":
                errors.append(f"{f} 编码是 {info['codec']}，必须是 H.264")
            if info["fps"] is None or abs(info["fps"] - a.fps) > 0.01:
                errors.append(f"{f} 帧率 {info['fps']}，必须是 {a.fps}")
        if (info["w"] or 0) < 1920:
            warns.append(f"{f} 宽度 {info['w']} < 1920（质量优先；只做小图展示时可忽略）")

    src = root / "src"
    if src.exists():
        for p in sorted(list(src.rglob("*.ts")) + list(src.rglob("*.tsx"))):
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(root).as_posix()
            for m in URL_RE.finditer(text):
                errors.append(f"{rel} 盗链外部素材地址：{m.group(0)}（必须下载到 public/media）")
            for m in REF_RE.finditer(text):
                if m.group(1) not in files:
                    errors.append(f"{rel} 引用 {m.group(1)}，但它不在 sources.json")

    for w in warns:
        print(f"警告：{w}")
    for e in errors:
        print(f"错误：{e}")
    print(f"汇总：{len(errors)} 个错误，{len(warns)} 个警告，{len(items)} 条素材记录")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
