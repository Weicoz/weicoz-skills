#!/usr/bin/env python3
"""生成分段旁白，并把语速校准到目标「字/分钟」。支持两个引擎。

用法：calibrate-voice.py <工程目录> --target 240 [--engine zero-tts|edge] [--tol 5]
        [--engine]         默认：设置了 ZERO_TTS_API_URL 用 zero-tts，否则用 edge
        [--voice <声线>]   zero-tts 默认读 ZERO_TTS_DEFAULT_VOICE，再退到 sunday；edge 默认 zh-CN-XiaoxiaoNeural
        [--tol N]            容差（字/分钟）。edge 默认 2；zero-tts 默认 5（同一速度两次生成时长会差约 ±3%）
        [--rate +5%]       edge：已知语速时直接生成，不校准
        [--speed 1.1]      zero-tts：已知语速倍率时直接生成，不校准
        [--gap 0.15]       zero-tts：句与句之间补的静音秒数
        [--sample-chars 300]  zero-tts：先在不超过约这么多字的样本上校准速度，再整片生成一次（远端 GPU 慢，整片生成要等几分钟到十几分钟）
        [--timeout 300]    zero-tts：单句合成的超时秒数
        [--dry-run]        只写到临时目录，不动工程里的旁白、清单、句界

引擎：
  zero-tts  主力。调用 weicoz-zero-tts 的 zero_tts.py（远端 GPU 的 Qwen3-TTS 服务）。该引擎不给时间戳，
            所以按句子逐句合成、量时长、补静音拼接，句界由累加得到。脚本位置用环境变量
            ZERO_TTS_SCRIPT 指定，未设置时在本仓库的 skills/weicoz-zero-tts/scripts/ 里找；
            端点、音色与参考音频的细节以 weicoz-zero-tts 为准。
  edge      兜底。edge-tts 命令行，一次生成整段并拿到句界（vtt）；zero-tts 不可用时试听、定时间线。
读：vo/script/segNN.txt（每段口播正文）。
写：public/audio/vo/segNN.mp3、vo/cues/segNN.json（每句 start/end 秒，相对该段音频）、
    src/vo-manifest.ts（每段文件名与实测时长）。
字数口径：去掉空白与标点后的字符数（汉字、数字、字母各算一个）。
依赖：ffprobe；zero-tts 需要 ZERO_TTS_API_URL，edge 需要 edge-tts 命令行。两个引擎都只给句级时间，词级时间需要另做对齐。
"""
import argparse
import json
import os
import re
import hashlib
import subprocess
import time
import sys
import shutil
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


class UserError(Exception):
    """可预期的用法或环境错误：打印一行说明，退出码 2。"""


CLOSERS = "”’）)」』】》"
SENT = re.compile(r"[^。！？!?\n]+[。！？!?]*[" + CLOSERS + r"]*")
WORD = re.compile(r"[一-鿿A-Za-z0-9]")


def split_sentences(text):
    """按 。！？ 与换行切句；句末的引号、括号并入前一句；没有文字的碎片丢弃。"""
    return [x.strip() for x in SENT.findall(text) if x.strip() and WORD.search(x)]


def find_zero_tts():
    env = os.environ.get("ZERO_TTS_SCRIPT")
    if env:
        if not Path(env).exists():
            raise UserError(f"ZERO_TTS_SCRIPT 指向的文件不存在：{env}")
        return Path(env)
    here = Path(__file__).resolve()
    for up in range(2, 6):  # skills/<本 skill>/scripts/ → skills/
        cand = here.parents[up - 1] / "weicoz-zero-tts/scripts/zero_tts.py"
        if cand.exists():
            return cand
    raise UserError("找不到 zero_tts.py。设置 ZERO_TTS_SCRIPT 指向它，或把 weicoz-zero-tts 放在本 skill 同级目录。")


def wav_format(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    sr, ch = r.stdout.strip().split(",")[:2]
    return int(sr), int(ch)


CACHE = Path(tempfile.gettempdir()) / "calibrate-voice-cache"
RETRIES, RETRY_WAIT = 5, 60


def synth_sentences(stem, sents, tts, voice, speed, gap, tmp, out_mp3, timeout):
    """逐句合成并拼接成一段 mp3，返回（时长秒，句界列表）。中间文件只放在 tmp。"""
    work = tmp / f"{stem}_parts"
    work.mkdir(parents=True, exist_ok=True)
    wavs, durs = [], []
    CACHE.mkdir(parents=True, exist_ok=True)
    for i, sent in enumerate(sents):
        key = hashlib.sha1(f"{voice}|{speed:.3f}|{os.environ.get('ZERO_TTS_CLARITY', '')}|{sent}".encode()).hexdigest()[:16]
        wav = CACHE / f"{key}.wav"  # 已合成的句子直接复用，服务中途掉线后重跑不必从头来
        for attempt in range(RETRIES + 1):
            if wav.exists():
                break
            part = wav.with_suffix(".part.wav")
            try:
                r = subprocess.run([sys.executable, str(tts), sent, "-v", voice, "-o", str(part), "--no-play", "--speed", f"{speed:.3f}"], capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                r = None
            if r is not None and r.returncode == 0 and part.exists():
                part.rename(wav)
                break
            if attempt < RETRIES and (r is None or "无法连接" in (r.stderr + r.stdout)):  # 只重试超时与连不上，参数类错误立刻报
                print(f"  {stem} 第 {i} 句合成失败，{RETRY_WAIT} 秒后重试（{attempt + 1}/{RETRIES}）", flush=True)
                time.sleep(RETRY_WAIT)
        if not wav.exists():
            raise RuntimeError(f"zero-tts 合成失败（{stem} 第 {i} 句，已重试 {RETRIES} 次；已合成的句子缓存在 {CACHE}，服务恢复后重跑会接着做）")
        wavs.append(wav)
        durs.append(duration(wav))
    sr, ch = wav_format(wavs[0])  # 静音与句子音频同采样率、声道，concat 才不会出杂音
    sil = work / "gap.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl={'mono' if ch == 1 else 'stereo'}", "-t", f"{gap}", str(sil)], check=True)
    rows = []
    for i, w in enumerate(wavs):
        rows.append(f"file '{w.resolve()}'")
        if i < len(wavs) - 1 and gap > 0:
            rows.append(f"file '{sil.resolve()}'")
    listing = work / "list.txt"
    listing.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)], check=True)
    cues, t = [], 0.0
    for sent, d in zip(sents, durs):
        cues.append({"start": round(t, 2), "end": round(t + d, 2), "text": sent})
        t += d + gap
    return duration(out_mp3), cues


def generate_zero(segments, tts, voice, speed, gap, outdir, tmp, timeout):
    """segments: [(stem, 句子列表)]。远端 GPU 顺序合成，避免并发占满显存。"""
    out, cues = {}, {}
    for stem, sents in segments:
        out[stem], cues[stem] = synth_sentences(stem, sents, tts, voice, speed, gap, tmp, outdir / f"{stem}.mp3", timeout)
    return out, cues


def calibrate_zero(segments, tts, voice, gap, target, tol, sample_chars, tmp, timeout):
    """在样本上用割线法找 --speed。模型每次采样的自然时长有波动，倍率与字/分钟不严格成正比，不能只按比例调。"""
    sample, n = [], 0
    for stem, sents in segments:
        take = []
        for sent in sents:
            if n >= sample_chars:
                break
            take.append(sent)
            n += count_chars(sent)
        if take:
            sample.append((stem, take))
        if n >= sample_chars:
            break
    hist, speed = [], 1.0
    for _ in range(5):
        durs, _c = generate_zero(sample, tts, voice, speed, gap, tmp / "_sample", tmp, timeout)
        cur = n / sum(durs.values()) * 60
        hist.append((speed, cur))
        print(f"样本 {n} 字，speed {speed:.3f}：{cur:.1f} 字/分钟（目标 {target:g}）")
        if abs(cur - target) <= tol:
            break
        if len(hist) >= 2 and hist[-1][0] != hist[-2][0] and (hist[-1][1] - hist[-2][1]) / (hist[-1][0] - hist[-2][0]) > 0:
            slope = (hist[-1][1] - hist[-2][1]) / (hist[-1][0] - hist[-2][0])
            nxt = speed + (target - cur) / slope
        else:
            nxt = speed * target / cur
        new = max(0.6, min(1.6, nxt))
        if abs(new - speed) < 1e-3:
            print(f"警告：speed 已到 {speed:.2f} 的上下限，目标 {target:g} 字/分钟可能达不到。")
            break
        speed = new
    return speed, hist


def generate(scripts, voice, rate, outdir):
    outdir.mkdir(parents=True, exist_ok=True)

    def one(f):
        name = f.stem
        mp3, vtt = outdir / f"{name}.mp3", outdir / f"{name}.vtt"
        subprocess.run(["edge-tts", "--voice", voice, f"--rate={rate}", "--file", str(f), "--write-media", str(mp3), "--write-subtitles", str(vtt)], check=True, capture_output=True)
        return name, duration(mp3)

    with ThreadPoolExecutor(max_workers=4) as ex:
        return dict(ex.map(one, scripts))


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--target", type=float, required=True, help="目标字/分钟")
    ap.add_argument("--engine", choices=["zero-tts", "edge"], default=None, help="默认：设置了 ZERO_TTS_API_URL 用 zero-tts，否则用 edge")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--speed", type=float, default=None, help="zero-tts 的语速倍率（0.5–2.0，服务端范围）")
    ap.add_argument("--gap", type=float, default=0.15)
    ap.add_argument("--sample-chars", type=int, default=300, help="zero-tts 校准样本的字数上限")
    ap.add_argument("--timeout", type=int, default=300, help="zero-tts 单句合成超时秒数")
    ap.add_argument("--tol", type=float, default=None, help="容差（字/分钟）。edge 默认 2；zero-tts 默认 5，因为同一速度重复生成的时长有波动")
    ap.add_argument("--rate", default=None, help="edge 的语速，如 +5%%")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.engine is None:
        a.engine = "zero-tts" if os.environ.get("ZERO_TTS_API_URL") else "edge"
        print(f"引擎：{a.engine}（未指定 --engine，按 ZERO_TTS_API_URL {'已' if a.engine == 'zero-tts' else '未'}设置选择）")
    if a.tol is None:
        a.tol = 2.0 if a.engine == "edge" else 5.0
    if a.voice is None:
        a.voice = "zh-CN-XiaoxiaoNeural" if a.engine == "edge" else os.environ.get("ZERO_TTS_DEFAULT_VOICE", "sunday")
    if a.speed is not None and not (0.5 <= a.speed <= 2.0):
        raise UserError("--speed 需要在 0.5 到 2.0 之间（zero-tts 服务端范围）。")
    if a.engine == "edge" and a.speed is not None:
        print("提示：--speed 只对 zero-tts 生效，已忽略。")
    if a.engine == "zero-tts" and a.rate:
        print("提示：--rate 只对 edge 生效，已忽略。")
    root = Path(a.project)
    scripts = sorted((root / "vo/script").glob("seg*.txt"))
    if not scripts:
        raise UserError("vo/script/segNN.txt 不存在。")
    chars = sum(count_chars(f.read_text(encoding="utf-8")) for f in scripts)
    work = Path(tempfile.mkdtemp(prefix="vo-")) if a.dry_run else root / "public/audio/vo"
    work.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vo-tmp-"))  # 合成的中间文件只放这里，结束时清理，不进工程的 public/

    def speed_of(durs, n=None):
        return (n or chars) / sum(durs.values()) * 60

    try:
        cues_by_seg = None
        if a.engine == "zero-tts":
            tts = find_zero_tts()
            if not os.environ.get("ZERO_TTS_API_URL"):
                print("提示：未设置 ZERO_TTS_API_URL，zero_tts.py 会回退到本机回环地址；远端服务请先设置，见 weicoz-zero-tts。")
            segments = [(f.stem, split_sentences(f.read_text(encoding="utf-8"))) for f in scripts]
            slope = None
            if a.speed:
                speed = a.speed
            else:
                speed, hist = calibrate_zero(segments, tts, a.voice, a.gap, a.target, a.tol, a.sample_chars, tmp, a.timeout)
                if len(hist) >= 2 and hist[-1][0] != hist[-2][0]:
                    slope = (hist[-1][1] - hist[-2][1]) / (hist[-1][0] - hist[-2][0])
            durs, cues_by_seg = generate_zero(segments, tts, a.voice, speed, a.gap, work, tmp, a.timeout)
            cur = speed_of(durs)
            print(f"整片 speed {speed:.3f}：{cur:.1f} 字/分钟（目标 {a.target:g}）")
            if not a.speed and abs(cur - a.target) > 2 * a.tol and slope and slope > 0:
                speed = max(0.6, min(1.6, speed + (a.target - cur) / slope))  # 偏差超过两倍容差才修正一次；小偏差属于生成波动
                durs, cues_by_seg = generate_zero(segments, tts, a.voice, speed, a.gap, work, tmp, a.timeout)
                print(f"整片 speed {speed:.3f}：{speed_of(durs):.1f} 字/分钟")
            rate = f"speed {speed:.3f}"
        elif a.rate:
            rate = a.rate
            durs = generate(scripts, a.voice, rate, work)
        else:
            rate, durs = "+0%", generate(scripts, a.voice, "+0%", work)
            for _ in range(3):
                cur = speed_of(durs)
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    final = speed_of(durs)
    print(f"最终 rate {rate}：{final:.1f} 字/分钟，共 {chars} 字、{sum(durs.values()):.1f} 秒")
    if abs(final - a.target) > 2 * a.tol:
        print(f"警告：最终 {final:.0f} 字/分钟，偏离目标 {a.target:g} 较多。")
    if a.dry_run:
        print(f"dry-run：文件在 {work}，工程未改动。")
        return 0

    (root / "vo/cues").mkdir(parents=True, exist_ok=True)
    for f in scripts:
        if cues_by_seg is not None:
            data = cues_by_seg[f.stem]
        else:
            vtt = work / f"{f.stem}.vtt"
            data = vtt_to_cues(vtt.read_text(encoding="utf-8"))
            vtt.unlink()
        (root / "vo/cues" / f"{f.stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = "".join(f"  {{file: 'audio/vo/{k}.mp3', seconds: {v:.2f}}},\n" for k, v in sorted(durs.items()))
    (root / "src").mkdir(exist_ok=True)
    (root / "src/vo-manifest.ts").write_text(f"// 由 calibrate-voice.py 生成：{a.engine}，{a.voice}，{rate}，约 {final:.0f} 字/分钟。\nexport const VO = [\n{rows}] as const;\n", encoding="utf-8")
    print("已写入：public/audio/vo、vo/cues、src/vo-manifest.ts。时间线 src/timing.ts 里的镜头帧数需要按新时长重排。")
    return 0


def main():
    try:
        return run()
    except UserError as e:
        print(f"错误：{e}")
        return 2
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"错误：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
