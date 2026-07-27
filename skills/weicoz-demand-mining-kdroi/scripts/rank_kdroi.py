#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _to_float(raw: str):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "")
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _detect_columns(headers):
    norm_map = {_norm(h): h for h in headers}

    keyword_candidates = [
        "keyword",
        "keywords",
        "searchterm",
        "term",
        "query",
    ]
    volume_candidates = [
        "volume",
        "searchvolume",
        "avgmonthlysearches",
        "monthlysearches",
    ]
    kd_candidates = [
        "kd",
        "keyworddifficulty",
        "difficulty",
        "seodifficulty",
    ]
    cpc_candidates = [
        "cpc",
        "avgcpc",
        "costperclick",
    ]
    cpc_low_candidates = [
        "topofpagebidlowrange",
    ]
    cpc_high_candidates = [
        "topofpagebidhighrange",
    ]

    def find_first(candidates):
        for c in candidates:
            if c in norm_map:
                return norm_map[c]
        return None

    keyword_col = find_first(keyword_candidates)
    volume_col = find_first(volume_candidates)
    kd_col = find_first(kd_candidates)
    cpc_col = find_first(cpc_candidates)
    cpc_low_col = find_first(cpc_low_candidates)
    cpc_high_col = find_first(cpc_high_candidates)

    return {
        "keyword": keyword_col,
        "volume": volume_col,
        "kd": kd_col,
        "cpc": cpc_col,
        "cpc_low": cpc_low_col,
        "cpc_high": cpc_high_col,
    }


def _pick_cpc(row, cols):
    direct = _to_float(row.get(cols["cpc"])) if cols["cpc"] else None
    if direct is not None:
        return direct
    low = _to_float(row.get(cols["cpc_low"])) if cols["cpc_low"] else None
    high = _to_float(row.get(cols["cpc_high"])) if cols["cpc_high"] else None
    if low is not None and high is not None:
        return (low + high) / 2
    if low is not None:
        return low
    if high is not None:
        return high
    return None


def _read_rows(path: Path):
    # 优先 utf-8-sig，兼容 Excel 导出的 BOM
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    return headers, rows


def main():
    parser = argparse.ArgumentParser(
        description="Rank keyword CSV by KDRoi = Volume * CPC / KD"
    )
    parser.add_argument("--in", dest="input_csv", required=True, help="Input CSV path")
    parser.add_argument("--out", dest="output_csv", required=True, help="Output CSV path")
    parser.add_argument("--min-kd", type=float, default=0.0)
    parser.add_argument("--max-kd", type=float, default=29.0)
    parser.add_argument("--min-volume", type=float, default=200.0)
    parser.add_argument("--max-volume", type=float, default=10000.0)
    parser.add_argument("--min-cpc", type=float, default=0.1)
    parser.add_argument("--kd-floor", type=float, default=1.0)
    parser.add_argument("--top", type=int, default=0, help="Keep top N rows, 0 = all")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    headers, rows = _read_rows(input_path)
    if not headers:
        raise SystemExit("ERROR: CSV has no header row.")

    cols = _detect_columns(headers)
    missing_required = [
        name for name in ("keyword", "volume", "kd")
        if not cols.get(name)
    ]
    if missing_required:
        raise SystemExit(
            "ERROR: Missing required columns: "
            + ", ".join(missing_required)
            + ". Found headers: "
            + ", ".join(headers)
        )
    if not cols["cpc"] and not cols["cpc_low"] and not cols["cpc_high"]:
        raise SystemExit(
            "ERROR: Missing CPC columns. Need one of: cpc/avg cpc/cost per click "
            "or top of page bid low/high range."
        )

    kept = []
    skipped = 0

    for row in rows:
        keyword = (row.get(cols["keyword"]) or "").strip()
        volume = _to_float(row.get(cols["volume"]))
        kd = _to_float(row.get(cols["kd"]))
        cpc = _pick_cpc(row, cols)

        if not keyword or volume is None or kd is None or cpc is None:
            skipped += 1
            continue

        if kd < args.min_kd or kd > args.max_kd:
            continue
        if volume < args.min_volume or volume > args.max_volume:
            continue
        if cpc < args.min_cpc:
            continue
        if "near me" in keyword.lower():
            continue

        kd_for_calc = max(kd, args.kd_floor)
        kdroi = (volume * cpc) / kd_for_calc

        kept.append(
            {
                "keyword": keyword,
                "volume": int(volume) if volume.is_integer() else round(volume, 2),
                "cpc": round(cpc, 4),
                "kd": round(kd, 4),
                "kdroi": round(kdroi, 4),
            }
        )

    kept.sort(key=lambda x: x["kdroi"], reverse=True)
    if args.top and args.top > 0:
        kept = kept[: args.top]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "volume", "cpc", "kd", "kdroi"])
        writer.writeheader()
        writer.writerows(kept)

    print(
        f"DONE: input={len(rows)}, ranked={len(kept)}, skipped_incomplete={skipped}, "
        f"output={output_path}"
    )


if __name__ == "__main__":
    main()
