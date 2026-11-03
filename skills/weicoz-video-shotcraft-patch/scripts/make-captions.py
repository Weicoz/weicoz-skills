#!/usr/bin/env python3
"""由 vo/cues 生成烧录字幕数据与 srt：长句按标点拆成短行，时间按字数分配。

用法：make-captions.py <工程目录> [--max-chars 22] [--display vo/script-display] [--out-data src/captions-data.ts] [--srt out/captions.srt]
字幕文字：<display>/segNN.txt 存在时，按句序号替换成其中的句子（配音稿用中文数字、字幕用阿拉伯数字时用；见 zh-numerals.py），
两边句数必须一致，否则报错。
读：src/timing.ts（每段旁白从该段第一个镜头的起点开始播放）、vo/cues/segNN.json。
写：src/captions-data.ts（{a: 起始帧, b: 结束帧, t: 文字}，全局帧号）与 srt。
字级时间：vo/cues-words/segNN.json 存在（align-words.py 生成）且字数对得上时，长句拆成的每一行按字级时间定起止（行首字起点到行末字终点），
  对不上时退回按字数比例分配。加 --no-words 强制用比例分配。
"""
import argparse
import json
import re
import sys
from pathlib import Path

FPS = 30
OBJ = re.compile(r"\{[^{}]*\}")
PUN = r"[，,；;：:。？！?!]"
PUN_ALL = r"[，,；;：:。？！?!、]"  # 字级时间的字表不含顿号，数字数时顿号也不算字
CLOSERS = "”’）)」』】》"
SENT = re.compile(r"[^。！？!?\n]+[。！？!?]*[" + CLOSERS + r"]*")
WORD = re.compile(r"[一-鿿A-Za-z0-9]")


def split(text, maxc):
    parts = [p for p in re.split(r"(?<=" + PUN + ")", text) if p.strip()]
    chunks, cur = [], ""
    for p in parts:
        if cur and len(re.sub(PUN, "", cur + p)) > maxc:
            chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    res = []
    for c in chunks:
        c = c.strip()
        while len(c) > maxc + 6:
            res.append(c[:maxc])
            c = c[maxc:]
        res.append(c)
    return [re.sub(PUN + "+$", "", x) for x in res if x]


def parts(text):
    return [p for p in re.split(r"(?<=" + PUN + ")", text) if p.strip()]


def groups(text, maxc):
    """与 split() 同样的合并规则，返回每一行包含哪几个标点小段（小段下标列表）；有硬切时返回 None。"""
    ps = parts(text)
    out, cur, curp = [], "", []
    for i, p in enumerate(ps):
        if cur and len(re.sub(PUN, "", cur + p)) > maxc:
            out.append(curp)
            cur, curp = p, [i]
        else:
            cur += p
            curp.append(i)
    if curp:
        out.append(curp)
    for g in out:
        if len("".join(ps[i] for i in g).strip()) > maxc + 6:
            return None
    return out


def word_lines(script, display, words, maxc):
    """按字级时间给每行定 (start, end, 行文字)，对不上返回 None。script 是配音稿句子，display 是字幕稿句子。"""
    sp, dp = parts(script), parts(display)
    if len(sp) != len(dp):
        return None
    chars = words.get("chars") or []
    n = [len(re.sub(PUN_ALL, "", x)) for x in sp]
    if sum(n) != len(chars):
        return None
    gs = groups(display, maxc)
    if not gs:
        return None
    off = [0]
    for k in n:
        off.append(off[-1] + k)
    lines = []
    for g in gs:
        lo, hi = off[g[0]], off[g[-1] + 1]
        if hi <= lo:
            return None
        txt = re.sub(PUN + "+$", "", "".join(dp[i] for i in g).strip())
        lines.append((chars[lo]["start"], chars[hi - 1]["end"], txt))
    return lines


def tc(f):
    ms = round(f / FPS * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--max-chars", type=int, default=22)
    ap.add_argument("--display", default="vo/script-display")
    ap.add_argument("--out-data", default="src/captions-data.ts")
    ap.add_argument("--srt", default="out/captions.srt")
    ap.add_argument("--no-words", action="store_true", help="不用字级时间，长句按字数比例分配")
    a = ap.parse_args()
    root = Path(a.project)
    start, s = {}, 0
    for obj in OBJ.findall((root / "src/timing.ts").read_text(encoding="utf-8")):
        i = re.search(r"['\"]?\bseg['\"]?\s*:\s*['\"](seg\d+)['\"]", obj)
        fr = re.search(r"['\"]?\bframes['\"]?\s*:\s*(\d+)", obj)
        if i and fr:
            start.setdefault(i.group(1), s)
            s += int(fr.group(1))
    if not start:
        print("错误：src/timing.ts 里没有解析出镜头。")
        return 2
    out = []
    nwords = 0
    for seg in sorted(start):
        p = root / "vo/cues" / f"{seg}.json"
        if not p.exists():
            continue
        cues = json.loads(p.read_text(encoding="utf-8"))
        wp = root / "vo/cues-words" / f"{seg}.json"
        wmap = {}
        if wp.exists() and not a.no_words:
            wmap = {w.get("cue"): w for w in json.loads(wp.read_text(encoding="utf-8"))}
        scripts = [c["text"] for c in cues]
        dp = root / a.display / f"{seg}.txt"
        if dp.exists():
            ds = [x.strip() for x in SENT.findall(dp.read_text(encoding="utf-8")) if x.strip() and WORD.search(x)]
            if len(ds) != len(cues):
                print(f"错误：{seg} 字幕稿 {len(ds)} 句，配音稿 {len(cues)} 句，句数不一致。")
                return 2
            for c, d in zip(cues, ds):
                c["text"] = d
        for ci, c in enumerate(cues):
            wl = word_lines(scripts[ci], c["text"], wmap[ci], a.max_chars) if ci in wmap else None
            if wl:
                for k, (ws, we, x) in enumerate(wl):
                    nxt = wl[k + 1][0] if k + 1 < len(wl) else None
                    b = we + 0.12 if nxt is None else (nxt if nxt - we < 0.35 else we + 0.12)
                    out.append((start[seg] + round(max(0.0, ws - 0.04) * FPS), start[seg] + round(b * FPS), x))
                nwords += 1
                continue
            ch = split(c["text"], a.max_chars)
            w = [max(1, len(x)) for x in ch]
            tw, t, dur = sum(w), c["start"], c["end"] - c["start"]
            for x, wi in zip(ch, w):
                d = dur * wi / tw
                out.append((start[seg] + round(t * FPS), start[seg] + round((t + d) * FPS), x))
                t += d
    for i in range(len(out) - 1):  # 不重叠
        if out[i][1] > out[i + 1][0]:
            out[i] = (out[i][0], out[i + 1][0], out[i][2])
    ts = "// 字幕：由 vo/cues 句子时间拆成短行，a/b 为全局帧号。换配音后重新生成。\nexport const CAPTIONS: {a: number; b: number; t: string}[] = [\n"
    ts += "".join(f"  {{a: {x}, b: {y}, t: {json.dumps(z, ensure_ascii=False)}}},\n" for x, y, z in out) + "];\n"
    (root / a.out_data).write_text(ts, encoding="utf-8")
    srt = root / a.srt
    srt.parent.mkdir(parents=True, exist_ok=True)
    srt.write_text("\n".join(f"{i + 1}\n{tc(x)} --> {tc(y)}\n{z}\n" for i, (x, y, z) in enumerate(out)), encoding="utf-8")
    print(f"字级时间 {nwords} 句，其余按字数比例分配")
    print(f"{len(out)} 条字幕，最长 {max((len(z) for _, _, z in out), default=0)} 字 → {a.out_data}、{a.srt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
