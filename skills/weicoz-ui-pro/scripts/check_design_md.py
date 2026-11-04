#!/usr/bin/env python3
"""Check a project's DESIGN.md against the repository it describes.

Errors (exit 1): backticked paths that do not exist, backticked CSS custom
properties that no style file defines. Notes (exit 0): length well over the
target, bullet rules without a source mark. Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STYLE_SUFFIXES = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".html", ".vue", ".svelte",
                  ".astro", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {".git", "node_modules", ".oil-ui", "dist", "build", ".next", ".nuxt", "out", "coverage",
             "vendor", ".cache", "_work"}
SOURCE_MARKS = ("用户确认", "Agent 推断", "待确认", "User confirmed", "Agent inferred", "To confirm")
# Sections whose bullets are pointers, not rules, and need no source mark.
UNMARKED_SECTIONS = ("可用组件", "样板页面", "待迁移", "Components", "Reference pages", "To migrate")
LINE_LIMIT = 120

CODE = re.compile(r"`([^`\n]+)`")
VARIABLE = re.compile(r"^--[A-Za-z0-9_-]+$")
DEFINITION = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
PATH_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def looks_like_path(token: str) -> bool:
    if any(ch in token for ch in " <>*{}()$|,;:=") or token.startswith(("-", "#", "@", ".")):
        return False
    if token.startswith(("http://", "https://")):
        return False
    return "/" in token or bool(PATH_SUFFIX.search(token))


def style_files(root: Path):
    for path in root.rglob("*"):
        if path.suffix.lower() not in STYLE_SUFFIXES or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def defined_variables(root: Path) -> set[str]:
    names: set[str] = set()
    for path in style_files(root):
        try:
            names.update(DEFINITION.findall(path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return names


def check(design: Path, root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    lines = design.read_text(encoding="utf-8").splitlines()
    variables = None
    in_fence = False
    section = ""
    unmarked: list[int] = []
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        for token in CODE.findall(line):
            token = token.strip()
            if VARIABLE.match(token):
                if variables is None:
                    variables = defined_variables(root)
                if token not in variables:
                    errors.append(f"第 {number} 行：变量 {token} 在项目的样式文件里没有定义")
            elif looks_like_path(token):
                target = (design.parent / token) if token.startswith("..") else root / token
                if not target.exists():
                    errors.append(f"第 {number} 行：路径 {token} 不存在")
        stripped = line.lstrip()
        if (stripped.startswith(("- ", "* ")) and not any(mark in line for mark in SOURCE_MARKS)
                and not any(name in section for name in UNMARKED_SECTIONS)):
            unmarked.append(number)
    if len(lines) > LINE_LIMIT:
        notes.append(f"共 {len(lines)} 行，目标是 100 行左右")
    if unmarked:
        shown = "、".join(str(n) for n in unmarked[:12]) + ("……" if len(unmarked) > 12 else "")
        notes.append(f"{len(unmarked)} 条规则没标来源（用户确认 / Agent 推断）：第 {shown} 行")
    return errors, notes


def project_root(design: Path) -> Path:
    """The enclosing Git checkout, so a spec kept under docs/ still resolves project paths."""
    for folder in (design.parent, *design.parent.parents):
        if (folder / ".git").exists():
            return folder
    return design.parent


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="核对 DESIGN.md 里的路径、CSS 变量、篇幅和来源标记。")
    parser.add_argument("design", nargs="?", default="DESIGN.md", help="规范文件，默认 ./DESIGN.md")
    parser.add_argument("--root", help="项目根目录，默认是规范所在的 Git 仓库根，不在仓库里时是规范所在目录")
    args = parser.parse_args(argv)
    design = Path(args.design).resolve()
    if not design.is_file():
        print(f"找不到规范文件：{args.design}")
        return 2
    root = Path(args.root).resolve() if args.root else project_root(design)
    errors, notes = check(design, root)
    for message in errors:
        print(f"错误：{message}")
    for message in notes:
        print(f"提示：{message}")
    if not errors and not notes:
        print("通过：路径和变量都能找到，篇幅和来源标记正常")
    elif not errors:
        print("路径和变量都能找到")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
