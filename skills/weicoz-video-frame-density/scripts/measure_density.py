#!/usr/bin/env python3
"""画面密度诊断：逐镜算内容覆盖率、中位亮度、亮度标准差。

用法：
    python3 measure_density.py <帧目录> [--thresh 0.16] [--w 480] [--h 270]
    python3 measure_density.py out/review --group-by shot

帧命名约定：<镜号>-<标签>-f<帧号>.png，例如 S05-peak-f859.png。
不按该约定时用 --all 逐文件输出。

判定阈值（深色讲解片）：
    覆盖率 < 6%   极空
          6-12%  偏空
         12-20%  正常
          >20%  偏满

中位亮度：纯墨底约 0.04；加氛围层后应到 0.08-0.11。
"""
import argparse
import glob
import os
import re
import subprocess
import sys

import numpy as np


def load_rgb(path: str, w: int, h: int) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0


def verdict(cov: float) -> str:
    if cov < 0.06:
        return "极空"
    if cov < 0.12:
        return "偏空"
    if cov <= 0.20:
        return "正常"
    return "偏满"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("--thresh", type=float, default=0.16, help="亮度阈值，默认 0.16")
    ap.add_argument("--w", type=int, default=480)
    ap.add_argument("--h", type=int, default=270)
    ap.add_argument("--all", action="store_true", help="逐文件输出，不按镜聚合")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.frames, "*.png")))
    if not files:
        print(f"未找到帧：{args.frames}", file=sys.stderr)
        return 1

    rows = []
    for p in files:
        img = load_rgb(p, args.w, args.h)
        lum = img.mean(axis=2)
        cov = float((lum > args.thresh).mean())
        m = re.match(r"([A-Za-z0-9]+)-([a-z]+)-f(\d+)", os.path.basename(p))
        shot = m.group(1) if m else os.path.basename(p)
        rows.append((shot, os.path.basename(p), cov, float(np.median(lum)), float(lum.std())))

    if args.all:
        print(f"{'文件':38s}{'覆盖':>7s}{'中位亮度':>9s}{'标准差':>8s}  判定")
        for _, name, cov, med, sd in rows:
            print(f"{name:38s}{cov*100:6.1f}%{med:9.3f}{sd:8.3f}  {verdict(cov)}")
    else:
        agg = {}
        for shot, _, cov, med, sd in rows:
            agg.setdefault(shot, []).append((cov, med, sd))
        print(f"{'镜':6s}{'覆盖(均)':>9s}{'最低':>7s}{'中位亮度':>9s}  判定")
        for shot, vals in agg.items():
            covs = [v[0] for v in vals]
            meds = [v[1] for v in vals]
            print(f"{shot:6s}{np.mean(covs)*100:8.1f}%{min(covs)*100:6.1f}%"
                  f"{np.mean(meds):9.3f}  {verdict(float(np.mean(covs)))}")

    covs = np.array([r[2] for r in rows])
    meds = np.array([r[3] for r in rows])
    print(f"\n全片中位覆盖率 {np.median(covs)*100:.1f}%  "
          f"中位亮度 {np.median(meds):.3f}  "
          f"极空镜头 {int((covs < 0.06).sum())}/{len(covs)}")
    print("目标：覆盖率 12-16%，中位亮度 0.08-0.11，极空镜头 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
