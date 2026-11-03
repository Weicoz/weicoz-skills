#!/usr/bin/env python3
"""声画同步检查：镜头里的节拍帧 vs 对应旁白句的真实起点。

用法：check-sync.py <工程目录> [--tol 15] [--shots-dir src/shots]
约定：镜头文件里的 BEATS 常量，每条写在一行内，注释写明对应的旁白句编号，格式 `cueN`。
      镜头文件按 S+id 命名（s7 → S7.tsx）。N 从 0 起，
      与 vo/cues/segNN.json 数组下标一致（第一句是 cue0）：
        const BEATS = {
          badge: 121,           // cue1 4.15s「还多出两毛」
          marks: [514, 574],    // cue4/5（数组：cue 个数与数字个数相同时逐个配对）
          rows: [419, 556, 708], // cue4–6（范围写法，也可写 cue4/5/6）
          lead: 430,  // cue3 句内，按字数估算
        };
读：src/timing.ts（镜头 id、所在段、段内起点、帧数）、vo/cues/segNN.json（每句起止秒）。
比对：该句窗口 = [起点, 终点]（秒，减去镜头在段内的起点后 × 帧率）；节拍帧落在窗口之外超过 --tol 帧判红。
      早于句首最伤（画面先给了答案），晚于句尾次之（观众已听完才看到）。
      注释里带「估算」的节拍只给黄色提示（句内词没有词级时间）。
字级锚点（推荐）：注释写 cueN@词（可加 #k 指第 k 次出现），如 `flip: 206, // cue3@推成「推成一单」`；
      数组节拍写多个锚点按顺序配对：`rows: [419, 556], // cue4@直推 cue5@间推`。
      锚点从 vo/cues-words/segNN.json（align-words.py 生成）取该词首字的开始时间：
      节拍早于它超过 --early 帧（默认 2）判红，画面抢在声音前面；晚于它超过 --late 帧（默认 6）判黄。
      已有 vo/cues-words 却仍写句级 cueN（没有 cueN@词）的节拍给黄色迁移提示（句窗口检查照做），
      汇总行单独计「待迁移 N」，不计入红黄，不影响退出码；同一条不重复报。
退出码：有红色返回 1；镜头表或节拍一条都没解析出来返回 2（格式不符时不会假装通过）。
      注释里没有 cueN 的节拍不检查，会列出数量。数组节拍：cue 个数与数字个数相同时逐个配对，
      否则每个数字都与所列 cue 的整体窗口（最早起点到最晚终点）比。
"""
import argparse
import json
import re
import sys
from pathlib import Path

FPS = 30
LINE = re.compile(r"^\s*(\w+):\s*\[?\s*(-?\d+(?:\s*,\s*-?\d+)*)\s*\]?,?\s*//\s*(.*)$")
OBJ = re.compile(r"\{[^{}]*\}")


def parse_cues(comment):
    """cue5、cue5/6/7、cue4–7 → [5] / [5,6,7] / [4,5,6,7]。"""
    m = re.search(r"\bcue(\d+(?:\s*[/、–\-~]\s*\d+)*)", comment)
    if not m:
        return []
    out, parts = [], re.split(r"(\s*[/、–\-~]\s*)", m.group(1))
    prev, sep = int(parts[0]), None
    out.append(prev)
    for i in range(1, len(parts), 2):
        sep, cur = parts[i].strip(), int(parts[i + 1])
        if sep in ("–", "-", "~"):
            if cur < prev:
                raise ValueError(f"cue 范围写反了：cue{prev}–{cur}")
            out += list(range(prev + 1, cur + 1))
        else:
            out.append(cur)
        prev = cur
    return out


ANCHOR = re.compile(r"\bcue(\d+)@([^\s，。、；;/@#「」“”]+)(?:#(\d+))?")


def word_start(chars, word, nth=1):
    """在该句的字级时间里找词 word 第 nth 次出现，返回首字开始秒；找不到返回 None。"""
    if not chars:
        return None
    text = "".join(c["c"] for c in chars)
    pos = -1
    for _ in range(nth):
        pos = text.find(word, pos + 1)
        if pos < 0:
            return None
    return chars[pos]["start"]


def shot_file(shots_dir: Path, sid: str):
    cand = shots_dir / f"{sid[0].upper()}{sid[1:]}.tsx"
    return cand if cand.exists() else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--tol", type=int, default=15)
    ap.add_argument("--shots-dir", default="src/shots")
    ap.add_argument("--early", type=int, default=2, help="字级锚点：节拍早于该词超过多少帧判红")
    ap.add_argument("--late", type=int, default=6, help="字级锚点：节拍晚于该词超过多少帧判黄")
    a = ap.parse_args(argv)
    root = Path(a.project).resolve()

    if not (root / "src/timing.ts").exists():
        print(f"错误：{root}/src/timing.ts 不存在。")
        return 2
    shots, unparsed, missing = [], [], []
    for obj in OBJ.findall((root / "src/timing.ts").read_text(encoding="utf-8")):
        i = re.search(r"['\"]?\bid['\"]?\s*:\s*['\"](\w+)['\"]", obj)
        g = re.search(r"['\"]?\bseg['\"]?\s*:\s*['\"](seg\d+)['\"]", obj)
        t = re.search(r"['\"]?\bsegStart['\"]?\s*:\s*([\d.]+)", obj)
        if i and g and t:
            shots.append((i.group(1), g.group(1), t.group(1)))
        elif i:
            unparsed.append(i.group(1))
    if not shots:
        print("错误：src/timing.ts 里没有解析出镜头（镜头对象写成单层 {id, seg, segStart, frames}，对象内不嵌套花括号）。")
        return 2
    red, yellow, ok, skipped, word_ok = [], [], 0, 0, 0
    migrate = []
    for sid, seg, seg_start in shots:
        f = shot_file(root / a.shots_dir, sid)
        cues_p = root / "vo/cues" / f"{seg}.json"
        if not f or not cues_p.exists():
            missing.append(sid)
            continue
        cues = json.loads(cues_p.read_text(encoding="utf-8"))
        words_p = root / "vo/cues-words" / f"{seg}.json"
        words = {r["cue"]: r["chars"] for r in json.loads(words_p.read_text(encoding="utf-8"))} if words_p.exists() else None
        in_beats = False
        for raw in f.read_text(encoding="utf-8").splitlines():
            if re.match(r"^\s*(?:export\s+)?const\s+BEATS\b", raw):
                in_beats = True
                continue
            if in_beats and raw.strip().startswith("}"):
                in_beats = False
            if not in_beats:
                continue
            m = LINE.match(raw)
            if not m:
                continue
            name, comment = m.group(1), m.group(3)
            frames_ = [int(x) for x in re.findall(r"-?\d+", m.group(2))]
            anchors = ANCHOR.findall(comment)
            if anchors:
                if words is None:
                    yellow.append(f"{sid}.{name}: 写了字级锚点，但 vo/cues-words/{seg}.json 不存在，先跑 align-words.py")
                    continue
                if len(anchors) != len(frames_):
                    red.append(f"{sid}.{name}: {len(frames_)} 个帧号对 {len(anchors)} 个锚点，数量要一致")
                    continue
                for frame, (n, word, nth) in zip(frames_, anchors):
                    t = word_start(words.get(int(n)), word, int(nth or 1))
                    if t is None:
                        red.append(f"{sid}.{name}: cue{n} 里找不到「{word}」" + (f"（第 {nth} 次）" if nth else ""))
                        continue
                    target = round((t - float(seg_start)) * FPS)
                    dev = frame - target
                    row = f"{sid}.{name}: 节拍 {frame} 帧；cue{n}@{word} 在 {target} 帧；{'早' if dev < 0 else '晚'} {abs(dev)} 帧（{abs(dev)/FPS:.2f}s）"
                    if dev < -a.early:
                        red.append(row)
                    elif dev > a.late:
                        yellow.append(row)
                    else:
                        word_ok += 1
                continue
            try:
                ns = parse_cues(comment)
            except ValueError as e:
                red.append(f"{sid}.{name}: {e}")
                continue
            if words is not None and ns:
                hint = f"{sid}.{name}: 已有 vo/cues-words，改成字级锚点 cueN@词（align-words.py --find 查帧号）"
                if hint not in migrate:
                    migrate.append(hint)
            if not ns:
                skipped += 1
                continue
            bad = [n for n in ns if n >= len(cues)]
            if bad:
                red.append(f"{sid}.{name}: 引用了不存在的 cue{bad[0]}（该段只有 {len(cues)} 句）")
                continue
            span = lambda n: (round((cues[n]["start"] - float(seg_start)) * FPS), round((cues[n]["end"] - float(seg_start)) * FPS))
            for k, frame in enumerate(frames_):
                if len(ns) == len(frames_):
                    lo, hi = span(ns[k])
                    label = f"cue{ns[k]}"
                else:
                    lo, hi = min(span(n)[0] for n in ns), max(span(n)[1] for n in ns)
                    label = "cue" + "/".join(map(str, ns))
                dev = frame - lo if frame < lo else (frame - hi if frame > hi else 0)
                where = "早于句首" if dev < 0 else ("晚于句尾" if dev > 0 else "在句内")
                row = f"{sid}.{name}: 节拍 {frame} 帧；{label} 窗口 {lo}–{hi} 帧；{where}{abs(dev)} 帧（{abs(dev)/FPS:.1f}s）"
                if abs(dev) > a.tol:
                    (yellow if "估算" in comment else red).append(row)
                else:
                    ok += 1
    if unparsed:
        print(f"警告：timing.ts 里这些镜头缺 seg 或 segStart，未检查：{', '.join(unparsed)}")
    if missing:
        print(f"警告：找不到镜头文件（按 S+id 命名）或 vo/cues，未检查：{', '.join(missing)}")
    if ok + word_ok + len(red) + len(yellow) == 0:
        print("错误：没有解析到任何带 cueN 的节拍。检查 BEATS 常量和注释格式（见脚本开头的约定）。")
        return 2
    print(f"字级锚点（早 >{a.early} 帧红、晚 >{a.late} 帧黄）通过 {word_ok}；句窗口（±{a.tol} 帧）通过 {ok}；红 {len(red)}，黄 {len(yellow)}，待迁移 {len(migrate)}，未写 cueN 跳过 {skipped}")
    for r in red:
        print("红", r)
    for y in yellow:
        print("黄", y)
    for m in migrate:
        print("黄(迁移)", m)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
