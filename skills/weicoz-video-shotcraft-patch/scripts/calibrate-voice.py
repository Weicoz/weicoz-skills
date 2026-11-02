#!/usr/bin/env python3
"""用 edge-tts 生成分段旁白，并把语速校准到目标「字/分钟」。

用法：calibrate-voice.py <工程目录> --target 240 [--voice zh-CN-XiaoxiaoNeural] [--tol 2]
        [--rate +5%]  已知语速时直接生成，不校准
        [--dry-run]   只写到临时目录，不动工程里的旁白、清单、句界
读：vo/script/segNN.txt（每段口播正文）。
写：public/audio/vo/segNN.mp3、vo/cues/segNN.json（每句 start/end 秒，相对该段音频）、
    src/vo-manifest.ts（每段文件名与实测时长）。
字数口径：去掉空白与标点后的字符数（汉字、数字、字母各算一个）。
依赖：edge-tts 命令行、ffprobe。edge-tts 的中文声线只给句级时间，词级时间需要另做对齐。
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PUNCT = re.compile(r"[\s，。！？；：、“”\"（）()—…·,.!?;:]")


def count_chars(text):
    return len(PUNCT.sub("", text))


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def vtt_to_cues(vtt):
    cues = []
    for block in vtt.strip().split("\n\n"):
        lines = block.split("\n")
        m = next((re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", ln) for ln in lines if "-->" in ln), None)
        if not m:
            continue
        g = list(map(int, m.groups()))
        text = "".join(ln for ln in lines if "-->" not in ln and not ln.strip().isdigit())
        cues.append({"start": round(g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, 2), "end": round(g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, 2), "text": text})
    return cues


def generate(scripts, voice, rate, outdir):
    outdir.mkdir(parents=True, exist_ok=True)

    def one(f):
        name = f.stem
        mp3, vtt = outdir / f"{name}.mp3", outdir / f"{name}.vtt"
        subprocess.run(["edge-tts", "--voice", voice, f"--rate={rate}", "--file", str(f), "--write-media", str(mp3), "--write-subtitles", str(vtt)], check=True, capture_output=True)
        return name, duration(mp3)

    with ThreadPoolExecutor(max_workers=4) as ex:
        return dict(ex.map(one, scripts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--target", type=float, required=True, help="目标字/分钟")
    ap.add_argument("--voice", default="zh-CN-XiaoxiaoNeural")
    ap.add_argument("--tol", type=float, default=2.0)
    ap.add_argument("--rate", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.project)
    scripts = sorted((root / "vo/script").glob("seg*.txt"))
    if not scripts:
        print("错误：vo/script/segNN.txt 不存在。")
        return 2
    chars = sum(count_chars(f.read_text(encoding="utf-8")) for f in scripts)
    work = Path(tempfile.mkdtemp(prefix="vo-")) if a.dry_run else root / "public/audio/vo"

    def speed(durs):
        return chars / sum(durs.values()) * 60

    if a.rate:
        rate = a.rate
        durs = generate(scripts, a.voice, rate, work)
    else:
        rate, durs = "+0%", generate(scripts, a.voice, "+0%", work)
        for _ in range(3):
            cur = speed(durs)
            print(f"rate {rate}: {cur:.1f} 字/分钟（目标 {a.target:g}）")
            if abs(cur - a.target) <= a.tol:
                break
            base = int(rate.rstrip("%"))
            nxt = round(((1 + base / 100) * a.target / cur - 1) * 100)
            nxt = max(-50, min(100, nxt))
            if f"{nxt:+d}%" == rate:
                break
            rate = f"{nxt:+d}%"
            durs = generate(scripts, a.voice, rate, work)
    final = speed(durs)
    print(f"最终 rate {rate}：{final:.1f} 字/分钟，共 {chars} 字、{sum(durs.values()):.1f} 秒")
    if a.dry_run:
        print(f"dry-run：文件在 {work}，工程未改动。")
        return 0

    (root / "vo/cues").mkdir(parents=True, exist_ok=True)
    for f in scripts:
        vtt = work / f"{f.stem}.vtt"
        (root / "vo/cues" / f"{f.stem}.json").write_text(json.dumps(vtt_to_cues(vtt.read_text(encoding="utf-8")), ensure_ascii=False, indent=1), encoding="utf-8")
        vtt.unlink()
    rows = "".join(f"  {{file: 'audio/vo/{k}.mp3', seconds: {v:.2f}}},\n" for k, v in sorted(durs.items()))
    (root / "src").mkdir(exist_ok=True)
    (root / "src/vo-manifest.ts").write_text(f"// 由 calibrate-voice.py 生成：{a.voice}，rate {rate}，约 {final:.0f} 字/分钟。\nexport const VO = [\n{rows}] as const;\n", encoding="utf-8")
    print("已写入：public/audio/vo、vo/cues、src/vo-manifest.ts。时间线 src/timing.ts 里的镜头帧数需要按新时长重排。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
