#!/usr/bin/env python3
"""Client-ready gate: forbid pending/undecided wording in deliverables."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

# 与 weicoz-demand-mindmap-organizer/scripts/validate_xmind.py 的 CLIENT_BLOCKERS/CLIENT_ALLOWED 保持一致
CLIENT_BLOCKERS = r"待确认|待定|未定|暂定|客户需确认|参考|以最终为准|待客户|另行公布|后续再定"
CLIENT_ALLOWED = ["待确认收货", "待确认付款", "待确认订单", "参考价", "参考售价"]

EXTENSIONS = {".md", ".txt", ".csv", ".xlsx", ".xmind"}
BLOCKER_RE = re.compile(CLIENT_BLOCKERS)
CONTEXT = 15


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_hits(text: str, old_terms: list[str]) -> list[tuple[str, str]]:
    masked = text
    for phrase in CLIENT_ALLOWED:
        masked = masked.replace(phrase, "\0" * len(phrase))
    hits = [(m.group(0), _snippet(text, m.start(), m.end())) for m in BLOCKER_RE.finditer(masked)]
    for term in old_terms:
        start = 0
        while term and (index := text.find(term, start)) != -1:
            hits.append((term, _snippet(text, index, index + len(term))))
            start = index + len(term)
    return hits


def _snippet(text: str, start: int, end: int) -> str:
    return text[max(0, start - CONTEXT):end + CONTEXT].replace("\n", " ")


def text_units(path: Path) -> Iterator[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".csv"}:
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            yield f"L{number}", line
    elif suffix == ".xlsx":
        yield from xlsx_units(path)
    elif suffix == ".xmind":
        yield from xmind_units(path)


def xlsx_units(path: Path) -> Iterator[tuple[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in root:
                shared.append("".join(t.text or "" for t in si.iter() if local(t.tag) == "t"))
        used: set[int] = set()
        sheets = sorted(n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/[^/]+\.xml", n))
        for sheet_name in sheets:
            label = Path(sheet_name).stem
            root = ET.fromstring(archive.read(sheet_name))
            for cell in root.iter():
                if local(cell.tag) != "c":
                    continue
                ref = f"{label}!{cell.get('r', '?')}"
                kind = cell.get("t")
                if kind == "s":
                    value = next((c.text for c in cell if local(c.tag) == "v"), None)
                    if value is not None and value.isdigit() and int(value) < len(shared):
                        used.add(int(value))
                        yield ref, shared[int(value)]
                else:
                    text = "".join(t.text or "" for t in cell.iter() if local(t.tag) == "t")
                    if text:
                        yield ref, text
        for index, value in enumerate(shared):
            if index not in used and value:
                yield f"sharedStrings#{index}", value


def walk_topic(topic: dict[str, Any], trail: list[str]) -> Iterator[tuple[str, str]]:
    title = topic.get("title")
    title = title if isinstance(title, str) else ""
    path = trail + [title]
    loc = ">".join(path)
    if title:
        yield loc, title
    notes = topic.get("notes")
    if isinstance(notes, dict):
        content = (notes.get("plain") or {}).get("content") if isinstance(notes.get("plain"), dict) else None
        if isinstance(content, str) and content:
            yield f"{loc}[notes]", content
    children = topic.get("children")
    if isinstance(children, dict):
        for group in children.values():
            if isinstance(group, list):
                for child in group:
                    if isinstance(child, dict):
                        yield from walk_topic(child, path)


def xmind_units(path: Path) -> Iterator[tuple[str, str]]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "content.json" in names:
            sheets = json.loads(archive.read("content.json"))
            for sheet in sheets if isinstance(sheets, list) else []:
                root = sheet.get("rootTopic") if isinstance(sheet, dict) else None
                if isinstance(root, dict):
                    yield from walk_topic(root, [])
        elif "content.xml" in names:
            root = ET.fromstring(archive.read("content.xml"))
            number = 0
            for node in root.iter():
                if node.text and node.text.strip():
                    number += 1
                    yield f"text#{number}", node.text.strip()


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS))
        elif path.is_file():
            files.append(path)
        else:
            print(f"missing path: {path}", file=sys.stderr)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories (.md .txt .csv .xlsx .xmind)")
    parser.add_argument("--old-term", action="append", default=[], help="old wording that must have 0 hits")
    args = parser.parse_args()

    files = collect(args.paths)
    if not files:
        print("no files collected: nothing was checked", file=sys.stderr)
        return 1
    total = 0
    for file in files:
        try:
            for loc, text in text_units(file):
                for word, snippet in find_hits(text, args.old_term):
                    total += 1
                    print(f"{file}:{loc}: {word} | {snippet}")
        except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
            print(f"{file}: unreadable ({error})", file=sys.stderr)
            return 1
    if total:
        print(f"FAIL {total} hits in {len(files)} files")
        return 1
    print(f"PASS {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
