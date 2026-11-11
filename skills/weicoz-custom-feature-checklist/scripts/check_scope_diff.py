#!/usr/bin/env python3
"""删除功能板块时复核范围：只允许删除指定板块内的连续功能行。"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"main": MAIN_NS}
HEADER = ("类型", "类型描述", "模块名称", "功能描述")
COLUMN_NAMES = HEADER


@dataclass(frozen=True)
class FeatureRow:
    type: str
    subtype: str
    module: str
    description: str
    row: int
    subtype_start: bool = False

    @property
    def signature(self) -> tuple[str, str, str, str]:
        return self.type, self.subtype, self.module, self.description

    def value(self, column: str) -> str:
        return {
            "类型": self.type,
            "类型描述": self.subtype,
            "模块名称": self.module,
            "功能描述": self.description,
        }[column]


def workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    result = []
    for sheet in workbook.findall("main:sheets/main:sheet", NS):
        target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        result.append((sheet.attrib["name"], target))
    return result


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in item.findall(".//main:t", NS)) for item in root]


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.findall("main:is//main:t", NS))
    value = cell.findtext("main:v", default="", namespaces=NS)
    if kind == "s" and value.isdigit() and int(value) < len(shared):
        return shared[int(value)]
    return value


def column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        return 0
    value = 0
    for char in letters.group(0):
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def read_sheet(archive: zipfile.ZipFile, part: str, shared: list[str]) -> list[FeatureRow]:
    root = ET.fromstring(archive.read(part))
    grid: list[tuple[int, list[str]]] = []
    for row in root.findall("main:sheetData/main:row", NS):
        cells = ["", "", "", ""]
        number = int(row.attrib["r"])
        for cell in row.findall("main:c", NS):
            index = column_index(cell.attrib["r"])
            if index < len(cells):
                cells[index] = cell_value(cell, shared)
        grid.append((number, cells))

    header_index = next(
        (index for index, (_, cells) in enumerate(grid) if tuple(cells[:4]) == HEADER),
        None,
    )
    if header_index is None:
        raise ValueError(f"{part} 缺少四列表头：{' | '.join(HEADER)}")

    result: list[FeatureRow] = []
    current_type = ""
    current_subtype = ""
    for number, (raw_type, raw_subtype, module, description) in grid[header_index + 1:]:
        if raw_type:
            if raw_type != current_type:
                current_subtype = ""
            current_type = raw_type
        if raw_subtype:
            current_subtype = raw_subtype
        if not any((raw_type, raw_subtype, module, description)):
            continue
        if not (module or description):
            continue
        result.append(FeatureRow(
            current_type, current_subtype, module, description, number, bool(raw_subtype)
        ))
    return result


def read_table(path: Path, sheet: str | None) -> tuple[str, list[FeatureRow]]:
    with zipfile.ZipFile(path) as archive:
        sheets = workbook_sheets(archive)
        shared = shared_strings(archive)
        candidates = [(name, part) for name, part in sheets if sheet is None or name == sheet]
        if sheet is not None and not candidates:
            raise ValueError(f"找不到工作表：{sheet}")
        errors = []
        for name, part in candidates:
            try:
                return name, read_sheet(archive, part, shared)
            except ValueError as error:
                errors.append(str(error))
        raise ValueError(errors[0] if errors else "没有可读取的业务工作表")


def subtract(rows: list[FeatureRow], remove: list[FeatureRow]) -> list[FeatureRow]:
    remaining = Counter(row.signature for row in remove)
    result = []
    for row in rows:
        if remaining[row.signature]:
            remaining[row.signature] -= 1
        else:
            result.append(row)
    return result


def short(value: str, limit: int = 48) -> str:
    value = value.replace("\n", " ")
    return value if len(value) <= limit else f"{value[:limit]}…"


def describe(row: FeatureRow) -> str:
    return (
        f"原表第 {row.row} 行：{row.type} | {row.subtype} | "
        f"{row.module} | {short(row.description)}"
    )


def select_block(rows: list[FeatureRow], block: str, column: str) -> list[FeatureRow]:
    if column != "类型描述":
        return [row for row in rows if row.value(column) == block]
    selected: set[int] = set()
    for index, row in enumerate(rows):
        if row.subtype != block or not row.subtype_start:
            continue
        selected.add(index)
        for child_index in range(index + 1, len(rows)):
            if rows[child_index].subtype_start:
                break
            selected.add(child_index)
    return [row for index, row in enumerate(rows) if index in selected]


def compare(
    source: list[FeatureRow],
    target: list[FeatureRow],
    block: str,
    column: str,
) -> tuple[list[str], list[FeatureRow]]:
    block_rows = select_block(source, block, column)
    if not block_rows:
        return [f"原表在“{column}”列找不到板块：{block}"], block_rows

    desired = [row for row in source if row not in block_rows]
    missing = subtract(desired, target)
    extra = subtract(target, desired)
    problems = []
    if missing:
        problems.append(f"删除了指定板块外的 {len(missing)} 行：")
        problems.extend(f"  - {describe(row)}" for row in missing)
    if extra:
        problems.append(f"目标表多出或保留了 {len(extra)} 行：")
        problems.extend(
            f"  - 目标表第 {row.row} 行：{row.type} | {row.subtype} | {row.module} | {short(row.description)}"
            for row in extra
        )
    if not missing and not extra and [row.signature for row in desired] != [row.signature for row in target]:
        problems.append("功能行顺序被改动；删除板块不应重排行序")
    return problems, block_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="删除前的原始 XLSX")
    parser.add_argument("target", type=Path, help="删除后的目标 XLSX")
    parser.add_argument("--remove-block", required=True, help="只允许删除的板块名称")
    parser.add_argument("--block-column", default="类型描述", choices=COLUMN_NAMES,
                        help="板块名称所在列（默认：类型描述）")
    parser.add_argument("--sheet", help="工作表名称；默认第一个含四列表头的工作表")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args()

    try:
        sheet, source = read_table(args.source, args.sheet)
        _, target = read_table(args.target, args.sheet or sheet)
        problems, block_rows = compare(source, target, args.remove_block, args.block_column)
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"FAIL：Excel 无法复核：{error}")
        return 2

    if args.json:
        print(json.dumps({
            "status": "ok" if not problems else "error",
            "sheet": sheet,
            "block": args.remove_block,
            "column": args.block_column,
            "blockRows": len(block_rows),
            "problems": problems,
        }, ensure_ascii=False))
    elif problems:
        print("\n".join(problems))
    else:
        print(f"PASS：仅删除“{args.remove_block}”板块，共 {len(block_rows)} 行")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
