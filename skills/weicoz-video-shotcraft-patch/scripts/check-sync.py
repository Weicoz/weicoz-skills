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


def shot_file(shots_dir: Path, sid: str):
    cand = shots_dir / f"{sid[0].upper()}{sid[1:]}.tsx"
    return cand if cand.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--tol", type=int, default=15)
    ap.add_argument("--shots-dir", default="src/shots")
    a = ap.parse_args()
    root = Path(a.project)

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
    red, yellow, ok, skipped = [], [], 0, 0
    for sid, seg, seg_start in shots:
        f = shot_file(root / a.shots_dir, sid)
        cues_p = root / "vo/cues" / f"{seg}.json"
        if not f or not cues_p.exists():
            missing.append(sid)
            continue
        cues = json.loads(cues_p.read_text(encoding="utf-8"))
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
            try:
                ns = parse_cues(comment)
            except ValueError as e:
                red.append(f"{sid}.{name}: {e}")
                continue
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
    if ok + len(red) + len(yellow) == 0:
        print("错误：没有解析到任何带 cueN 的节拍。检查 BEATS 常量和注释格式（见脚本开头的约定）。")
        return 2
    print(f"容差 ±{a.tol} 帧：通过 {ok}，红 {len(red)}，黄 {len(yellow)}（句内估算），未写 cueN 跳过 {skipped}")
    for r in red:
        print("红", r)
    for y in yellow:
        print("黄", y)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
