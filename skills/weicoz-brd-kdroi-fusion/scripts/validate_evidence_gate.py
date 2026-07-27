#!/usr/bin/env python3
"""Validate evidence quality gate from evidence-log.csv."""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


PAIN_MIN_MENTIONS = 3
PAIN_MIN_PLATFORMS = 2

SWITCH_PATTERN = re.compile(
    r"switched from|switch(?:ed)? to|migrat(?:e|ed|ing)|alternative", re.IGNORECASE
)
WTP_PATTERN = re.compile(
    r"\$\d|pricing|price|paid|pay|willing to pay|付费|价格|每月花费|cost|monthly spend",
    re.IGNORECASE,
)


def _normalize_text(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip()).lower()


def _normalize_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", _normalize_text(raw))


def _route_key(raw: str) -> str:
    text = (raw or "").strip().upper()
    match = re.match(r"^([ABCD])(?:$|[^A-Z0-9])", text)
    return match.group(1) if match else ""


def _load_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _analyze(rows):
    pain_groups = defaultdict(lambda: {"count": 0, "platforms": set(), "sample": ""})
    routes = set()
    has_switch = False
    has_wtp = False
    valid_source_rows = 0

    for row in rows:
        route = _route_key(row.get("route", ""))
        if route:
            routes.add(route)

        source_url = (row.get("source_url") or "").strip()
        if source_url:
            valid_source_rows += 1

        combined = " | ".join(
            [
                row.get("query_or_page") or "",
                row.get("pain_point_or_insight") or "",
                row.get("quote_or_note") or "",
            ]
        )
        if SWITCH_PATTERN.search(combined):
            has_switch = True

        signal_type = _normalize_text(row.get("signal_type", ""))
        if signal_type in {"wtp", "pricing", "transaction"} or WTP_PATTERN.search(combined):
            has_wtp = True

        pain = (row.get("pain_point_or_insight") or "").strip()
        platform = (row.get("platform") or "").strip() or "unknown"
        if not pain:
            continue
        if signal_type and signal_type not in {"pain", "wtp", "pricing", "transaction"}:
            continue

        key = _normalize_key(pain)
        if not key:
            continue
        group = pain_groups[key]
        group["count"] += 1
        group["platforms"].add(platform)
        if not group["sample"]:
            group["sample"] = pain

    passed_pains = []
    for data in pain_groups.values():
        platform_count = len(data["platforms"])
        if data["count"] >= PAIN_MIN_MENTIONS and platform_count >= PAIN_MIN_PLATFORMS:
            passed_pains.append(
                {
                    "pain": data["sample"],
                    "mentions": data["count"],
                    "platform_count": platform_count,
                }
            )

    passed_pains.sort(key=lambda x: (x["mentions"], x["platform_count"]), reverse=True)

    validated_pain_points = len(passed_pains) > 0
    route_coverage_ok = len(routes) >= 3
    mandatory_pass = validated_pain_points and has_switch and has_wtp

    return {
        "summary": {
            "rows_total": len(rows),
            "rows_with_source_url": valid_source_rows,
            "routes_present": sorted(routes),
            "route_coverage_ok": route_coverage_ok,
            "validated_pain_points": validated_pain_points,
            "switch_evidence_found": has_switch,
            "wtp_evidence_found": has_wtp,
            "mandatory_gate_pass": mandatory_pass,
        },
        "thresholds": {
            "pain_min_mentions": PAIN_MIN_MENTIONS,
            "pain_min_platforms": PAIN_MIN_PLATFORMS,
        },
        "passed_pain_groups": passed_pains,
    }


def _update_scoring(path: Path, report):
    data = json.loads(path.read_text(encoding="utf-8"))
    go_checks = data.setdefault("go_checks", {})
    no_go_signals = data.setdefault("no_go_signals", {})

    go_checks["validated_pain_points"] = bool(report["summary"]["validated_pain_points"])
    go_checks["wtp_validated"] = bool(report["summary"]["wtp_evidence_found"])
    no_go_signals["cannot_find_real_pain"] = not bool(report["summary"]["validated_pain_points"])

    note = (
        "Updated by validate_evidence_gate.py: "
        f"pain={go_checks['validated_pain_points']}, "
        f"wtp={go_checks['wtp_validated']}."
    )
    data["notes"] = note
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Validate evidence quality gate")
    parser.add_argument("--evidence", required=True, help="Path to evidence-log.csv")
    parser.add_argument("--out", help="Path to write JSON report")
    parser.add_argument("--scoring", help="Optional scoring-input.json to update")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if mandatory gate fails",
    )
    args = parser.parse_args()

    evidence_path = Path(args.evidence).resolve()
    if not evidence_path.exists():
        print(f"ERROR: evidence file not found: {evidence_path}")
        return 1

    rows = _load_rows(evidence_path)
    report = _analyze(rows)

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if args.scoring:
        scoring_path = Path(args.scoring).resolve()
        if not scoring_path.exists():
            print(f"ERROR: scoring file not found: {scoring_path}")
            return 1
        _update_scoring(scoring_path, report)

    print("# Evidence Gate Summary")
    print(f"rows_total: {report['summary']['rows_total']}")
    print(f"rows_with_source_url: {report['summary']['rows_with_source_url']}")
    print(f"routes_present: {', '.join(report['summary']['routes_present']) or '(none)'}")
    print(f"route_coverage_ok: {report['summary']['route_coverage_ok']}")
    print(f"validated_pain_points: {report['summary']['validated_pain_points']}")
    print(f"switch_evidence_found: {report['summary']['switch_evidence_found']}")
    print(f"wtp_evidence_found: {report['summary']['wtp_evidence_found']}")
    print(f"mandatory_gate_pass: {report['summary']['mandatory_gate_pass']}")

    if args.strict and not report["summary"]["mandatory_gate_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
