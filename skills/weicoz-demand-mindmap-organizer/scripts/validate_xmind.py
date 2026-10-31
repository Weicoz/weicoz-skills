#!/usr/bin/env python3
"""Validate XMind package structure and minimum map density."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_MEMBERS = {"content.json", "metadata.json", "manifest.json"}
PROFILES = {
    "small": {"first_level": 3, "nodes": 20, "max_nodes": 45, "depth": 2},
    "normal": {"first_level": 5, "nodes": 50, "max_nodes": 100, "depth": 3},
    "large": {"first_level": 7, "nodes": 80, "max_nodes": 200, "depth": 3},
}
MAX_FIRST_LEVEL = 8
# 与 weicoz-jy-design-demand-archive/scripts/check_client_ready.py 的 CLIENT_BLOCKERS/CLIENT_ALLOWED 保持一致
CLIENT_BLOCKERS = r"待确认|待定|未定|暂定|客户需确认|参考|以最终为准|待客户|另行公布|后续再定"
CLIENT_ALLOWED = ["待确认收货", "待确认付款", "待确认订单", "参考价", "参考售价"]


def client_hits(root: dict[str, Any]) -> list[str]:
    hits: list[str] = []

    def walk(topic: dict[str, Any], trail: list[str]) -> None:
        title = topic.get("title")
        title = title if isinstance(title, str) else ""
        path = trail + [title]
        texts = [title]
        notes = topic.get("notes")
        if isinstance(notes, dict) and isinstance(notes.get("plain"), dict):
            content = notes["plain"].get("content")
            if isinstance(content, str):
                texts.append(content)
        for text in texts:
            masked = text
            for phrase in CLIENT_ALLOWED:
                masked = masked.replace(phrase, "\0" * len(phrase))
            for match in re.finditer(CLIENT_BLOCKERS, masked):
                hits.append(f"{'>'.join(path)}: {match.group(0)}")
        for child in children(topic):
            walk(child, path)

    walk(root, [])
    return hits


def children(topic: dict[str, Any]) -> list[dict[str, Any]]:
    return topic.get("children", {}).get("attached", [])


def inspect(topic: dict[str, Any], level: int = 1) -> tuple[int, int, list[str]]:
    titles = [topic.get("title", "")]
    count = 1
    depth = level
    for child in children(topic):
        child_count, child_depth, child_titles = inspect(child, level + 1)
        count += child_count
        depth = max(depth, child_depth)
        titles.extend(child_titles)
    return count, depth, titles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xmind", type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="normal")
    parser.add_argument("--require", action="append", default=[], help="required first-level branch title")
    parser.add_argument(
        "--max-topics",
        type=int,
        default=None,
        help="topic ceiling for readability; 0 disables the check (default: profile ceiling)",
    )
    parser.add_argument(
        "--max-first-level",
        type=int,
        default=MAX_FIRST_LEVEL,
        help=f"first-level branch ceiling; 0 disables the check (default: {MAX_FIRST_LEVEL})",
    )
    parser.add_argument("--client", action="store_true", help="fail on pending/undecided wording in titles and notes")
    args = parser.parse_args()

    if not args.xmind.is_file():
        print(f"missing file: {args.xmind}", file=sys.stderr)
        return 1

    try:
        with zipfile.ZipFile(args.xmind) as archive:
            names = set(archive.namelist())
            missing = REQUIRED_MEMBERS - names
            if missing:
                raise ValueError(f"missing package members: {', '.join(sorted(missing))}")
            sheets = json.loads(archive.read("content.json"))
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(f"invalid XMind package: {error}", file=sys.stderr)
        return 1

    if not isinstance(sheets, list) or not sheets or not isinstance(sheets[0], dict):
        print("content.json has no usable sheet", file=sys.stderr)
        return 1
    root = sheets[0].get("rootTopic")
    if not isinstance(root, dict) or not isinstance(root.get("title"), str) or not root["title"].strip():
        print("missing root topic title", file=sys.stderr)
        return 1

    count, depth, titles = inspect(root)
    first_level = [topic.get("title", "") for topic in children(root)]
    limits = PROFILES[args.profile]
    failures = []
    if len(first_level) < limits["first_level"]:
        failures.append(f"first-level branches {len(first_level)} < {limits['first_level']}")
    if args.max_first_level and len(first_level) > args.max_first_level:
        failures.append(f"first-level branches {len(first_level)} > {args.max_first_level} ceiling")
    if count < limits["nodes"]:
        failures.append(f"topics {count} < {limits['nodes']}")
    ceiling = args.max_topics if args.max_topics is not None else limits["max_nodes"]
    if ceiling and count > ceiling:
        failures.append(
            f"topics {count} > {ceiling} ceiling; move detail into the requirements doc instead of merging rows"
        )
    if depth < limits["depth"]:
        failures.append(f"depth {depth} < {limits['depth']}")
    missing_branches = [title for title in args.require if title not in first_level]
    if missing_branches:
        failures.append(f"missing first-level branches: {', '.join(missing_branches)}")
    blank_titles = sum(1 for title in titles if not isinstance(title, str) or not title.strip())
    if blank_titles:
        failures.append(f"blank topic titles: {blank_titles}")

    if args.client:
        hits = client_hits(root)
        if hits:
            shown = "; ".join(hits[:10])
            more = f" (+{len(hits) - 10} more)" if len(hits) > 10 else ""
            failures.append(f"client-blocking wording {len(hits)}: {shown}{more}")

    print(json.dumps({
        "root": root["title"],
        "first_level": len(first_level),
        "topics": count,
        "depth": depth,
        "ceiling": args.max_topics if args.max_topics is not None else limits["max_nodes"],
        "branches": first_level,
        "profile": args.profile,
        "client": args.client,
    }, ensure_ascii=False))
    if failures:
        print("; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
