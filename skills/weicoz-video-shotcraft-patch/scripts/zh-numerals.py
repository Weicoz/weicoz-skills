#!/usr/bin/env python3
"""把「字幕用」的阿拉伯数字口播稿转成「配音用」的中文数字口播稿，并逐处列出替换供人工核对。

用法：zh-numerals.py <工程目录> [--src vo/script-display] [--dst vo/script] [--dry-run] [--keep-spaces]
读：<src>/segNN.txt（含阿拉伯数字，字幕用，是文案的唯一来源）
写：<dst>/segNN.txt（数字全部写成中文，TTS 读它）；--dry-run 只打印不写。
--keep-spaces 保留原稿空格。默认把中文之间的空格当排版符去掉；某片旁白已按带空格文本合成、
不接受重排时加这个开关，才能重跑出与已入库 vo/script 完全一致的文件。

规则：整数按位读（2999→两千九百九十九）；小数点后逐位读（39.8→三十九点八）；
N%→百分之N；千分位逗号去掉；数字 2 开头且后接量词或「到」时读「两」（2 桶→两桶，2 到 3 公里→两到三公里）；
数字之间的加号读「加」（链动1+1→链动一加一，2+1→二加一）；
字母开头的编号整段保留不拆读（B2、C3、MP3 原样留给 TTS）。
若 <工程>/vo/pronounce.json 存在（{"字幕里的词": "配音里的词"}），再按它替换读音有歧义的词（如 间推→间接推），字幕不受影响。
换文案后必须看一遍输出的替换清单。
"""
import argparse
import json
import re
import sys
from pathlib import Path

D = "零一二三四五六七八九"
# 前一个字符是字母或数字时不拆：B2、C3、MP3 整段留给 TTS 自己念
NUM = re.compile(r"(?<![A-Za-z0-9])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s*%)?")  # 逗号只当千分位，1,2,3 拆成三个数
# 数字之间的加号：1+1、2+1
PLUS = re.compile(r"(?<![A-Za-z0-9])(\d+)\s*\+\s*(\d+)(?![A-Za-z0-9])")
MEASURE = re.compile(r"^\s*(?:桶|元|块|个|箱|单|天|次|公里|人|户|份|成)")


def int_zh(n):
    """0–99999999 的整数读法。千位、百位的 2 读「两」，万位恰为 2 时也读「两万」。"""
    if n == 0:
        return "零"
    if n >= 10 ** 8:
        raise ValueError(f"数字过大：{n}")
    if n >= 10000:
        hi, lo = divmod(n, 10000)
        s = ("两" if hi == 2 else int_zh(hi)) + "万"
        if lo:
            if lo < 1000:
                s += "零"
            s += int_zh(lo)
        return s
    out, started, zero = "", False, False
    for i, u in enumerate("千百十"):
        base = 10 ** (3 - i)
        d, n = divmod(n, base)
        if d:
            if zero and started:
                out += "零"
            zero = False
            if d == 2 and u in "千百":
                out += "两"
            elif d == 1 and u == "十" and not started:
                out += ""  # 10–19 读「十几」
            else:
                out += D[d]
            out += u
            started = True
        elif started:
            zero = True
    if n:
        if zero and started:
            out += "零"
        out += D[n]
    return out


def to_zh(m, text):
    raw, pct = m.group(1), m.group(2)
    s = raw.replace(",", "")
    tail = text[m.end():]
    if "." in s:
        a, b = s.split(".")
        zh = int_zh(int(a)) + "点" + "".join(D[int(c)] for c in b)
    else:
        v = int(s)
        zh = int_zh(v)
        if v == 2 and not pct and (MEASURE.match(tail) or re.match(r"^\s*(?:到|万)", tail)):
            zh = "两"
    return ("百分之" + zh) if pct else zh


def convert(text, keep_spaces=False):
    log = []

    def plus_rep(m):
        z = int_zh(int(m.group(1))) + "加" + int_zh(int(m.group(2)))
        log.append((m.group(0), z))
        return z

    def rep(m):
        z = to_zh(m, text)
        log.append((m.group(0).strip(), z))
        return z

    text = PLUS.sub(plus_rep, text)
    new = NUM.sub(rep, text)
    if not keep_spaces:
        # 中文之间不留空格（原稿里数字两侧的空格是给字幕排版用的）
        new = re.sub(r"(?<=[\u4e00-\u9fff：，、；])[ \t]+(?=[\u4e00-\u9fff])", "", new)
    return new, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--src", default="vo/script-display")
    ap.add_argument("--dst", default="vo/script")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-spaces", dest="keep_spaces", action="store_true", help="保留原稿空格（旁白已按带空格文本合成时用）")
    a = ap.parse_args()
    root = Path(a.project)
    pron = {}
    if (root / "vo/pronounce.json").exists():
        pron = json.loads((root / "vo/pronounce.json").read_text(encoding="utf-8"))
    files = sorted((root / a.src).glob("seg*.txt"))
    if not files:
        print(f"错误：{root / a.src} 下没有 segNN.txt。")
        return 2
    total = 0
    for f in files:
        new, log = convert(f.read_text(encoding="utf-8"), keep_spaces=a.keep_spaces)
        for k, v in pron.items():
            if k in new:
                print(f"{f.stem}: {k} → {v}（读音）")
                new = new.replace(k, v)
        total += len(log)
        for old, z in log:
            print(f"{f.stem}: {old} → {z}")
        if not a.dry_run:
            (root / a.dst).mkdir(parents=True, exist_ok=True)
            (root / a.dst / f.name).write_text(new, encoding="utf-8")
    left = [f.name for f in files if re.search(r"(?<![A-Za-z])\d", (root / a.dst / f.name).read_text(encoding="utf-8"))] if not a.dry_run else []
    print(f"共替换 {total} 处" + ("" if a.dry_run else f"，写入 {a.dst}") + (f"；仍含阿拉伯数字：{left}" if left else ""))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
