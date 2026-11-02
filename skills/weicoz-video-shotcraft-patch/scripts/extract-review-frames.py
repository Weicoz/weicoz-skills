#!/usr/bin/env python3
"""给审查员备好证据：每镜头一张联系表 + 每句旁白的全局帧号表。

用法：extract-review-frames.py <工程目录> <成片.mp4> <输出目录>
        [--positions 0.05,0.25,0.5,0.75,0.97] [--tile-width 640]
读：src/timing.ts（镜头 id、frames）、vo/cues/segNN.json（每句 start/end 秒，相对该段音频）。
写：<输出目录>/sheet_<镜头id>.png、cues_global.txt。依赖 ffmpeg。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FPS = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("outdir")
    ap.add_argument("--positions", default="0.05,0.25,0.5,0.75,0.97")
    ap.add_argument("--tile-width", type=int, default=640)
    a = ap.parse_args()
    root, out = Path(a.project), Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    pos = [float(x) for x in a.positions.split(",")]

    shots, s = [], 0
    for m in re.finditer(r"id:\s*'(\w+)',\s*seg:\s*'(seg\d+)'.*?segStart:\s*([\d.]+).*?frames:\s*(\d+)", (root / "src/timing.ts").read_text(encoding="utf-8")):
        sid, seg, seg_start, fr = m.group(1), m.group(2), float(m.group(3)), int(m.group(4))
        shots.append((sid, seg, seg_start, s, fr))
        s += fr

    seg_first = {}
    for sid, seg, _, start, _ in shots:
        seg_first.setdefault(seg, start)  # 每段旁白从该段第一个镜头起点开始播放

    lines = ["全局帧\t时间码\t镜头\t句子"]
    for seg, start in seg_first.items():
        p = root / "vo/cues" / f"{seg}.json"
        if not p.exists():
            continue
        for c in json.loads(p.read_text(encoding="utf-8")):
            f = start + round(c["start"] * FPS)
            sid = next((x[0] for x in shots if x[3] <= f < x[3] + x[4]), "?")
            lines.append(f"{f}\t{f/FPS:.1f}s\t{sid}\t{c['text']}")
    (out / "cues_global.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for sid, _, _, start, fr in shots:
        sel = "+".join(f"eq(n,{start + min(fr - 1, int(fr * p))})" for p in pos)
        vf = f"select='{sel}',scale={a.tile_width}:-1,tile={len(pos)}x1"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", vf, "-frames:v", "1", str(out / f"sheet_{sid}.png")], check=True)
    print(f"完成：{len(shots)} 张联系表，{len(lines) - 1} 句旁白帧号 → {out}")


if __name__ == "__main__":
    sys.exit(main())
