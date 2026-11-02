#!/usr/bin/env python3
"""换配音后重排时间线：镜头时长、BEATS 节拍帧、音效钉帧，按句子做分段线性映射。

用法：remap-timeline.py <工程目录> --old-cues <旧 cues 目录> --old-timing <旧 timing.ts>
        [--apply]      不加只打印将要做的改动，不写文件
        [--shots-dir src/shots] [--sfx src/Sfx.tsx]
前提：新旁白已生成（vo/cues/segNN.json、src/vo-manifest.ts 是新的），且每段句子数与旧版相同
（句子按 。！？ 切分，换引擎不改句子数）。
做法：每个镜头在旧、新两条时间线上各取「镜头起点、每句起点、镜头终点」作断点，
      旧断点→新断点做分段线性映射；镜头总帧数按新旁白重算（src/timing.ts 重写，保留尾部额外帧）。
      BEATS 里相隔不超过 --chain 帧（默认 40）的节拍成一串：串内保持原间隔（急推 6 帧、预备 8 帧这类
      固定时长不能被压缩），串的第一个节拍走映射；串与串之间各自走映射。
      Sfx.tsx 里 `local:` 的钉帧跟着对应的节拍走（旧值相差不超过 4 帧即视为同一个节拍），找不到才走映射。
注意：BEATS 里若有「时长」而不是「时刻」的数字，也会被当作时刻处理，按报告核对。
"""
import argparse
import json
import re
import sys
from pathlib import Path

FPS = 30
OBJ = re.compile(r"\{[^{}]*\}")


def read_shots(path):
    out = []
    for obj in OBJ.findall(Path(path).read_text(encoding="utf-8")):
        g = lambda k, pat: re.search(r"['\"]?\b" + k + r"['\"]?\s*:\s*" + pat, obj)
        i, sg, ss, se, fr = g("id", r"['\"](\w+)['\"]"), g("seg", r"['\"](seg\d+)['\"]"), g("segStart", r"([\d.]+)"), g("segEnd", r"([\d.]+)"), g("frames", r"(\d+)")
        if i and sg and ss and se and fr:
            out.append({"id": i.group(1), "seg": sg.group(1), "start": float(ss.group(1)), "end": float(se.group(1)), "frames": int(fr.group(1))})
    return out


def read_cues(d, seg):
    return json.loads((Path(d) / f"{seg}.json").read_text(encoding="utf-8"))


def read_manifest(path):
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"audio/vo/(seg\d+)\.mp3',\s*seconds:\s*([\d.]+)", Path(path).read_text(encoding="utf-8"))}


def interp(bps, f):
    """bps: [(旧帧, 新帧)] 递增。分段线性，两端外推用端点斜率 1。"""
    if f <= bps[0][0]:
        return bps[0][1] + (f - bps[0][0])
    for (a0, b0), (a1, b1) in zip(bps, bps[1:]):
        if f <= a1:
            return b0 + (f - a0) * (b1 - b0) / (a1 - a0) if a1 != a0 else b0
    return bps[-1][1] + (f - bps[-1][0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--old-cues", required=True)
    ap.add_argument("--old-timing", required=True)
    ap.add_argument("--shots-dir", default="src/shots")
    ap.add_argument("--sfx", default="src/Sfx.tsx")
    ap.add_argument("--chain", type=int, default=40, help="相隔不超过这么多帧的节拍成一串，串内保持原间隔")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    root = Path(a.project)
    old_shots = read_shots(a.old_timing)
    if not old_shots:
        print("错误：旧 timing.ts 里没有解析出镜头（需要 {id, seg, segStart, segEnd, frames}）。")
        return 2
    new_dur = read_manifest(root / "src/vo-manifest.ts")
    old_dur_by_seg = {}
    for s in old_shots:
        old_dur_by_seg[s["seg"]] = max(old_dur_by_seg.get(s["seg"], 0), s["end"])

    maps, new_timing, report = {}, [], []
    for s in old_shots:
        oc, nc = read_cues(a.old_cues, s["seg"]), read_cues(root / "vo/cues", s["seg"])
        if len(oc) != len(nc):
            print(f"错误：{s['seg']} 句子数不同（旧 {len(oc)}，新 {len(nc)}），不能按句映射。")
            return 2
        eps = 0.02
        idx = [i for i, c in enumerate(oc) if s["start"] - eps <= c["start"] < s["end"] - eps]
        n_start = nc[idx[0]]["start"] if s["start"] > eps and idx else 0.0
        if s["end"] >= old_dur_by_seg[s["seg"]] - eps:
            n_end = new_dur[s["seg"]]
        else:
            nxt = next(i for i, c in enumerate(oc) if abs(c["start"] - s["end"]) <= 0.05)
            n_end = nc[nxt]["start"]
        extra = s["frames"] - round((s["end"] - s["start"]) * FPS)  # 旧镜头在旁白之外的尾部额外帧（如片尾 hold）
        new_frames = round((n_end - n_start) * FPS) + extra
        bps = [(0, 0)]
        for i in idx:
            bps.append((round((oc[i]["start"] - s["start"]) * FPS), round((nc[i]["start"] - n_start) * FPS)))
        bps.append((s["frames"], new_frames))
        bps = sorted(set(bps))
        maps[s["id"]] = bps
        new_timing.append({**s, "newStart": n_start, "newEnd": n_end, "newFrames": new_frames})
        report.append(f"{s['id']}: {s['frames']} → {new_frames} 帧（{new_frames - s['frames']:+d}）")

    # 重写 timing.ts
    total = sum(x["newFrames"] for x in new_timing)
    lines = ["// 镜头时间表：由旁白实测时长与句界决定。frames 为该镜头总帧数（30fps）。",
             "// seg/segStart/segEnd 指向 vo/cues/segNN.json 的句子时间（秒，相对该段音频）。",
             "export const FPS = 30;", "export const SHOTS = ["]
    for x in new_timing:
        lines.append(f"  {{id: '{x['id']}', seg: '{x['seg']}', segStart: {x['newStart']:.2f}, segEnd: {x['newEnd']:.2f}, frames: {x['newFrames']}}},")
    lines += ["] as const;", f"// 合计 {total} 帧 = {total / FPS:.1f} 秒", f"export const TOTAL_FRAMES = {total};", ""]
    new_timing_text = "\n".join(lines)

    changes = {}  # 文件 -> 新文本

    def remap_num(sid, n):
        return int(round(interp(maps[sid], n)))

    beat_rows, beat_maps = [], {}

    def chain_map(sid, olds):
        """olds：该镜头所有节拍的旧帧号。返回 {旧: 新}。"""
        vals = sorted(set(olds))
        out = {}
        for i, v in enumerate(vals):
            if i and v - vals[i - 1] <= a.chain:
                nv = out[vals[i - 1]] + (v - vals[i - 1])
            else:
                nv = remap_num(sid, v)
            out[v] = max(0, nv)
        return out

    BEAT_LINE = re.compile(r"^(\s*\w+:\s*\[?\s*)(-?\d+(?:\s*,\s*-?\d+)*)(\s*\]?,?.*)$")
    for sid in maps:
        f = root / a.shots_dir / f"{sid[0].upper()}{sid[1:]}.tsx"
        if not f.exists():
            report.append(f"提示：找不到 {f.name}，该镜头的 BEATS 未映射。")
            continue
        lines, in_b, olds = f.read_text(encoding="utf-8").splitlines(), False, []
        for raw in lines:  # 第一遍：收集旧帧号
            if re.match(r"^\s*(?:export\s+)?const\s+BEATS\b", raw):
                in_b = True
            elif in_b and raw.strip().startswith("}"):
                in_b = False
            m = BEAT_LINE.match(raw) if in_b else None
            if m:
                olds += [int(x) for x in re.findall(r"-?\d+", m.group(2))]
        mp = chain_map(sid, olds)
        beat_maps[sid] = mp
        out, in_b = [], False
        for raw in lines:  # 第二遍：改写
            if re.match(r"^\s*(?:export\s+)?const\s+BEATS\b", raw):
                in_b = True
            elif in_b and raw.strip().startswith("}"):
                in_b = False
            m = BEAT_LINE.match(raw) if in_b else None
            if m:
                nums = [int(x) for x in re.findall(r"-?\d+", m.group(2))]
                new = [mp[n] for n in nums]
                if new != nums:
                    beat_rows.append(f"{sid} {raw.strip()[:40]}  {nums} → {new}")
                raw = m.group(1) + ", ".join(map(str, new)) + m.group(3)
            out.append(raw)
        changes[f] = "\n".join(out) + "\n"
    sfx = root / a.sfx
    if sfx.exists():
        def sfx_new(sid, n):
            near = [o for o in beat_maps.get(sid, {}) if abs(o - n) <= 4]
            if near:
                o = min(near, key=lambda x: abs(x - n))
                return beat_maps[sid][o] + (n - o)
            return remap_num(sid, n)

        def sub(m):
            sid, n = m.group(1), int(m.group(3))
            if sid not in maps:
                return m.group(0)
            return m.group(0)[: m.start(3) - m.start(0)] + str(sfx_new(sid, n)) + m.group(0)[m.end(3) - m.start(0):]

        changes[sfx] = re.sub(r"\{shot:\s*'(\w+)',\s*(local:\s*)(\d+)", sub, sfx.read_text(encoding="utf-8"))
    changes[root / "src/timing.ts"] = new_timing_text

    print("镜头帧数：")
    print("\n".join("  " + r for r in report))
    print(f"合计 {sum(x['frames'] for x in old_shots)} → {total} 帧；BEATS 改动 {len(beat_rows)} 行（最多显示 12 行）：")
    print("\n".join("  " + r for r in beat_rows[:12]))
    if not a.apply:
        print("\n未写文件（加 --apply 才会写）。")
        return 0
    for f, text in changes.items():
        Path(f).write_text(text, encoding="utf-8")
    print(f"\n已写入 {len(changes)} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
