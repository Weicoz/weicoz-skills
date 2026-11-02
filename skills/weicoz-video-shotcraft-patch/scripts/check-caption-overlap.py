#!/usr/bin/env python3
"""字幕遮挡检查：字幕在场的帧里，字幕条区域内有没有画面内容（文字、数字、图标）。

在「无字幕」的画面里取字幕条区域，找内容色像素；水波、背景不算。
用法：check-caption-overlap.py <工程目录> --plain out/video-silent.mp4
        [--captions src/captions-data.ts] [--y0 946] [--y1 1034]
        [--colors 17324d,ff8a3d,ffc24b] [--step 12] [--min-px 8] [--tol 48]
captions 文件里每条字幕写成 {a: 起始帧, b: 结束帧, ...}（全局帧号）。
退出码：发现遮挡返回 1。依赖：ffmpeg；有 numpy 时更快，没有也能跑。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:  # 纯 Python 回退
    np = None

W_SMALL = 480  # 区域横向缩到 480 像素宽，只数色块，不求精确


def hex_rgb(h):
    h = h.strip().lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def load_timing(root):
    p = root / "src/timing.ts"
    if not p.exists():
        return []
    out, s = [], 0
    for m in re.finditer(r"id:\s*'(\w+)'.*?frames:\s*(\d+)", p.read_text(encoding="utf-8")):
        out.append((m.group(1), s, s + int(m.group(2))))
        s += int(m.group(2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--plain", required=True, help="不带字幕的画面视频")
    ap.add_argument("--captions", default="src/captions-data.ts")
    ap.add_argument("--y0", type=int, default=946)
    ap.add_argument("--y1", type=int, default=1034)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--colors", default="17324d,ff8a3d,ffc24b")
    ap.add_argument("--step", type=int, default=12)
    ap.add_argument("--min-px", type=int, default=8)
    ap.add_argument("--tol", type=int, default=48)
    a = ap.parse_args()
    root = Path(a.project)

    caps = [(int(x), int(y)) for x, y in re.findall(r"\ba:\s*(\d+),\s*b:\s*(\d+)", (root / a.captions).read_text(encoding="utf-8"))]
    if not caps:
        print("错误：字幕文件里没有读到 {a:, b:}。")
        return 2
    shots = load_timing(root)
    cols = [hex_rgb(c) for c in a.colors.split(",")]
    h = a.y1 - a.y0
    hs = max(1, round(h * W_SMALL / a.width))
    vf = f"select='not(mod(n,{a.step}))',crop={a.width}:{h}:0:{a.y0},scale={W_SMALL}:{hs}"
    cmd = ["ffmpeg", "-v", "error", "-i", a.plain, "-vf", vf, "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    fsize = W_SMALL * hs * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    idx, flagged, checked = 0, [], 0
    while True:
        buf = proc.stdout.read(fsize)
        if len(buf) < fsize:
            break
        frame = idx * a.step
        idx += 1
        if not any(s <= frame < e for s, e in caps):
            continue
        checked += 1
        if np is not None:
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(-1, 3).astype(int)
            n = 0
            for c in cols:
                n += int((np.abs(arr - np.array(c)).sum(axis=1) <= a.tol).sum())
        else:
            n = 0
            for i in range(0, fsize, 3):
                px = buf[i : i + 3]
                if any(sum(abs(px[k] - c[k]) for k in range(3)) <= a.tol for c in cols):
                    n += 1
        if n >= a.min_px:
            flagged.append((frame, n))
    proc.wait()

    def shot_of(f):
        return next((i for i, s, e in shots if s <= f < e), "?")

    print(f"字幕在场的采样帧：{checked}，疑似遮挡：{len(flagged)}（区域 y {a.y0}–{a.y1}，阈值 {a.min_px} 个缩小像素）")
    by = {}
    for f, n in flagged:
        by.setdefault(shot_of(f), []).append((f, n))
    for sid, lst in by.items():
        ex = ", ".join(f"帧{f}({f/30:.1f}s,{n}px)" for f, n in lst[:4])
        print(f"  {sid}：{len(lst)} 处，例：{ex}")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
