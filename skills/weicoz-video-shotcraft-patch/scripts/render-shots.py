#!/usr/bin/env python3
"""只重渲改动过的镜头，再拼回整片。修复轮次不必全片重渲。

用法：render-shots.py <工程目录> --base out/video-silent-cap.mp4 --out out/video-new.mp4
        --ids s7,s8 [--props '{"captions":true,...}'] [--comp Main] [--crf 18]
        [--entry src/index.ts] [--parts-dir out/parts]
前提：镜头总帧数没变（改了帧数必须全片重渲）。--base 必须用同样的 props 渲出（同画幅、同帧率）。
做法：对每个 id 按 src/timing.ts 的帧区间执行 remotion render --frames=a-b，
再用 ffmpeg 把 base 里未改动的区间与新片段首尾相接，重新编码一次。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# PATH 有 vrender（全局渲染排队）就用它，否则退回直接调用 remotion
RENDER_CMD = ["vrender"] if shutil.which("vrender") else ["npx", "remotion"]


def frames_of(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", video], capture_output=True, text=True, check=True)
    return int(r.stdout.strip().strip(",").split(",")[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--props", default="{}")
    ap.add_argument("--comp", default="Main")
    ap.add_argument("--entry", default="src/index.ts")
    ap.add_argument("--crf", default="18")
    ap.add_argument("--parts-dir", default="out/parts")
    a = ap.parse_args()
    root = Path(a.project).resolve()
    json.loads(a.props)  # 提前校验

    ranges, s = {}, 0
    for m in re.finditer(r"id:\s*'(\w+)'.*?frames:\s*(\d+)", (root / "src/timing.ts").read_text(encoding="utf-8")):
        ranges[m.group(1)] = (s, s + int(m.group(2)) - 1)
        s += int(m.group(2))
    total = s
    want = a.ids.split(",")
    unknown = [i for i in want if i not in ranges]
    if unknown:
        print(f"错误：timing.ts 里没有镜头 {unknown}，可选：{list(ranges)}")
        return 2
    base = Path(a.base) if Path(a.base).is_absolute() else root / a.base
    nb = frames_of(str(base))
    if nb != total:
        print(f"错误：base 有 {nb} 帧，timing.ts 合计 {total} 帧。镜头帧数变了就必须全片重渲。")
        return 2

    # 合并相邻区间，按起点排序
    spans = sorted(ranges[i] for i in want)
    merged = []
    for st, en in spans:
        if merged and st <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(en, merged[-1][1]))
        else:
            merged.append((st, en))

    parts = root / a.parts_dir
    parts.mkdir(parents=True, exist_ok=True)
    part_files = []
    for st, en in merged:
        pf = parts / f"part_{st}_{en}.mp4"
        subprocess.run(RENDER_CMD + ["render", a.entry, a.comp, str(pf), "--muted", f"--crf={a.crf}", f"--frames={st}-{en}", f"--props={a.props}"], cwd=root, check=True)
        if frames_of(str(pf)) != en - st + 1:
            print(f"错误：{pf} 帧数不对。")
            return 2
        part_files.append(pf)

    inputs, chains, labels, cur = ["-i", str(base)], [], [], 0
    for k, ((st, en), pf) in enumerate(zip(merged, part_files), 1):
        if st > cur:
            chains.append(f"[0:v]trim=start_frame={cur}:end_frame={st},setpts=PTS-STARTPTS[b{k}]")
            labels.append(f"[b{k}]")
        inputs += ["-i", str(pf)]
        chains.append(f"[{k}:v]setpts=PTS-STARTPTS[p{k}]")
        labels.append(f"[p{k}]")
        cur = en + 1
    if cur < total:
        chains.append(f"[0:v]trim=start_frame={cur}:end_frame={total},setpts=PTS-STARTPTS[bz]")
        labels.append("[bz]")
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[v]")
    out = Path(a.out) if Path(a.out).is_absolute() else root / a.out
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains), "-map", "[v]", "-c:v", "libx264", "-crf", a.crf, "-pix_fmt", "yuv420p", str(out)], check=True)
    n2 = frames_of(str(out))
    print(f"完成：重渲 {merged}，输出 {out}（{n2} 帧，应为 {total}）")
    return 0 if n2 == total else 1


if __name__ == "__main__":
    sys.exit(main())
