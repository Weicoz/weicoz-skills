#!/usr/bin/env python3
"""Build a real XMind JSON package from a small outline JSON document."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_MEMBERS = {"content.json", "metadata.json", "manifest.json"}


def new_id() -> str:
    return uuid.uuid4().hex


def load_outline(source: str) -> dict[str, Any]:
    if source == "-":
        data = json.load(sys.stdin)
    else:
        with Path(source).open(encoding="utf-8") as handle:
            data = json.load(handle)

    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        raise ValueError("outline root must be an object with a non-empty string title")
    if not data["title"].strip():
        raise ValueError("outline title cannot be empty")

    children = data.get("children", data.get("branches", []))
    if not isinstance(children, list):
        raise ValueError("outline children/branches must be an array")
    data["children"] = children
    return data


def normalize_node(value: Any, location: str) -> dict[str, Any]:
    if isinstance(value, str):
        title = value.strip()
        children: list[Any] = []
    elif isinstance(value, dict):
        title = value.get("title")
        children = value.get("children", [])
        if not isinstance(title, str) or not isinstance(children, list):
            raise ValueError(f"{location} must contain string title and array children")
        title = title.strip()
    else:
        raise ValueError(f"{location} must be a string or object")

    if not title:
        raise ValueError(f"{location} title cannot be empty")
    return {"title": title, "children": children}


def build_topic(value: Any, location: str) -> dict[str, Any]:
    node = normalize_node(value, location)
    topic: dict[str, Any] = {"id": new_id(), "title": node["title"]}
    if node["children"]:
        topic["children"] = {
            "attached": [
                build_topic(child, f"{location}.children[{index}]")
                for index, child in enumerate(node["children"])
            ]
        }
    return topic


def load_template(path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "content.json" not in names:
            raise ValueError("template must use XMind JSON format with content.json")
        content = json.loads(archive.read("content.json"))
        if not isinstance(content, list) or not content:
            raise ValueError("template content.json must contain at least one sheet")
        files = {
            info.filename: archive.read(info.filename)
            for info in archive.infolist()
            if not info.is_dir() and info.filename not in {"content.json", "content.xml"}
        }
    files = strip_thumbnails(files)
    return files, copy.deepcopy(content[0])


def strip_thumbnails(files: dict[str, bytes]) -> dict[str, bytes]:
    files = {name: data for name, data in files.items() if not name.startswith("Thumbnails/")}
    raw = files.get("manifest.json")
    if raw is None:
        return files
    try:
        manifest = json.loads(raw)
        entries = manifest["file-entries"]
        if not isinstance(entries, dict):
            return files
    except (ValueError, KeyError, TypeError):
        return files
    manifest["file-entries"] = {k: v for k, v in entries.items() if not k.startswith("Thumbnails/")}
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode()
    return files


def build_sheet(outline: dict[str, Any], template_sheet: dict[str, Any] | None) -> dict[str, Any]:
    if template_sheet:
        sheet = template_sheet
        old_root = sheet.get("rootTopic", {})
        root = {
            key: copy.deepcopy(value)
            for key, value in old_root.items()
            if key not in {"id", "title", "children", "notes", "labels", "markers"}
        }
    else:
        sheet = {"class": "sheet", "title": "Map"}
        root = {"class": "topic", "structureClass": "org.xmind.ui.map.clockwise"}

    sheet["id"] = new_id()
    sheet["revisionId"] = new_id()
    root["id"] = new_id()
    root["title"] = outline["title"].strip()
    root.setdefault("class", "topic")
    root.setdefault("structureClass", "org.xmind.ui.map.clockwise")
    if outline["children"]:
        root["children"] = {
            "attached": [
                build_topic(child, f"children[{index}]")
                for index, child in enumerate(outline["children"])
            ]
        }
    else:
        root.pop("children", None)
    sheet["rootTopic"] = root
    return sheet


def default_metadata() -> bytes:
    value = {
        "dataStructureVersion": "2",
        "creator": {"name": "Codex", "version": "1"},
        "layoutEngineVersion": "4",
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def default_manifest() -> bytes:
    value = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def write_xmind(
    output: Path,
    outline: dict[str, Any],
    template: Path | None,
) -> None:
    files: dict[str, bytes] = {}
    template_sheet = None
    if template:
        files, template_sheet = load_template(template)

    sheet = build_sheet(outline, template_sheet)
    content = json.dumps([sheet], ensure_ascii=False, indent=2).encode()
    files.setdefault("metadata.json", default_metadata())
    files.setdefault("manifest.json", default_manifest())
    files["content.json"] = content

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def ascii_lines(children: list[Any], prefix: str, location: str) -> list[str]:
    lines: list[str] = []
    for index, child in enumerate(children):
        node = normalize_node(child, f"{location}[{index}]")
        last = index == len(children) - 1
        lines.append(f"{prefix}{'└─ ' if last else '├─ '}{node['title']}")
        lines.extend(ascii_lines(node["children"], prefix + ("   " if last else "│  "), f"{location}[{index}].children"))
    return lines


def markdown_lines(children: list[Any], depth: int, location: str) -> list[str]:
    lines: list[str] = []
    for index, child in enumerate(children):
        node = normalize_node(child, f"{location}[{index}]")
        if depth == 0:
            lines.append(f"## {node['title']}")
        else:
            lines.append(f"{'  ' * (depth - 1)}- {node['title']}")
        lines.extend(markdown_lines(node["children"], depth + 1, f"{location}[{index}].children"))
    return lines


def count_topics(children: list[Any]) -> int:
    return sum(1 + count_topics(normalize_node(c, "x")["children"]) for c in children)


def write_text_exports(outline: dict[str, Any], ascii_path: Path | None, md_path: Path | None) -> None:
    title = outline["title"].strip()
    children = outline["children"]
    for path, text in (
        (ascii_path, "\n".join([title] + ascii_lines(children, "", "children")) + "\n"),
        (md_path, "\n".join([f"# {title}", ""] + markdown_lines(children, 0, "children")) + "\n"),
    ):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


def validate_xmind(path: Path, expected_title: str) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated XMind package contains a corrupt member")
        names = set(archive.namelist())
        missing = REQUIRED_MEMBERS - names
        if missing:
            raise ValueError(f"generated XMind package missing: {', '.join(sorted(missing))}")
        content = json.loads(archive.read("content.json"))
        actual_title = content[0]["rootTopic"]["title"]
        if actual_title != expected_title:
            raise ValueError("generated XMind root title does not match outline")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("outline", help="outline JSON path, or - for stdin")
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument("--template", type=Path, help="existing JSON-format .xmind style source")
    parser.add_argument("--ascii", type=Path, help="also write an ASCII tree text file")
    parser.add_argument("--markdown", type=Path, help="also write a Markdown outline file")
    args = parser.parse_args()

    if args.output.suffix.lower() != ".xmind":
        parser.error("--output must end with .xmind")
    if args.template and args.template.suffix.lower() != ".xmind":
        parser.error("--template must be a .xmind file")

    try:
        outline = load_outline(args.outline)
        write_xmind(args.output, outline, args.template)
        validate_xmind(args.output, outline["title"].strip())
        write_text_exports(outline, args.ascii, args.markdown)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

