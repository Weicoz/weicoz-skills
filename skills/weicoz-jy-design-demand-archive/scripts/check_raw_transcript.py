#!/usr/bin/env python3
"""Check that meeting raw-transcript archives were not replaced by summaries."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RAW_WORDS = ("原文", "逐字", "转写", "全文")
SUMMARY_WORDS = ("摘要", "总结")
SUBSTITUTE_MARKERS = ["详见会话", "原话语义", "以下省略", "此处省略", "（略）", "(略)", "节选", "摘录"]
ELLIPSES = ["...", "……"]


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def normalize_lines(text: str) -> list[str]:
    lines = (normalize_line(line) for line in text.splitlines())
    return [line for line in lines if line]


def extract_sections(text: str) -> list[str]:
    """Return lines of every heading section whose title contains 原文/逐字/转写/全文.

    A file without any level 2+ heading is a bare transcript: every non-heading line counts.
    """
    lines = text.splitlines()
    sections: list[list[str]] = []
    current: list[str] | None = None
    current_level = 0
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2)
            if current is not None and level <= current_level:
                sections.append(current)
                current = None
            if (
                current is None
                and 2 <= level <= 4
                and any(word in title for word in RAW_WORDS)
                and not any(word in title for word in SUMMARY_WORDS)
            ):
                current = []
                current_level = level
                continue
        if current is not None:
            current.append(line)
    if current is not None:
        sections.append(current)
    if not sections and not any(
        (m := HEADING_RE.match(line)) and len(m.group(1)) >= 2 for line in lines
    ):
        return [line for line in lines if not HEADING_RE.match(line)]
    return [line for section in sections for line in section]


def match_source(source_lines: list[str], section_lines: list[str]) -> list[str]:
    """Subsequence match; a section line matches when it contains the source line."""
    missing: list[str] = []
    pos = 0
    for src in source_lines:
        found = None
        for index in range(pos, len(section_lines)):
            if src in section_lines[index]:
                found = index
                break
        if found is None:
            missing.append(src)
        else:
            pos = found + 1
    return missing


def check_file(raw: Path, source_text: str | None, source_lines: list[str] | None) -> tuple[bool, str, list[str]]:
    warns: list[str] = []
    if not raw.is_file():
        return False, "文件不存在", warns
    text = raw.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return False, "文件为空", warns
    section_lines = normalize_lines("\n".join(extract_sections(text)))
    if not section_lines:
        return False, "无原文区段或区段为空", warns
    section_text = "\n".join(section_lines)

    reasons: list[str] = []
    for marker in SUBSTITUTE_MARKERS:
        if marker in section_text and not (source_text is not None and marker in source_text):
            reasons.append(f"含替代标记「{marker}」")
    for ell in ELLIPSES:
        if ell in section_text:
            if source_text is None:
                warns.append(f"WARN {raw} 含省略号「{ell}」（口语转写常见，请人工确认）")
            elif ell not in source_text:
                reasons.append(f"含省略号「{ell}」但源文件没有")

    info = ""
    if source_lines is not None:
        missing = match_source(source_lines, section_lines)
        src_chars = sum(len(line) for line in source_lines)
        sec_chars = sum(len(line) for line in section_lines)
        info = f"（规范化字符数 源={src_chars} 区段={sec_chars}）"
        if missing:
            shown = "；".join(m[:60] for m in missing[:5])
            reasons.append(f"缺失源行 {len(missing)} 条，前 {min(5, len(missing))} 条：{shown}")
    if reasons:
        return False, "; ".join(reasons) + info, warns
    return True, f"区段 {len(section_lines)} 行{info}", warns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", nargs="+", type=Path, help="raw transcript archive file(s)")
    parser.add_argument("--source", type=Path, help="source transcript to compare line by line")
    args = parser.parse_args()

    source_text: str | None = None
    source_lines: list[str] | None = None
    if args.source:
        if not args.source.is_file():
            print(f"missing source: {args.source}", file=sys.stderr)
            return 1
        source_text = args.source.read_text(encoding="utf-8", errors="replace")
        source_lines = normalize_lines(source_text)

    failed = False
    for raw in args.raw:
        ok, reason, warns = check_file(raw, source_text, source_lines)
        print(f"{'PASS' if ok else 'FAIL'} {raw} {reason}")
        for warn in warns:
            print(warn)
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
