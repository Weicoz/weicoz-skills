#!/usr/bin/env python3
"""Search bundled GooseDesigns catalog locally."""
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1] / "references" / "goosedesigns"
files = list(ROOT.glob("*.md"))
query = " ".join(sys.argv[1:]).strip().lower()
terms = [x for x in re.findall(r"[\w-]+", query) if x]
if not terms:
    print("usage: goose_search.py <keywords>", file=sys.stderr); raise SystemExit(2)
hits = []
for p in files:
    text = p.read_text(errors="ignore")
    low = text.lower()
    score = sum(low.count(t) for t in terms)
    if score: hits.append((score, p, text))
for score, p, text in sorted(hits, reverse=True)[:12]:
    lines = [x.strip() for x in text.splitlines() if any(t in x.lower() for t in terms)]
    print(f"## {p.stem} (score={score})")
    print("\n".join(lines[:8]))
    print()
