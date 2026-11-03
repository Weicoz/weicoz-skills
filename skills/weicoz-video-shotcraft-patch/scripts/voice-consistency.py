#!/usr/bin/env python3
"""检查整片旁白里有没有「声音变了」的句子，并可重新合成挑最接近的一遍。

零样本 TTS 逐句合成时，个别句子会漂：音高突然升高、音色发亮或发闷，听起来像换了个人。
本脚本读 calibrate-voice.py 的逐句缓存，交给 weicoz-zero-tts skill 的远端服务（zero_tts.py --analyze）算每句的音高中位数和频谱重心，
与整片中位数比较，偏离超过容差的句子列出来。计算在远端 TTS 机器上做，本机不需要 numpy。

用法：voice-consistency.py <工程目录> --voice <音色> [--speed 1.0] [--tol 0.2] [--fix] [--takes 4]
前提：已跑过 calibrate-voice.py（缓存在系统临时目录 calibrate-voice-cache）；weicoz-zero-tts 的远端服务可连（ZERO_TTS_API_URL）。
  默认只报告。--fix 对每个偏离的句子再合成 --takes 遍，连同原来那遍，留下最接近整片中位数的一遍写回缓存；
  之后重跑 calibrate-voice.py（命中缓存，很快）把新句子拼进整片，再重排时间线。
只比较 ≥2 秒的句子：太短的句子音高估计不稳，疑问句尾本来就会升调。
退出码：有偏离且没用 --fix 时为 1。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import statistics
import tempfile
from pathlib import Path

CACHE = Path(tempfile.gettempdir()) / "calibrate-voice-cache"
SENT = re.compile(r"[^。！？!?\n]+[。！？!?]*[”’）)」』】》]*")
WORD = re.compile(r"[一-鿿A-Za-z0-9]")


def key(voice, speed, sent):
    return hashlib.sha1(f"{voice}|{speed:.3f}|{os.environ.get('ZERO_TTS_CLARITY', '')}|{sent}".encode()).hexdigest()[:16]


def profiles(tts, paths):
    """远端算每个文件的 {f0, centroid, dur}；返回与 paths 同序的列表。"""
    if not paths:
        return []
    r = subprocess.run([sys.executable, str(tts), "--analyze", *map(str, paths)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"错误：远端分析失败：{(r.stderr or r.stdout).strip()[:200]}")
    out = json.loads(r.stdout.strip().splitlines()[-1])
    return [out.get(str(p)) or {"f0": 0.0, "centroid": 0.0, "dur": 0.0} for p in paths]


def find_tts():
    env = os.environ.get("ZERO_TTS_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    here = Path(__file__).resolve()
    for up in here.parents:
        c = up / "weicoz-zero-tts/scripts/zero_tts.py"
        if c.exists():
            return c
    raise SystemExit("错误：找不到 zero_tts.py，设置 ZERO_TTS_SCRIPT。")


def dist(p, ref):
    return abs(p["f0"] / ref["f0"] - 1) + 0.5 * abs(p["centroid"] / ref["centroid"] - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--src", default="vo/script")
    ap.add_argument("--tol", type=float, default=0.2, help="音高相对整片中位数的容许偏离，默认 0.2（20%%）")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--takes", type=int, default=4)
    a = ap.parse_args()
    tts = find_tts()
    rows = []
    for f in sorted((Path(a.project) / a.src).glob("seg*.txt")):
        for i, s in enumerate(x.strip() for x in SENT.findall(f.read_text(encoding="utf-8")) if WORD.search(x)):
            p = CACHE / f"{key(a.voice, a.speed, s)}.wav"
            if p.exists():
                rows.append((f.stem, i, s, p))
    rows = [r + (pr,) for r, pr in zip(rows, profiles(tts, [r[3] for r in rows]))]
    long_ = [r for r in rows if r[4]["dur"] >= 2.0 and r[4]["f0"] > 0]
    if len(long_) < 5:
        print("错误：缓存里可比较的句子太少，先跑 calibrate-voice.py（音色、倍率、ZERO_TTS_CLARITY 要一致）。")
        return 2
    ref = {"f0": statistics.median(r[4]["f0"] for r in long_), "centroid": statistics.median(r[4]["centroid"] for r in long_)}
    print(f"整片中位数：音高 {ref['f0']:.0f} Hz，频谱重心 {ref['centroid']:.0f} Hz（{len(long_)} 句参与）")
    bad = [r for r in long_ if abs(r[4]["f0"] / ref["f0"] - 1) > a.tol or abs(r[4]["centroid"] / ref["centroid"] - 1) > 0.5]
    for seg, i, s, p, pr in bad:
        print(f"  偏离：{seg} 第 {i} 句 音高 {pr['f0']:.0f}（{pr['f0'] / ref['f0'] - 1:+.0%}）重心 {pr['centroid']:.0f}（{pr['centroid'] / ref['centroid'] - 1:+.0%}）  {s[:24]}")
    if not bad:
        print("没有偏离的句子。")
        return 0
    if not a.fix:
        print(f"\n{len(bad)} 句偏离。加 --fix 重新合成挑最接近的一遍，或改写这些句子。")
        return 1
    for seg, i, s, p, pr in bad:
        best, best_d = p, dist(pr, ref)
        takes = []
        for t in range(a.takes):
            q = CACHE / f"take-{p.stem}-{t}.wav"
            r = subprocess.run([sys.executable, str(tts), s, "-v", a.voice, "-o", str(q), "--no-play", "--speed", f"{a.speed:.3f}"], capture_output=True, text=True, timeout=300)
            if r.returncode != 0 or not q.exists():
                print(f"  {seg} 第 {i} 句第 {t + 1} 遍合成失败：{(r.stderr or r.stdout).strip()[:120]}")
                continue
            takes.append(q)
        for q, qp in zip(takes, profiles(tts, takes)):
            d = dist(qp, ref)
            if d < best_d:
                best, best_d = q, d
        if best != p:
            os.replace(best, p)
        for q in CACHE.glob(f"take-{p.stem}-*.wav"):
            q.unlink()
        now = profiles(tts, [p])[0]
        print(f"  {seg} 第 {i} 句 → 音高 {now['f0']:.0f}（{now['f0'] / ref['f0'] - 1:+.0%}）重心 {now['centroid']:.0f}")
    print("\n完成。重跑 calibrate-voice.py（命中缓存）把新句子拼进整片，再重排时间线、抽听这几句。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
