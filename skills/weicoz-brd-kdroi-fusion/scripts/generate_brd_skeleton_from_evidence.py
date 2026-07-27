#!/usr/bin/env python3
"""Generate BRD draft skeleton from evidence-log.csv."""

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


def normalize_text(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def normalize_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", normalize_text(raw).lower())


def route_bucket(raw: str) -> str:
    text = (raw or "").strip().upper()
    match = re.match(r"^([ABCD])(?:$|[^A-Z0-9])", text)
    if not match:
        return "unknown"
    return match.group(1)


def load_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def aggregate(rows):
    route_counts = Counter()
    segment_counts = Counter()
    platform_counts = Counter()
    confidence_counts = Counter()
    pain_map = defaultdict(
        lambda: {"sample": "", "mentions": 0, "platforms": set(), "evidence": []}
    )
    wtp_items = []
    switch_items = []

    for row in rows:
        route = route_bucket(row.get("route", ""))
        route_counts[route] += 1

        platform = normalize_text(row.get("platform", "")) or "unknown"
        platform_counts[platform] += 1

        confidence = normalize_text(row.get("confidence", "")).lower() or "unknown"
        confidence_counts[confidence] += 1

        signal_type = normalize_text(row.get("signal_type", "")).lower()
        if signal_type in {"pain", "wtp", "pricing", "transaction"}:
            segment = normalize_text(row.get("user_segment", ""))
            if segment:
                segment_counts[segment] += 1

        query = normalize_text(row.get("query_or_page", ""))
        pain = normalize_text(row.get("pain_point_or_insight", ""))
        quote = normalize_text(row.get("quote_or_note", ""))
        source = normalize_text(row.get("source_url", ""))
        recency = normalize_text(row.get("recency_window", ""))

        if signal_type in {"wtp", "pricing", "transaction"}:
            wtp_items.append(
                {
                    "platform": platform,
                    "pain": pain,
                    "quote": quote,
                    "source": source,
                    "recency": recency,
                }
            )

        combined = f"{query} {pain} {quote}"
        if re.search(r"switched from|switch(?:ed)? to|migrat(?:e|ed|ing)|alternative", combined, re.IGNORECASE):
            switch_items.append(
                {
                    "platform": platform,
                    "text": pain or quote or query,
                    "source": source,
                }
            )

        if signal_type not in {"pain", "wtp", "pricing", "transaction"}:
            continue
        if not pain:
            continue

        key = normalize_key(pain)
        if not key:
            continue
        item = pain_map[key]
        item["sample"] = item["sample"] or pain
        item["mentions"] += 1
        item["platforms"].add(platform)
        if quote:
            item["evidence"].append(quote)

    pain_list = []
    for item in pain_map.values():
        pain_list.append(
            {
                "pain": item["sample"],
                "mentions": item["mentions"],
                "platform_count": len(item["platforms"]),
                "platforms": sorted(item["platforms"]),
                "evidence": item["evidence"][:2],
            }
        )

    pain_list.sort(key=lambda x: (x["mentions"], x["platform_count"]), reverse=True)

    return {
        "route_counts": route_counts,
        "segment_counts": segment_counts,
        "platform_counts": platform_counts,
        "confidence_counts": confidence_counts,
        "pain_list": pain_list,
        "wtp_items": wtp_items,
        "switch_items": switch_items,
    }


def format_markdown(data, rows_total: int, top_pains: int, top_segments: int):
    route_counts = data["route_counts"]
    segment_counts = data["segment_counts"]
    platform_counts = data["platform_counts"]
    confidence_counts = data["confidence_counts"]
    pain_list = data["pain_list"][:top_pains]
    wtp_items = data["wtp_items"][:5]
    switch_items = data["switch_items"][:5]

    lines = []
    lines.append("# BRD Draft (Auto Generated From Evidence)")
    lines.append("")
    lines.append("> 这是自动草稿，用于加速整理；最终结论请人工复核。")
    lines.append("")
    lines.append("## 0. Evidence Snapshot")
    lines.append("")
    lines.append(f"- rows_total: {rows_total}")
    lines.append(
        f"- route_distribution: A={route_counts.get('A', 0)}, B={route_counts.get('B', 0)}, C={route_counts.get('C', 0)}, D={route_counts.get('D', 0)}, unknown={route_counts.get('unknown', 0)}"
    )
    lines.append(
        "- confidence_distribution: "
        + ", ".join(f"{k}={v}" for k, v in confidence_counts.items())
    )
    lines.append(
        "- top_platforms: "
        + ", ".join(f"{k}({v})" for k, v in platform_counts.most_common(6))
    )
    lines.append("")
    lines.append("## 1. Problem Hypothesis (Draft)")
    lines.append("")
    lines.append("- Product idea: ")
    lines.append("- Core user pain hypothesis: ")
    lines.append("- Why now: ")
    lines.append("")
    lines.append("## 2. Candidate ICP (From user_segment)")
    lines.append("")
    for seg, cnt in segment_counts.most_common(top_segments):
        lines.append(f"- {seg} ({cnt})")
    if not segment_counts:
        lines.append("- (no user_segment evidence yet)")
    lines.append("")
    lines.append("## 3. Pain Map (Top candidates)")
    lines.append("")
    lines.append("| Pain | Mentions | Platform Count | Platforms |")
    lines.append("| --- | --- | --- | --- |")
    if pain_list:
        for item in pain_list:
            platforms = ", ".join(item["platforms"])
            lines.append(
                f"| {item['pain']} | {item['mentions']} | {item['platform_count']} | {platforms} |"
            )
    else:
        lines.append("| (no pain evidence yet) | 0 | 0 | - |")
    lines.append("")
    lines.append("## 4. WTP Evidence (Pricing / Transaction)")
    lines.append("")
    if wtp_items:
        for item in wtp_items:
            source = item["source"] or "(no source)"
            snippet = item["quote"] or item["pain"] or "(empty)"
            lines.append(f"- [{item['platform']}] {snippet} | {source}")
    else:
        lines.append("- (no wtp evidence yet)")
    lines.append("")
    lines.append("## 5. Migration Signals (Switch / Alternative)")
    lines.append("")
    if switch_items:
        for item in switch_items:
            source = item["source"] or "(no source)"
            lines.append(f"- [{item['platform']}] {item['text']} | {source}")
    else:
        lines.append("- (no switch evidence yet)")
    lines.append("")
    lines.append("## 6. Decision Pre-check")
    lines.append("")
    if pain_list:
        top = pain_list[0]
        pain_gate_pass = top["mentions"] >= 3 and top["platform_count"] >= 2
    else:
        pain_gate_pass = False
    wtp_gate_pass = len(wtp_items) > 0
    switch_gate_pass = len(switch_items) > 0
    lines.append(f"- pain_gate_pass: {pain_gate_pass}")
    lines.append(f"- wtp_gate_pass: {wtp_gate_pass}")
    lines.append(f"- switch_gate_pass: {switch_gate_pass}")
    lines.append(
        "- recommendation: "
        + ("进入完整评分（score_go_no_go）" if (pain_gate_pass and wtp_gate_pass) else "先补证据再评分")
    )
    lines.append("")
    lines.append("## 7. Next Actions")
    lines.append("")
    lines.append("- 补齐缺失证据（若有）并回填 evidence-log.csv。")
    lines.append("- 跑 validate_evidence_gate.py 更新 scoring-input.json。")
    lines.append("- 跑 score_go_no_go.py 输出 GO / HOLD / NO-GO。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Generate BRD draft markdown from evidence log"
    )
    parser.add_argument("--evidence", required=True, help="Path to evidence-log.csv")
    parser.add_argument("--out", required=True, help="Output markdown path")
    parser.add_argument("--top-pains", type=int, default=8, help="Top pain rows")
    parser.add_argument("--top-segments", type=int, default=6, help="Top ICP segments")
    args = parser.parse_args()

    evidence_path = Path(args.evidence).resolve()
    if not evidence_path.exists():
        raise SystemExit(f"ERROR: evidence file not found: {evidence_path}")

    rows = load_rows(evidence_path)
    data = aggregate(rows)
    content = format_markdown(
        data=data,
        rows_total=len(rows),
        top_pains=max(args.top_pains, 1),
        top_segments=max(args.top_segments, 1),
    )

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    print(f"DONE: rows={len(rows)}, output={out_path}")


if __name__ == "__main__":
    main()
