#!/usr/bin/env python3
"""检查项目目录、交付文件名和重复内容，避免错放、别名和重复外发。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

NEW_DIR = re.compile(r"^(\d{8})-(.+)$")
OLD_DIR = re.compile(r"^(.+)-(\d{8})$")
INTERNAL_MARKER = re.compile(r"内部版|初稿|草稿")
DELIVERY_EXTENSIONS = {
    ".md", ".txt", ".csv", ".xlsx", ".xmind", ".docx", ".pdf", ".pptx"
}


def project_identity(path: Path) -> tuple[str, str]:
    match = NEW_DIR.fullmatch(path.name)
    if match:
        date, name = match.groups()
    else:
        match = OLD_DIR.fullmatch(path.name)
        if not match:
            raise ValueError(f"项目目录名不符合 YYYYMMDD-项目名：{path.name}")
        name, date = match.groups()
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"项目目录日期无效：{date}") from error
    return name, date


def delivery_files(root: Path, external: bool) -> list[Path]:
    files = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name.startswith((".", "~$")):
            continue
        if path.suffix.lower() not in DELIVERY_EXTENSIONS:
            continue
        if external and INTERNAL_MARKER.search(path.stem):
            continue
        files.append(path)
    return files


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def check_project(root: Path, external: bool) -> dict:
    project, date = project_identity(root)
    files = delivery_files(root, external)
    problems = []
    if not files:
        problems.append("未找到可检查的交付文件")
    for path in files:
        if not path.name.startswith(f"{project}-"):
            problems.append(f"{path.name}：文件名前缀不是“{project}-”")
        if date not in path.name:
            problems.append(f"{path.name}：文件名缺少项目日期 {date}")

    by_digest: dict[str, list[str]] = {}
    for path in files:
        by_digest.setdefault(digest(path), []).append(path.name)
    for names in by_digest.values():
        if len(names) > 1:
            problems.append(f"内容重复但文件名不同：{', '.join(names)}")
    return {
        "status": "ok" if not problems else "error",
        "project": project,
        "date": date,
        "files": [path.name for path in files],
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--external", action="store_true", help="跳过内部版、初稿和草稿")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args()

    try:
        if not args.project_dir.is_dir():
            raise ValueError(f"项目目录不存在：{args.project_dir}")
        result = check_project(args.project_dir, args.external)
    except (OSError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "problems": [str(error)]}, ensure_ascii=False))
        else:
            print(f"FAIL：{error}")
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["problems"]:
        print("\n".join(result["problems"]))
    else:
        print(f"PASS：{len(result['files'])} 个交付文件")
    return int(bool(result["problems"]))


if __name__ == "__main__":
    raise SystemExit(main())
