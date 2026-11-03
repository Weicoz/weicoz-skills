#!/usr/bin/env python3
"""成片音频检查：把听感问题变成测量值，供听不到声音的审查员按数字判。

用法：check-audio.py <工程目录> --out <证据目录> [--final <成片.mp4>] [--comp Main] [--entry src/index.ts]
        [--props '<JSON，基础 props>'] [--stems-dir <目录>] [--skip-asr] [--listen] [--listen-max 16]
读：src/timing.ts（镜头 id、seg、segStart、frames；FPS 读不到默认 30）、vo/cues/segNN.json（句界，秒，相对该段音频）、
    src/Root.tsx（合成的 defaultProps 必须含 vo、sfx、bgm 三个开关）、成片 mp4 的音轨（--final）。
写：<证据目录>/stems/{vo,bed,mix}.wav、audio-report.json、audio-report.md、clips/named/（黄红句的 mix 切片 mp3）、--listen 时另有 listen-key.json。
做法：
  1 分轨：在工程目录用 remotion 渲 vo.wav（vo 开，sfx/bgm 关）与 bed.wav（vo 关，sfx/bgm 开），并行；
    mix 取 --final 的音轨，没给 --final 就再渲一条全开的 mix.wav。--stems-dir 里已有分轨时跳过渲染。
  2 响度（mix，ebur128）：I 在 [-16,-12] LUFS 外黄（平台会做响度归一，不判红）；真峰值 > -1 dBTP 黄、> 0 红（削波）。
  3 逐句 vo−bed：句窗内每 0.05 秒一块，只取有人声的块（vo > -45 dBFS），逐块算 vo 减 bed（dB）。
    中位数 < 10 dB 或背景比旁白响的块 ≥ 25% 记黄；中位数 < 0 dB（背景大部分时间比旁白响）记红；bed < -60 dBFS 记「无背景」。
    声学测量只是间接证据：只按它判红要求背景压倒性地响，其余由第 4 项识别确认。
    阈值来自 qinglan-water 实测：93 句中位数的中位数 16.9 dB，句首叠转场音效的 5 句落在 3–10 dB，识别与试听都能听清。
  4 可懂度（远端识别，可 --skip-asr）：每句 mix 与 vo 各识别一次，mix 比 vo 多错 2 字记黄，多错 ≥3 字或多错的字 ≥ 句长 15% 记红「成片里听不清」。
    远端失败或没设 ZERO_TTS_API_URL：标「未验证」，不报错退出。
  5 静音与接缝：mix 连续 > 2.0 秒低于 -50 dBFS 记黄；每段旁白起止 ±30 ms 内 vo 相邻样本差最大值 > 0.5 记黄「疑似爆音」。
  --listen：挑最多 --listen-max 个片段（黄红句 > 每段首句与中间句 > 段接缝前后各 1.5 秒），每 8 个交给 agy（Gemini）盲听：
    agy 的工作目录是工程外的系统临时目录，结束后删除，里面只有 c01.mp3… 和每批 1 段 pink 噪声对照，不放稿子；映射在 <证据目录>/listen-key.json。
    脚本自己用 difflib 比 transcript 与稿子（差异率 > 30% 记黄）；对照被当成人声则整批作废并标未验证。
    带镜头名的试听片段在 clips/named/。结果写进报告「Gemini 试听（参考）」，不影响退出码。环境变量：CHECK_AUDIO_AGY（默认 agy）、
    CHECK_AUDIO_LISTEN_MODEL（默认 gemini-3.8-flash-low）、CHECK_AUDIO_LISTEN_EFFORT（默认 low）。
退出码：0 无红；1 有红；2 输入缺失或渲染失败。
依赖：ffmpeg / ffprobe；渲染分轨需要工程里的 npx remotion；可懂度需要 weicoz-zero-tts 的远端服务（ZERO_TTS_API_URL）。
只用标准库。
"""
import argparse
import array
import json
import math
import operator
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

PAD = 0.05            # 切句前后留白（秒）
BLOCK = 0.05          # 能量统计块长（秒）
SR = 16000            # 分析采样率
SPEECH_DB = -45.0     # vo 块高于它才算有人声
LISTEN_BATCH = 8
LEVEL_RANK = {"": 0, "yellow": 1, "red": 2}
MARK = {"yellow": "黄", "red": "红"}


# ---------- 输入解析 ----------

def parse_timing(root):
    text = (root / "src/timing.ts").read_text(encoding="utf-8")
    m = re.search(r"\bFPS\s*=\s*(\d+)", text)
    fps = int(m.group(1)) if m else 30
    shots, s = [], 0
    for m in re.finditer(r"id:\s*'(\w+)',\s*seg:\s*'(seg\d+)'.*?segStart:\s*([\d.]+).*?frames:\s*(\d+)", text):
        sid, seg, fr = m.group(1), m.group(2), int(m.group(4))
        shots.append({"id": sid, "seg": seg, "start": s, "frames": fr})
        s += fr
    return fps, shots


def load_cues(root, fps, shots):
    """返回 [{seg, i, text, g0, g1, frame, shot}]，g0/g1 为全局秒；同时返回 seg_first {seg: 起点帧}。"""
    seg_first = {}
    for sh in shots:
        seg_first.setdefault(sh["seg"], sh["start"])  # 每段旁白从该段第一个镜头起点开始播放
    cues = []
    for seg, f0 in seg_first.items():
        p = root / "vo/cues" / f"{seg}.json"
        if not p.exists():
            continue
        base = f0 / fps
        for i, c in enumerate(json.loads(p.read_text(encoding="utf-8"))):
            fr = f0 + round(c["start"] * fps)
            sid = next((x["id"] for x in shots if x["start"] <= fr < x["start"] + x["frames"]), "?")
            cues.append({"seg": seg, "i": i, "text": c["text"], "g0": base + c["start"], "g1": base + c["end"],
                         "frame": fr, "shot": sid})
    return cues, seg_first


def seg_durations(root, seg_first, cues):
    """每段旁白时长：优先 ffprobe 段音频，读不到用最后一句的结束时间。"""
    res = {}
    for seg in seg_first:
        d = None
        mp3 = root / "public/audio/vo" / f"{seg}.mp3"
        if mp3.exists():
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                               capture_output=True, text=True)
            try:
                d = float(r.stdout.strip())
            except ValueError:
                d = None
        if d is None:
            ends = [c["g1"] - seg_first[seg] / 30 for c in cues if c["seg"] == seg]
            d = max(ends) if ends else 0.0
        res[seg] = d
    return res


def check_root_switches(root, comp):
    """返回 (是否通过, 说明)。合成的 defaultProps 必须含 vo、sfx、bgm。"""
    p = root / "src/Root.tsx"
    if not p.exists():
        return False, "找不到 src/Root.tsx"
    text = p.read_text(encoding="utf-8")
    m = re.search(r"<Composition\b(?:(?!<Composition\b).)*?\bid=[\"']%s[\"'](?:(?!<Composition\b).)*" % re.escape(comp), text, re.S)
    if not m:
        return False, f"src/Root.tsx 里没有 id 为 {comp} 的合成"
    d = re.search(r"defaultProps=\{\{(.*?)\}\}", m.group(0), re.S)
    keys = set(re.findall(r"([A-Za-z_]\w*)\s*:", d.group(1))) if d else set()
    miss = [k for k in ("vo", "sfx", "bgm") if k not in keys]
    if miss:
        return False, f"合成 {comp} 的 defaultProps 缺少 {'、'.join(miss)}：要给合成加 vo、sfx、bgm 三个开关"
    return True, ""


# ---------- 音频 ----------

def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"解码失败 {path}：{r.stderr.decode()[:150]}")
    a = array.array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def block_energy(samples):
    """每 BLOCK 秒一块，返回 [平均能量（满量程 1）]。"""
    n = int(SR * BLOCK)
    out = []
    k = 32768.0 ** 2
    for i in range(0, len(samples), n):
        c = samples[i:i + n]
        out.append(sum(map(operator.mul, c, c)) / (len(c) * k))
    return out


def to_db(x):
    return 10 * math.log10(x) if x > 1e-12 else -120.0


def win_db(blocks, t0, t1):
    i0 = max(0, int(t0 / BLOCK))
    i1 = min(len(blocks), max(i0 + 1, math.ceil(t1 / BLOCK)))
    seg = blocks[i0:i1]
    return to_db(sum(seg) / len(seg)) if seg else -120.0


def loudness(mix):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(mix), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = r.stderr.split("Summary:")[-1]
    def g(pat):
        m = re.search(pat, tail)
        return float(m.group(1)) if m else None
    return {"I": g(r"\bI:\s+(-?[\d.]+|-inf)\s+LUFS"), "LRA": g(r"\bLRA:\s+([\d.]+)\s+LU"), "TP": g(r"Peak:\s+(-?[\d.]+)\s+dBFS")}


def loudness_issues(ld):
    out = []
    I, tp = ld["I"], ld["TP"]
    if I is None:
        out.append(("red", "读不到整体响度"))
    elif I < -16 or I > -12:
        out.append(("yellow", f"整体响度 {I:.1f} LUFS，超出 [-16,-12]"))
    if tp is not None:
        if tp > 0:
            out.append(("red", f"真峰值 {tp:.1f} dBTP > 0"))
        elif tp > -1:
            out.append(("yellow", f"真峰值 {tp:.1f} dBTP > -1"))
    return out


def analyze_cues(cues, vo_b, bed_b):
    for c in cues:
        v, b = win_db(vo_b, c["g0"], c["g1"]), win_db(bed_b, c["g0"], c["g1"])
        c["vo_db"], c["bed_db"] = v, b
        c["issues"] = []
        if b < -60:
            c["diff"] = None
            c["issues"].append(("", "无背景"))
            continue
        i0, i1 = max(0, int(c["g0"] / BLOCK)), min(len(vo_b), len(bed_b), math.ceil(c["g1"] / BLOCK))
        ds = sorted(to_db(vo_b[k]) - to_db(bed_b[k]) for k in range(i0, i1) if to_db(vo_b[k]) > SPEECH_DB)
        if not ds:
            c["diff"] = None
            continue
        med, over = ds[len(ds) // 2], sum(x < 0 for x in ds) / len(ds)
        c["diff"], c["over"] = med, round(over, 2)
        if med < 0:
            c["issues"].append(("red", f"背景大部分时间比旁白响（逐块中位数 {med:.1f} dB）"))
        elif med < 10:
            c["issues"].append(("yellow", f"旁白只比背景高 {med:.1f} dB（逐块中位数 <10）"))
        if med >= 0 and over >= 0.25:
            c["issues"].append(("yellow", f"背景压过旁白的时间占 {over:.0%}（≥25%）"))


def find_silence(mix_b):
    runs, start = [], None
    for i, e in enumerate(mix_b + [1.0]):
        if to_db(e) < -50 and i < len(mix_b):
            if start is None:
                start = i
        elif start is not None:
            if (i - start) * BLOCK > 2.0:
                runs.append((start * BLOCK, i * BLOCK))
            start = None
    return runs


def find_pops(vo, seg_first, durs, fps):
    out = []
    w = int(0.03 * SR)
    for seg, f0 in seg_first.items():
        t0 = f0 / fps
        for name, t in (("起点", t0), ("终点", t0 + durs.get(seg, 0))):
            c = int(t * SR)
            s = vo[max(0, c - w):c + w]
            if len(s) < 2:
                continue
            m = max(abs(b - a) for a, b in zip(s, s[1:])) / 32768.0
            if m > 0.5:
                out.append({"seg": seg, "where": name, "time": t, "max_step": round(m, 3)})
    return out


# ---------- 渲染 ----------

def render_stems(root, a, out, need):
    """need: {文件名: props 覆盖}；并行渲染，任何一条失败返回错误文本。"""
    base = json.loads(a.props) if a.props else {}
    procs = []
    for name, extra in need.items():
        props = json.dumps({**base, **extra}, ensure_ascii=False)
        cmd = ["npx", "remotion", "render", a.entry, a.comp, str(out / "stems" / name), "--codec", "wav", "--props", props]
        procs.append((name, subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
    err = None
    for name, p in procs:
        o, _ = p.communicate()
        if p.returncode != 0 and err is None:
            err = f"渲染 {name} 失败：{(o or '').strip()[-300:]}"
    return err


# ---------- 远端识别 ----------

def find_tts():
    env = os.environ.get("ZERO_TTS_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    for up in Path(__file__).resolve().parents:
        c = up / "weicoz-zero-tts/scripts/zero_tts.py"
        if c.exists():
            return c
    raise FileNotFoundError("找不到 zero_tts.py，设置 ZERO_TTS_SCRIPT 指向 weicoz-zero-tts 的脚本")


def diff_chars(x):
    return sum(max(len(d.get("script") or ""), len(d.get("heard") or "")) for d in x.get("diff", []))


def run_asr(cues, mix, vo):
    """返回 (结果 dict 或 None, 未验证原因)。结果：{"红句": ..}写回 cues。"""
    if not os.environ.get("ZERO_TTS_API_URL"):
        return None, "没设 ZERO_TTS_API_URL，无法调用远端识别"
    try:
        tts = find_tts()
    except FileNotFoundError as e:
        return None, str(e)
    with tempfile.TemporaryDirectory(prefix="check-audio-") as td:
        job = []
        for c in cues:
            for who, src in (("mix", mix), ("vo", vo)):
                key = f"{who}#{c['seg']}#{c['i']}"
                wav = Path(td) / f"{who}-{c['seg']}-{c['i']}.wav"
                r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, c['g0'] - PAD):.3f}", "-to", f"{c['g1'] + PAD:.3f}",
                                    "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)], capture_output=True)
                if r.returncode != 0:
                    return None, f"切句失败 {key}：{r.stderr.decode()[:100]}"
                job.append({"id": key, "wav": str(wav), "text": c["text"]})
        jp = Path(td) / "job.json"
        jp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, str(tts), "--align-json", str(jp)], capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                return None, f"远端识别失败：{(r.stderr or r.stdout).strip()[:200]}"
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
            return None, f"远端识别失败：{type(e).__name__} {str(e)[:100]}"
    for c in cues:
        m, v = res.get(f"mix#{c['seg']}#{c['i']}"), res.get(f"vo#{c['seg']}#{c['i']}")
        if not m or not v:
            continue
        c["asr"] = {"mix_diff": diff_chars(m), "vo_diff": diff_chars(v),
                    "mix_heard": m.get("heard") or "".join(d.get("heard", "") for d in m.get("diff", []))}
        extra = c["asr"]["mix_diff"] - c["asr"]["vo_diff"]
        msg = f"成片里听不清（成片差 {c['asr']['mix_diff']} 字，纯旁白差 {c['asr']['vo_diff']} 字）"
        if extra >= 3 or (extra >= 1 and extra >= 0.15 * len(norm_text(c["text"]))):
            c["issues"].append(("red", msg))
        elif extra >= 2:
            c["issues"].append(("yellow", msg))
    return res, ""


# ---------- 切片与试听 ----------

def cut(mix, t0, t1, dst):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-to", f"{t1:.3f}", "-i", str(mix),
                        "-c:a", "libmp3lame", "-b:a", "96k", str(dst)], capture_output=True)
    return r.returncode == 0


def tc(t):
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def level_of(c):
    return max((l for l, _ in c["issues"]), key=lambda l: LEVEL_RANK[l], default="")


def pick_listen(cues, seg_first, durs, fps, limit):
    """按优先级排：红 > 黄 > 每段首句与中间句 > 接缝；返回 [{kind, name, t0, t1, cue}]。"""
    picks, seen = [], set()
    def add(kind, name, t0, t1, cue):
        if name in seen:
            return
        seen.add(name)
        picks.append({"kind": kind, "name": name, "t0": t0, "t1": t1, "cue": cue})
    def cname(c):
        return f"{c['shot']}_{c['seg']}-{c['i']}.mp3"
    for lv in ("red", "yellow"):
        for c in cues:
            if level_of(c) == lv:
                add(lv, cname(c), c["g0"] - 0.1, c["g1"] + 0.1, c)
    for seg in seg_first:
        sc = [c for c in cues if c["seg"] == seg]
        for c in (sc[:1] + sc[len(sc) // 2:len(sc) // 2 + 1]):
            add("sample", cname(c), c["g0"] - 0.1, c["g1"] + 0.1, c)
    for seg, f0 in seg_first.items():
        t0 = f0 / fps
        if t0 > 0.1:
            add("seam", f"seam_{seg}_start.mp3", t0 - 1.5, t0 + 1.5, None)
        add("seam", f"seam_{seg}_end.mp3", t0 + durs.get(seg, 0) - 1.5, t0 + durs.get(seg, 0) + 1.5, None)
    return picks[:limit]


LISTEN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "file": {"type": "string"}, "transcript": {"type": "string"}, "has_speech": {"type": "boolean"},
            "natural": {"type": "integer"}, "emotion": {"type": "string", "enum": ["平淡", "热情", "严肃", "其他"]},
            "masking": {"type": "string", "enum": ["none", "slight", "obvious"]}, "notes": {"type": "string"}},
            "required": ["file", "transcript", "has_speech", "natural", "emotion", "masking", "notes"]}},
        "overall": {"type": "object", "properties": {"voice_fit": {"type": "string"}, "bgm_fit": {"type": "string"},
                                                     "notes": {"type": "string"}},
                    "required": ["voice_fit", "bgm_fit", "notes"]},
    },
    "required": ["items", "overall"],
}
DIFF_RATE_YELLOW = 0.30


_ZH = None


def norm_text(s):
    """去标点与空白，阿拉伯数字转中文数字（借 zh-numerals.py），「两」按「二」比，只留字。"""
    global _ZH
    if _ZH is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("zh_numerals", Path(__file__).resolve().parent / "zh-numerals.py")
        _ZH = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ZH)
    s = _ZH.convert(s or "")[0]
    return re.sub(r"[^\w]|_", "", s).replace("两", "二")


def compare_text(script, heard):
    """difflib 比对：返回 (差异字数, 差异率, [{script, heard}])。"""
    import difflib
    a, b = norm_text(script), norm_text(heard)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    n, frags = 0, []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            n += max(i2 - i1, j2 - j1)
            frags.append({"script": a[i1:i2], "heard": b[j1:j2]})
    return n, (n / len(a) if a else 0.0), frags


def make_control(dst):
    """3 秒 pink 噪声，音量约 -25 dBFS（先量再补增益）。"""
    tmp = dst.with_suffix(".tmp.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=3:amplitude=0.1:sample_rate=16000",
                    str(tmp)], check=True, capture_output=True)
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(tmp), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    gain = -25.0 - float(m.group(1)) if m else 0.0
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", f"volume={gain:.2f}dB", "-c:a", "libmp3lame", "-b:a", "96k",
                    str(dst)], check=True, capture_output=True)
    tmp.unlink(missing_ok=True)


def clean_misread(s):
    s = (s or "").strip()
    return "" if (not s or s.startswith("无") or s.lower() in ("none", "n/a")) else s


def parse_agy(stdout):
    """真 agy 的 json 输出：{status, response, structured_output:{items, overall}, ...}。"""
    d = json.loads(stdout)
    so = d.get("structured_output")
    if not isinstance(so, dict):
        m = re.search(r"(\{.*\})\s*$", d.get("response") or "", re.S)
        so = json.loads(m.group(1)) if m else None
    if not isinstance(so, dict) or "items" not in so:
        raise ValueError("输出里没有 structured_output.items")
    return so


def run_listen(out, mix, picks, fps):
    """盲听：agy 的目录里只有 c01.mp3…（含每批 1 段对照噪声），稿子留在 <out>/listen-key.json。
    返回 (结果 dict, 未验证原因)；结果里 batches 记录每批是否通过对照。"""
    import random
    import shutil
    import tempfile
    clips = out / "clips"
    named = clips / "named"
    named.mkdir(parents=True, exist_ok=True)
    # 盲听目录放在工程外的系统临时目录，agy 的工作目录附近没有稿子、listen-key.json 和工程文件
    blind = Path(tempfile.mkdtemp(prefix="check-audio-listen-"))
    try:
        return _listen(out, clips, named, blind, mix, real_picks(picks, mix, named), fps)
    finally:
        shutil.rmtree(blind, ignore_errors=True)


def real_picks(picks, mix, named):
    real = []
    for p in picks:
        c = p["cue"]
        if not cut(mix, p["t0"], p["t1"], named / p["name"]):
            continue
        real.append({"pick": p, "named": p["name"], "timecode": tc(p["t0"]), "kind": "clip",
                     "shot": c["shot"] if c else "", "seg": c["seg"] if c else "", "i": c["i"] if c else None,
                     "text": c["text"] if c else "", "vo_minus_bed_db": round(c["diff"], 1) if c and c.get("diff") is not None else None})
    return real


def _listen(out, clips, named, blind, mix, real, fps):
    import random
    import shutil
    if not real:
        return None, "没有可听的片段"
    control_src = out / "control-pink.mp3"
    try:
        make_control(control_src)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return None, f"生成对照噪声失败：{e}"
    schema = out / "listen-schema.json"
    schema.write_text(json.dumps(LISTEN_SCHEMA, ensure_ascii=False), encoding="utf-8")
    agy = shlex.split(os.environ.get("CHECK_AUDIO_AGY", "agy"))
    model = os.environ.get("CHECK_AUDIO_LISTEN_MODEL", "gemini-3.8-flash-low")
    effort = os.environ.get("CHECK_AUDIO_LISTEN_EFFORT", "low")
    key, items, overall, batches, counter = [], [], [], [], 0
    for n, i in enumerate(range(0, len(real), LISTEN_BATCH), 1):
        group = list(real[i:i + LISTEN_BATCH])
        group.insert(random.randint(min(1, len(group)), max(1, len(group) - 1)), {"kind": "control"})
        files = []
        for g in group:
            counter += 1
            g["file"] = f"c{counter:02d}.mp3"
            if g["kind"] == "control":
                shutil.copy(control_src, blind / g["file"])
            else:
                cut(mix, g["pick"]["t0"], g["pick"]["t1"], blind / g["file"])
            files.append(g["file"])
            key.append({k: v for k, v in g.items() if k != "pick"} | {"batch": n})
        prompt = ("你是音频试听员。当前目录有以下音频文件，逐个用 read_file 读取并亲自听，不要运行任何命令，也不要读取其他目录。"
                  "文件可能有人声，也可能只有音乐、噪声或静音，如实判断。对每个文件输出：transcript（逐字转写听到的话，听不到人声就写空字符串，不要猜）、"
                  "has_speech（是否有人声）、natural（人声自然度 1-5，5 为像真人；没有人声填 1）、emotion（平淡/热情/严肃/其他）、"
                  "masking（背景音乐或音效是否盖住人声：none/slight/obvious）、notes（简短说明）。"
                  "另给整体 overall：voice_fit（声线是否适合讲解）、bgm_fit（背景是否合适）、notes。按 JSON schema 输出，items 里每个文件一条，file 填文件名。\n文件：\n"
                  + "\n".join(files))
        cmd = agy + ["-p", prompt, "--mode", "plan", "--model", model, "--effort", effort, "--print-timeout", "600s",
                     "--output-format", "json", "--json-schema", str(schema)]
        (out / "listen-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            r = subprocess.run(cmd, cwd=blind, capture_output=True, text=True, timeout=900)
        except FileNotFoundError:
            return None, f"找不到 agy 可执行文件（{' '.join(agy)}）"
        except subprocess.TimeoutExpired:
            return None, f"agy 第 {n} 批超时"
        if r.returncode != 0:
            (clips / f"listen-raw-{n}.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
            return None, f"agy 第 {n} 批返回 {r.returncode}，原始输出见 clips/listen-raw-{n}.txt"
        try:
            so = parse_agy(r.stdout)
        except (ValueError, TypeError) as e:
            (clips / f"listen-raw-{n}.txt").write_text(r.stdout, encoding="utf-8")
            return None, f"agy 第 {n} 批输出解析失败（{e}），原始输出见 clips/listen-raw-{n}.txt"
        got = {x.get("file"): x for x in so["items"] if isinstance(x, dict)}
        ctrl = next(g for g in group if g["kind"] == "control")
        cx = got.get(ctrl["file"])
        if cx is None:
            batches.append({"n": n, "ok": False, "reason": "Gemini 未通过对照（没有返回对照片段）"})
            continue
        if cx.get("has_speech") or (cx.get("transcript") or "").strip():
            batches.append({"n": n, "ok": False, "reason": "Gemini 未通过对照（把噪声当成人声）",
                            "control_transcript": cx.get("transcript") or ""})
            continue
        batches.append({"n": n, "ok": True, "reason": ""})
        for g in group:
            x = got.get(g["file"])
            if g["kind"] == "control" or x is None:
                continue
            it = dict(x)
            it.update({"shot": g["shot"], "seg": g["seg"], "i": g["i"], "script": g["text"], "timecode": g["timecode"],
                       "named": g["named"], "reasons": []})
            if g["text"]:
                nd, rate, frags = compare_text(g["text"], x.get("transcript"))
                it.update({"diff_chars": nd, "diff_rate": round(rate, 2), "diff_frags": frags})
                if rate > DIFF_RATE_YELLOW:
                    it["reasons"].append(f"Gemini 听到的与稿子不符（差异率 {rate:.0%}）")
            if x.get("masking") == "obvious":
                it["reasons"].append("背景明显遮挡旁白")
            it["yellow"] = bool(it["reasons"])
            items.append(it)
        if so.get("overall"):
            overall.append(so["overall"])
    return {"items": items, "overall": overall, "count": len(real), "batches": batches}, ""


# ---------- 报告 ----------

def write_report(out, data, cues, ld, ld_issues, silences, pops, asr_reason, listen, listen_reason, verdict, args):
    L = []
    L.append("# 成片音频检查报告\n")
    L.append(f"**结论：{verdict}**（红 {data['red']} 项，黄 {data['yellow']} 项）\n")
    L.append("## 响度（mix）\n")
    L.append("| 指标 | 值 | 阈值 |\n|---|---|---|")
    f = lambda v, u: "未读到" if v is None else f"{v:.1f} {u}"
    L.append(f"| 整体响度 I | {f(ld['I'], 'LUFS')} | 黄 [-16,-12] 外 |")
    L.append(f"| 真峰值 | {f(ld['TP'], 'dBTP')} | 黄 > -1，红 > 0 |")
    L.append(f"| 响度范围 LRA | {f(ld['LRA'], 'LU')} | 仅记录 |")
    for lv, t in ld_issues:
        L.append(f"- {MARK[lv]}：{t}")
    L.append("\n## 逐句（只列黄和红）\n")
    bad = [c for c in cues if level_of(c)]
    if bad:
        L.append("| 全局帧 | 时间码 | 镜头 | seg#句 | 稿子前 20 字 | vo−bed 逐块中位 dB | 问题 | 切片 |\n|---|---|---|---|---|---|---|---|")
        for c in bad:
            probs = "；".join(f"{MARK[l]}：{t}" for l, t in c["issues"] if l)
            d = "无背景" if c["diff"] is None else f"{c['diff']:.1f}"
            clip = c.get("clip", "")
            L.append(f"| {c['frame']} | {tc(c['g0'])} | {c['shot']} | {c['seg']}#{c['i']} | {c['text'][:20]} | {d} | {probs} | {clip} |")
    else:
        L.append("无黄红句。")
    nobg = sum(1 for c in cues if c["diff"] is None)
    if nobg:
        L.append(f"\n另有 {nobg} 句背景近乎静音（< -60 dBFS），记为「无背景」，不判 vo−bed。")
    L.append("\n## 可懂度（成片 vs 纯旁白识别）\n")
    if asr_reason:
        L.append(f"未验证：{asr_reason}")
    else:
        rows = [c for c in cues if c.get("asr") and c["asr"]["mix_diff"] > c["asr"]["vo_diff"]]
        done = sum(1 for c in cues if c.get("asr"))
        L.append(f"共识别 {done} 句，成片比纯旁白多错字的 {len(rows)} 句（多错 2 字黄，≥3 字或 ≥15% 红）。")
        for c in rows:
            L.append(f"- {c['seg']}#{c['i']}（{c['shot']}，{tc(c['g0'])}）稿子「{c['text'][:30]}」→ 成片识别「{c['asr']['mix_heard'] or '（无）'}」")
    L.append("\n## 静音与接缝\n")
    if silences:
        for s0, s1 in silences:
            L.append(f"- 黄：mix 空白 {tc(s0)}–{tc(s1)}（{s1 - s0:.1f} 秒，低于 -50 dBFS）")
    else:
        L.append("- 无超过 2.0 秒的静音。")
    if pops:
        for p in pops:
            L.append(f"- 黄：疑似爆音 {p['seg']} 旁白{p['where']} {tc(p['time'])}，相邻样本差 {p['max_step']}（>0.5）")
    else:
        L.append("- 各段旁白起止 ±30 ms 内无疑似爆音。")
    if args.listen:
        L.append("\n## Gemini 试听（参考）\n")
        if listen is None:
            L.append(f"未验证：{listen_reason}")
        else:
            flagged = [i for i in listen["items"] if i["yellow"]]
            bad_b = [b for b in listen["batches"] if not b["ok"]]
            L.append(f"试听 {listen['count']} 个片段（盲听，每批混入 1 段噪声对照），有效结果 {len(listen['items'])} 条，黄 {len(flagged)} 项（不影响退出码）。\n")
            for b in bad_b:
                L.append(f"- 第 {b['n']} 批未验证：{b['reason']}，该批结果作废，不计黄项。")
            if listen["items"]:
                L.append("\n| 片段 | 时间码 | 有人声 | 自然度 | 情绪 | 遮挡 | 差异率 | 备注 |\n|---|---|---|---|---|---|---|---|")
                for i in listen["items"]:
                    nm = f"{i['shot']} {i['seg']}#{i['i']}" if i.get("seg") else f"接缝 {i['named']}"
                    rate = f"{i['diff_rate']:.0%}" if "diff_rate" in i else "-"
                    L.append(f"| {'黄 ' if i['yellow'] else ''}{nm} | {i['timecode']} | {i.get('has_speech')} | {i.get('natural')} | "
                             f"{i.get('emotion')} | {i.get('masking')} | {rate} | {str(i.get('notes', ''))[:60]} |")
            for i in flagged:
                nm = f"{i['shot']} {i['seg']}#{i['i']}" if i.get("seg") else i["named"]
                L.append(f"\n- 黄 {nm}：{'；'.join(i['reasons'])}")
                if i.get("script"):
                    L.append(f"  - 稿子：{i['script']}\n  - Gemini 听到：{i.get('transcript') or '（没听到人声）'}")
                    L.append(f"  - 差异：{i['diff_chars']} 字；" + "、".join(f"「{d['script'] or '（无）'}」→「{d['heard'] or '（无）'}」" for d in i["diff_frags"][:6]))
                L.append(f"  - 试听：clips/named/{i['named']}")
            for o in listen["overall"]:
                L.append(f"\n整体：声线 {o.get('voice_fit', '')}；背景音乐 {o.get('bgm_fit', '')}；{o.get('notes', '')}")
    L.append("\n## 未验证项\n")
    unv = []
    if asr_reason:
        unv.append(f"可懂度：{asr_reason}")
    if args.listen and listen is None:
        unv.append(f"Gemini 试听：{listen_reason}")
    if args.listen and listen:
        unv.extend(f"Gemini 试听第 {b['n']} 批：{b['reason']}" for b in listen["batches"] if not b["ok"])
    L.extend([f"- {u}" for u in unv] or ["- 无。"])
    (out / "audio-report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", required=True)
    ap.add_argument("--final")
    ap.add_argument("--comp", default="Main")
    ap.add_argument("--entry", default="src/index.ts")
    ap.add_argument("--props", default="")
    ap.add_argument("--stems-dir")
    ap.add_argument("--skip-asr", action="store_true")
    ap.add_argument("--listen", action="store_true")
    ap.add_argument("--listen-max", type=int, default=16)
    a = ap.parse_args()
    root, out = Path(a.project).resolve(), Path(a.out).resolve()

    if not (root / "src/timing.ts").exists():
        print("错误：找不到 src/timing.ts。")
        return 2
    ok, why = check_root_switches(root, a.comp)
    if not ok:
        print(f"错误：{why}。")
        return 2
    if a.final and not Path(a.final).exists():
        print(f"错误：成片 {a.final} 不存在。")
        return 2
    if a.props:
        try:
            json.loads(a.props)
        except ValueError:
            print("错误：--props 不是合法 JSON。")
            return 2
    fps, shots = parse_timing(root)
    cues, seg_first = load_cues(root, fps, shots)
    if not cues:
        print("错误：没有读到任何句界（vo/cues/segNN.json）。")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    (out / "stems").mkdir(exist_ok=True)
    sd = Path(a.stems_dir) if a.stems_dir else None
    ready = sd and (sd / "vo.wav").exists() and (sd / "bed.wav").exists() and (a.final or (sd / "mix.wav").exists())
    if ready:
        stem_dir = sd
    else:
        stem_dir = out / "stems"
        need = {"vo.wav": {"vo": True, "sfx": False, "bgm": False}, "bed.wav": {"vo": False, "sfx": True, "bgm": True}}
        if not a.final:
            need["mix.wav"] = {"vo": True, "sfx": True, "bgm": True}
        print(f"渲染分轨 {'、'.join(need)}（并行）……")
        err = render_stems(root, a, out, need)
        if err:
            print(f"错误：{err}")
            return 2
    vo_wav, bed_wav = stem_dir / "vo.wav", stem_dir / "bed.wav"
    if a.final:
        mix_wav = out / "stems" / "mix.wav"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.final, "-vn", "-c:a", "pcm_s16le", str(mix_wav)], capture_output=True)
        if r.returncode != 0:
            print(f"错误：抽取成片音轨失败：{r.stderr.decode()[:150]}")
            return 2
    else:
        mix_wav = stem_dir / "mix.wav"

    try:
        vo, bed, mix = decode(vo_wav), decode(bed_wav), decode(mix_wav)
    except RuntimeError as e:
        print(f"错误：{e}")
        return 2
    vo_b, bed_b, mix_b = block_energy(vo), block_energy(bed), block_energy(mix)
    ld = loudness(mix_wav)
    ld_issues = loudness_issues(ld)
    analyze_cues(cues, vo_b, bed_b)
    durs = seg_durations(root, seg_first, cues)
    for seg in durs:  # seg_durations 的回退值按 30fps 估，这里按真实 FPS 重算
        if not (root / "public/audio/vo" / f"{seg}.mp3").exists():
            durs[seg] = max((c["g1"] for c in cues if c["seg"] == seg), default=seg_first[seg] / fps) - seg_first[seg] / fps
    silences = find_silence(mix_b)
    pops = find_pops(vo, seg_first, durs, fps)

    asr_reason = ""
    if a.skip_asr:
        asr_reason = "按 --skip-asr 跳过"
    else:
        _, asr_reason = run_asr(cues, mix_wav, vo_wav)

    # 黄红句切片
    clips = out / "clips" / "named"
    clips.mkdir(parents=True, exist_ok=True)
    for c in cues:
        if level_of(c):
            name = f"{c['shot']}_{c['seg']}-{c['i']}.mp3"
            if cut(mix_wav, c["g0"] - 0.1, c["g1"] + 0.1, clips / name):
                c["clip"] = f"clips/named/{name}"

    listen, listen_reason = None, ""
    if a.listen:
        picks = pick_listen(cues, seg_first, durs, fps, a.listen_max)
        listen, listen_reason = run_listen(out, mix_wav, picks, fps)

    reds = sum(1 for l, _ in ld_issues if l == "red") + sum(1 for c in cues for l, _ in c["issues"] if l == "red")
    yellows = (sum(1 for l, _ in ld_issues if l == "yellow") + sum(1 for c in cues for l, _ in c["issues"] if l == "yellow")
               + len(silences) + len(pops))
    verdict = "FAIL" if reds else "PASS"
    data = {"verdict": verdict, "red": reds, "yellow": yellows, "fps": fps, "loudness": ld,
            "loudness_issues": [{"level": l, "text": t} for l, t in ld_issues],
            "cues": [{"seg": c["seg"], "i": c["i"], "shot": c["shot"], "frame": c["frame"], "start": round(c["g0"], 3),
                      "end": round(c["g1"], 3), "text": c["text"], "vo_db": round(c["vo_db"], 1), "bed_db": round(c["bed_db"], 1),
                      "vo_minus_bed": None if c["diff"] is None else round(c["diff"], 1), "asr": c.get("asr"),
                      "clip": c.get("clip", ""), "issues": [{"level": l, "text": t} for l, t in c["issues"]]} for c in cues],
            "silences": [{"start": round(s, 2), "end": round(e, 2)} for s, e in silences], "pops": pops,
            "asr_unverified": asr_reason, "listen": listen, "listen_unverified": listen_reason if a.listen else ""}
    (out / "audio-report.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(out, data, cues, ld, ld_issues, silences, pops, asr_reason, listen, listen_reason, verdict, a)

    bad = sum(1 for c in cues if level_of(c))
    I = "?" if ld["I"] is None else f"{ld['I']:.1f}"
    print(f"{verdict}：红 {reds}，黄 {yellows}；{len(cues)} 句中 {bad} 句有问题；响度 {I} LUFS")
    if asr_reason:
        print(f"可懂度未验证：{asr_reason}")
    if a.listen and listen is None:
        print(f"Gemini 试听未验证：{listen_reason}")
    if listen:
        for b in listen["batches"]:
            if not b["ok"]:
                print(f"Gemini 试听第 {b['n']} 批未验证：{b['reason']}")
    print(f"报告：{out / 'audio-report.md'}")
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
