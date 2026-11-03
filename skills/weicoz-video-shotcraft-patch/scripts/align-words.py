#!/usr/bin/env python3
"""字级时间 + 识别回读：给每句旁白算出每个字的开始和结束时间，并把旁白识别回文字与配音稿逐字比对。

用法：align-words.py <工程目录> [--segs seg01,seg03] [--accept]
      align-words.py <工程目录> --find seg03 推成 [--fps 30]   # 查词的帧号，写镜头 BEATS 用
读：vo/cues/segNN.json（每句起止与文字）、public/audio/vo/segNN.mp3（calibrate-voice.py 生成的段音频）。
写：vo/cues-words/segNN.json：[{cue, text, src, chars: [{c, start, end}]}]，时间相对该段音频，与 vo/cues 同一基准。
做法：按句界从段音频切出每句（前后各留 0.05 秒），交给 weicoz-zero-tts skill 的远端服务（zero_tts.py --align-json）：
  先用 paraformer 识别，按编辑距离映射回配音稿的字；识别与配音稿不一致的句子改用 Qwen3-ForcedAligner 强制对齐。
  不一致的地方列为「回读差异」：可能是 TTS 读错、漏读、多读，也可能是识别误差，必须逐条听过。
退出码：有回读差异且没加 --accept 时为 1（字级时间照常写出）；缺文件或服务失败为 2。
依赖：本机 ffmpeg；weicoz-zero-tts 的远端服务（ZERO_TTS_API_URL）。本机不装模型。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PAD = 0.05


def find_tts():
    env = os.environ.get("ZERO_TTS_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    for up in Path(__file__).resolve().parents:
        c = up / "weicoz-zero-tts/scripts/zero_tts.py"
        if c.exists():
            return c
    raise SystemExit("错误：找不到 zero_tts.py，设置 ZERO_TTS_SCRIPT 指向 weicoz-zero-tts 的脚本。")


def find_word(root, seg, word, fps):
    """在 vo/cues-words/<seg>.json 里找词，打印每次出现的句号、秒数、段内帧号，以及落在哪个镜头、镜头内帧号。"""
    p = root / "vo/cues-words" / f"{seg}.json"
    if not p.exists():
        print(f"错误：{p.relative_to(root)} 不存在，先跑 align-words.py。")
        return 2
    shots = []
    tp = root / "src/timing.ts"
    if tp.exists():
        for obj in re.findall(r"\{[^{}]*\}", tp.read_text(encoding="utf-8")):
            i = re.search(r"\bid['\"]?\s*:\s*['\"](\w+)['\"]", obj)
            g = re.search(r"\bseg['\"]?\s*:\s*['\"](seg\d+)['\"]", obj)
            t = re.search(r"\bsegStart['\"]?\s*:\s*([\d.]+)", obj)
            n = re.search(r"\bframes['\"]?\s*:\s*(\d+)", obj)
            if i and g and t and n and g.group(1) == seg:
                shots.append((i.group(1), float(t.group(1)), int(n.group(1))))
    hits = 0
    for row in json.loads(p.read_text(encoding="utf-8")):
        text = "".join(c["c"] for c in row["chars"])
        pos, k = text.find(word), 0
        while pos >= 0:
            k += 1
            hits += 1
            t = row["chars"][pos]["start"]
            where = [f"{sid} 第 {round((t - st) * fps)} 帧" for sid, st, n in shots if 0 <= round((t - st) * fps) < n]
            tag = f"cue{row['cue']}@{word}" + (f"#{k}" if k > 1 else "")
            print(f"{tag}\t{t:.3f}s\t段内第 {round(t * fps)} 帧\t{'；'.join(where) or '（timing.ts 里没有覆盖它的镜头）'}\t{row['text'][:24]}")
            pos = text.find(word, pos + 1)
    if not hits:
        print(f"{seg} 里没有找到「{word}」（按配音稿查：数字写中文，如「三积分」）。")
        return 1
    print("把注释写成上面第一列（如 cue3@推成），帧号填镜头内帧号；check-sync.py 会按字级时间核对。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--find", nargs=2, metavar=("SEG", "词"), help="查词在段内与镜头内的帧号，不做对齐")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--segs", help="只处理这些段，逗号分隔，如 seg01,seg03")
    ap.add_argument("--accept", action="store_true", help="回读差异已逐条听过、确认无误时加，退出码为 0")
    a = ap.parse_args()
    root = Path(a.project).resolve()
    if a.find:
        return find_word(root, a.find[0], a.find[1], a.fps)
    want = {s.strip() for s in (a.segs or "").split(",") if s.strip()}
    cue_files = [f for f in sorted((root / "vo/cues").glob("seg*.json")) if not want or f.stem in want]
    if not cue_files:
        print("错误：vo/cues/segNN.json 不存在，先跑 calibrate-voice.py。")
        return 2
    tts = find_tts()
    out_dir = root / "vo/cues-words"
    out_dir.mkdir(parents=True, exist_ok=True)
    diffs = 0
    with tempfile.TemporaryDirectory(prefix="align-words-") as td:
        job, meta = [], {}
        for f in cue_files:
            mp3 = root / "public/audio/vo" / f"{f.stem}.mp3"
            if not mp3.exists():
                print(f"错误：{mp3.relative_to(root)} 不存在，先跑 calibrate-voice.py 生成旁白。")
                return 2
            for i, cue in enumerate(json.loads(f.read_text(encoding="utf-8"))):
                t0 = max(0.0, cue["start"] - PAD)
                wav = Path(td) / f"{f.stem}-{i}.wav"
                r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-to", f"{cue['end'] + PAD:.3f}",
                                    "-i", str(mp3), "-ac", "1", "-ar", "16000", str(wav)], capture_output=True)
                if r.returncode != 0:
                    print(f"错误：切句失败 {f.stem} 第 {i} 句：{r.stderr.decode()[:120]}")
                    return 2
                key = f"{f.stem}#{i}"
                job.append({"id": key, "wav": str(wav), "text": cue["text"]})
                meta[key] = (f.stem, i, cue["text"], t0)
        jp = Path(td) / "job.json"
        jp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        print(f"对齐 {len(job)} 句（{len(cue_files)} 段）……")
        r = subprocess.run([sys.executable, str(tts), "--align-json", str(jp)], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"错误：远端对齐失败：{(r.stderr or r.stdout).strip()[:300]}")
            return 2
        res = json.loads(r.stdout.strip().splitlines()[-1])
    per_seg, src_count = {}, {}
    for key, (seg, i, text, t0) in meta.items():
        x = res.get(key)
        if not x:
            print(f"错误：{seg} 第 {i} 句没有结果。")
            return 2
        src_count[x["src"]] = src_count.get(x["src"], 0) + 1
        per_seg.setdefault(seg, []).append({"cue": i, "text": text, "src": x["src"],
                                            "chars": [{"c": c, "start": round(t0 + s, 3), "end": round(t0 + e, 3)} for c, s, e in x["chars"]]})
        for d in x["diff"]:
            diffs += 1
            print(f"  回读差异 {seg} 第 {i} 句：稿子「{d['script'] or '（无）'}」→ 听成「{d['heard'] or '（无）'}」  {text[:28]}")
    for seg, rows in per_seg.items():
        (out_dir / f"{seg}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 vo/cues-words/（{len(per_seg)} 段）；时间来源：" + "，".join(f"{k} {v} 句" for k, v in src_count.items()))
    if diffs and not a.accept:
        print(f"\n{diffs} 处回读差异：逐条听过。TTS 读错就改稿或写 vo/pronounce.json 后重新合成；确认是识别误差就加 --accept。")
        return 1
    print("回读：没有差异。" if not diffs else f"回读：{diffs} 处差异已确认（--accept）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
