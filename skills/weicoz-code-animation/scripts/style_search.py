#!/usr/bin/env python3
"""在 341 条代码动画风格里检索。

用法（在 skill 根目录执行）：
    python3 scripts/style_search.py 水墨
    python3 scripts/style_search.py 数据 新闻 --series L
    python3 scripts/style_search.py --code 粒 --limit 5
    python3 scripts/style_search.py --series O --json | jq '.hits[].id'
    python3 scripts/style_search.py --grep 孤独        # 搜正文（一句话描述不够用时）
    python3 scripts/style_search.py --random 3
    python3 scripts/style_search.py --list-series

输出只给命中摘要与正文路径，不打印整篇提示词；需要正文时按返回的 path 读那一个 md。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "references" / "library"
INDEX = ROOT / "references" / "index.json"

# 命中权重：名称 > 标签 > 一句话 > 适合 > 英文名 > 分类
WEIGHTS = {"name": 6, "name_en": 4, "tags": 5, "desc": 3, "fit": 3, "cat": 1}


def load() -> dict:
    if not INDEX.exists():
        sys.exit(
            "缺少 references/index.json。\n"
            "先在 skill 根目录执行：python3 scripts/build_index.py"
        )
    return json.loads(INDEX.read_text(encoding="utf-8"))


def score(item: dict, terms: list[str]) -> int:
    total = 0
    name = item["name"].lower()
    name_en = item["name_en"].lower()
    tags = "、".join(item["tags"]).lower()
    desc = item["desc"].lower()
    fit = item["fit"].lower()
    cat = item["cat"].lower()
    for raw in terms:
        t = raw.lower()
        if not t:
            continue
        if t in name:
            total += WEIGHTS["name"] + (4 if name == t else 0)
        if t in name_en:
            total += WEIGHTS["name_en"]
        if t in tags:
            total += WEIGHTS["tags"]
        if t in desc:
            total += WEIGHTS["desc"]
        if t in fit:
            total += WEIGHTS["fit"]
        if t in cat:
            total += WEIGHTS["cat"]
    return total


def matches(item: dict, terms: list[str]) -> bool:
    if not terms:
        return True
    blob = " ".join(
        [item["name"], item["name_en"], item["desc"], item["fit"], item["cat"], " ".join(item["tags"])]
    ).lower()
    return all(t.lower() in blob for t in terms)


def excerpt(text: str, terms: list[str], width: int = 72) -> str:
    """取命中关键词的第一行正文，供判断是否真的相关。"""
    for line in text.splitlines():
        low = line.lower()
        if any(t.lower() in low for t in terms):
            line = line.strip().lstrip("-•*># ").strip()
            if line and not line.startswith("```"):
                return line[:width] + ("…" if len(line) > width else "")
    return ""


def breadcrumb(item: dict) -> str:
    """类别 + 子类；与类别名重复的部分省掉（如 Z 中国风 · 中国风、O 奥斯卡98部 · O 奥斯卡 98 部）。"""
    label = item["series_label"]
    squeeze = lambda s: s.replace(" ", "").replace("　", "")
    parts = [p for p in item["cat"].split(" · ") if p.strip()]
    if parts and squeeze(parts[0]) in squeeze(label):
        parts = parts[1:]
    parts = [p for p in parts if p not in label and squeeze(p) not in squeeze(label)]
    return f"{label} · {' · '.join(parts)}" if parts else label


def fmt(item: dict, width: int = 46, note: str = "") -> str:
    flags = "".join(
        [" [代码]" if item["has_code"] else "", " [静帧]" if item["still"] else ""]
    )
    desc = item["desc"] or item["fit"] or "—"
    if len(desc) > width:
        desc = desc[:width] + "…"
    tags = "·".join(item["tags"][:4])
    head = f"{item['id']:<4} {item['name'] or '（空条目）'}"
    extra = f"     ↳ {note}\n" if note else ""
    return (
        f"{head}\n"
        f"     {desc}{flags}\n"
        f"     {breadcrumb(item)}{(' · ' + tags) if tags else ''}\n"
        f"{extra}"
        f"     {item['file']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="检索代码动画风格库")
    ap.add_argument("terms", nargs="*", help="关键词，可用多个（须同时命中）")
    ap.add_argument("--series", help="限定类别，如 AG / M / K / Z / H / L / V / X / R / O")
    ap.add_argument("--code", action="store_true", help="只要有可运行参考实现的")
    ap.add_argument("--still", action="store_true", help="只要有静帧预览的")
    ap.add_argument("--id", help="按 ID 精确取一条")
    ap.add_argument("--random", type=int, metavar="N", help="随机推荐 N 条（可叠加其它筛选）")
    ap.add_argument("--grep", action="store_true", help="搜正文全文（默认只搜名称/描述/标签）")
    ap.add_argument("--limit", type=int, default=8, help="最多返回条数，默认 8")
    ap.add_argument("--include-empty", action="store_true", help="包含 8 条空白条目")
    ap.add_argument("--list-series", action="store_true", help="列出 10 个类别统计")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.limit < 1:
        ap.error("--limit 必须是 ≥1 的整数")
    if args.random is not None and args.random < 1:
        ap.error("--random 必须是 ≥1 的整数")

    index = load()
    styles = index["styles"]

    if args.list_series:
        for s in index["meta"]["series"]:
            print(f"{s['id']:<3} {s['label']:<22} {s['count']:>3} 条 · 可用 {s['usable']:>3} · 静帧 {s['with_still']:>3} · 代码 {s['with_code']:>2}")
            if s["note"]:
                print(f"    {s['note']}")
        print(f"\n合计 {index['meta']['total']} 条，可用 {index['meta']['usable']} 条")
        return 0

    pool = styles if args.include_empty else [x for x in styles if not x["empty"]]
    if args.series:
        key = args.series.replace("-", "").replace("_", "").upper()
        if key == "A":
            key = "AG"
        pool = [x for x in pool if x["series"] == key]
    if args.code:
        pool = [x for x in pool if x["has_code"]]
    if args.still:
        pool = [x for x in pool if x["still"]]
    if args.id:
        pool = [x for x in pool if x["id"].lower() == args.id.lower()]

    if not pool:
        if args.json:
            print(
                json.dumps(
                    {
                        "query": [],
                        "filters": {"series": args.series, "code": args.code, "still": args.still, "grep": args.grep},
                        "hits": [],
                        "error": f"没有符合条件的风格（id={args.id or '-'}，series={args.series or '-'}）",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        if args.id:
            hit = [x for x in styles if x["id"].lower() == args.id.lower()]
            if hit and hit[0]["empty"]:
                print(
                    f"{hit[0]['id']} 是原素材的空白占位（无名称、无提示词）。"
                    "要它出现在结果里加 --include-empty。",
                    file=sys.stderr,
                )
                return 1
            print(f"没有 ID 为 {args.id} 的风格。可用 --grep 按正文找，或 --list-series 看类别。", file=sys.stderr)
            return 1
        print("没有符合筛选条件的风格。可先 `--list-series` 看类别，或放宽 --series/--code。", file=sys.stderr)
        return 1

    terms = [t for t in args.terms if t.strip()]

    notes: dict[str, str] = {}
    if args.grep:
        if not terms:
            print("--grep 需要关键词，例如：--grep 孤独", file=sys.stderr)
            return 2
        keep, counts = [], {}
        for x in pool:
            text = (LIB / x["file"]).read_text(encoding="utf-8", errors="ignore")
            low = text.lower()
            if not all(t.lower() in low for t in terms):
                continue
            keep.append(x)
            counts[x["id"]] = sum(low.count(t.lower()) for t in terms)
            notes[x["id"]] = excerpt(text, terms)
        hits = sorted(keep, key=lambda x: (-counts[x["id"]], x["id"]))
    elif args.random:
        cand = [x for x in pool if matches(x, terms)]
        if not cand:
            print(f"没有命中：{' '.join(terms)}", file=sys.stderr)
            return 1
        hits = random.sample(cand, min(args.random, len(cand)))
    elif terms:
        hits = [x for x in pool if matches(x, terms)]
        strict = [x for x in hits if score(x, terms) > 0]
        hits = strict or hits
        hits.sort(key=lambda x: (-score(x, terms), x["id"]))
    else:
        hits = pool

    hits = hits[: args.limit]

    def emit_json() -> None:
        print(
            json.dumps(
                {
                    "query": terms,
                    "filters": {"series": args.series, "code": args.code, "still": args.still, "grep": args.grep},
                    "hits": [
                        {
                            "id": x["id"],
                            "name": x["name"],
                            "name_en": x["name_en"],
                            "series": x["series"],
                            "cat": x["cat"],
                            "desc": x["desc"],
                            "fit": x["fit"],
                            "tags": x["tags"],
                            "year": x["year"],
                            "has_code": x["has_code"],
                            "still": (str(LIB / x["still"]) if x["still"] else ""),
                            "excerpt": notes.get(x["id"], ""),
                            "path": str(LIB / x["file"]),
                        }
                        for x in hits
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if args.json:
        hit_rows = [
            x for x in hits
        ]
        if not hit_rows:
            print(
                json.dumps(
                    {
                        "query": terms,
                        "filters": {"series": args.series, "code": args.code, "still": args.still, "grep": args.grep},
                        "hits": [],
                        "error": f"没有命中：{' '.join(terms)}" if terms else "没有符合条件的风格",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        emit_json()
        return 0

    if not hits:
        print(f"没有命中：{' '.join(terms)}", file=sys.stderr)
        return 1

    print(f"命中 {len(hits)} 条（查询：{' '.join(terms) or '全部'}）\n")
    for item in hits:
        print(fmt(item, note=notes.get(item["id"], "")))
        print()
    print("读命中项正文取「风格提示词」一节；判定与输出契约见 references/RENDER.md。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
