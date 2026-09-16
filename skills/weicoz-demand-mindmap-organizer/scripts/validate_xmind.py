#!/usr/bin/env python3
"""Validate XMind package structure and minimum map density."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_MEMBERS = {"content.json", "metadata.json", "manifest.json"}
PROFILES = {
    "small": {"first_level": 3, "nodes": 20, "depth": 2},
    "normal": {"first_level": 5, "nodes": 50, "depth": 3},
    "large": {"first_level": 7, "nodes": 100, "depth": 3},
}


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
    if count < limits["nodes"]:
        failures.append(f"topics {count} < {limits['nodes']}")
    if depth < limits["depth"]:
        failures.append(f"depth {depth} < {limits['depth']}")
    missing_branches = [title for title in args.require if title not in first_level]
    if missing_branches:
        failures.append(f"missing first-level branches: {', '.join(missing_branches)}")
    blank_titles = sum(1 for title in titles if not isinstance(title, str) or not title.strip())
    if blank_titles:
        failures.append(f"blank topic titles: {blank_titles}")

    print(json.dumps({
        "root": root["title"],
        "first_level": len(first_level),
        "topics": count,
        "depth": depth,
        "branches": first_level,
        "profile": args.profile,
    }, ensure_ascii=False))
    if failures:
        print("; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
