#!/usr/bin/env python3
"""按生成 payload 复核最终 Excel：名称、功能行、模板样式与表尾。"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from create_feature_checklist_xlsx import (
    CONFIRM_SHEET, DEFAULT_COLS_XML, DEFAULT_STYLES, NS, REL_NS,
    build_confirm_sheet_xml, merge_ranges, normalize_confirm_items, normalize_target,
    resolve_template_sheet_path, sheet_specs, template_sheet_config,
)

INTERNAL_LABEL = re.compile(r"客户版|内部版|初稿|草稿")


def naming_problems(path: Path, specs: list[dict], audience: str) -> list[str]:
    if audience not in {"client", "internal"}:
        return ["audience 只能为 client 或 internal"]
    if audience == "internal":
        return []
    labels = [path.name] + [str(s.get(k, "")) for s in specs for k in ("name", "title")]
    return [f"对外交付名称含内部标记：{value}" for value in labels if INTERNAL_LABEL.search(value)]


def xml_signature(node: ET.Element | None):
    if node is None:
        return None
    return (node.tag, sorted(node.attrib.items()), (node.text or "").strip(),
            [xml_signature(child) for child in node])


def workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    paths = {rel.attrib["Id"]: normalize_target(rel.attrib["Target"]) for rel in rels}
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    return [(s.attrib["name"], paths[s.attrib[f"{{{REL_NS}}}id"]])
            for s in workbook.findall("main:sheets/main:sheet", NS)]


def cells(root: ET.Element, shared: list[str]) -> dict[str, tuple[str, str]]:
    result = {}
    for cell in root.findall("main:sheetData/main:row/main:c", NS):
        ref = cell.attrib["r"]
        if ref in result:
            raise ValueError(f"重复单元格：{ref}")
        if cell.find("main:f", NS) is not None:
            raise ValueError(f"功能清单单元格含公式：{ref}")
        value = cell.findtext("main:v", default="", namespaces=NS)
        if cell.get("t") == "s":
            value = shared[int(value)]
        elif cell.get("t") == "inlineStr":
            value = "".join(t.text or "" for t in cell.findall("main:is//main:t", NS))
        result[ref] = (value, cell.get("s", "0"))
    return result


def check_workbook(path: Path, payload: dict) -> list[str]:
    specs = sheet_specs(payload)
    audience = payload.get("audience", "client")
    problems = naming_problems(path, specs, audience)
    config = {"styles": DEFAULT_STYLES, "cols": DEFAULT_COLS_XML}
    expected_style = None
    if payload.get("template"):
        with zipfile.ZipFile(Path(payload["template"]).expanduser()) as template:
            config = template_sheet_config(template, resolve_template_sheet_path(template))
            expected_style = xml_signature(ET.fromstring(template.read("xl/styles.xml")))
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            return problems + ["Excel ZIP 校验失败"]
        if expected_style is not None and xml_signature(ET.fromstring(archive.read("xl/styles.xml"))) != expected_style:
            problems.append("模板样式表被改动")
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in item.findall(".//main:t", NS)))
        sheets = workbook_sheets(archive)
        names = [name for name, _ in sheets]
        if len(names) != len(set(name.casefold() for name in names)):
            problems.append("工作表名称重复")
        business = [(n, p) for n, p in sheets if n != CONFIRM_SHEET]
        if "sheets" in payload:
            if [n for n, _ in business] != [s["name"] for s in specs]:
                problems.append("业务工作表名称或顺序与 payload 不一致")
        else:
            business = [(n, p) for n, p in business if cells(ET.fromstring(archive.read(p)), shared)]
        if len(business) != len(specs):
            problems.append("业务工作表数量与 payload 不一致")
        for (name, part), spec in zip(business, specs):
            root = ET.fromstring(archive.read(part))
            actual = cells(root, shared)
            problems.extend(naming_problems(Path("交付.xlsx"),
                            [{"name": name, "title": actual.get("A1", ("",))[0]}], audience))
            expected = {}
            values = [(spec["title"], "", "", ""), ("类型", "类型描述", "模块名称", "功能描述")]
            previous = (None, None)
            for row in spec["rows"]:
                values.append((row[0] if row[0] != previous[0] else "",
                               row[1] if row[:2] != previous else "", row[2], row[3]))
                previous = row[:2]
            for number, row in enumerate(values, 1):
                kind = "title" if number == 1 else "header" if number == 2 else "body"
                for column, value, style in zip("ABCD", row, config["styles"][kind]):
                    expected[f"{column}{number}"] = (value, style)
            if actual != expected:
                differences = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
                problems.append(f"{name}：单元格内容、样式或四列范围不符（含表尾追加）：{', '.join(differences[:8])}")
            row_numbers = [r.get("r") for r in root.findall("main:sheetData/main:row", NS)]
            if row_numbers != [str(i) for i in range(1, len(values) + 1)]:
                problems.append(f"{name}：功能表结束位置或行序不符")
            if root.find("main:dimension", NS).get("ref") != f"A1:D{len(values)}":
                problems.append(f"{name}：主表范围不符")
            if xml_signature(root.find("main:cols", NS)) != xml_signature(ET.fromstring(config["cols"])):
                problems.append(f"{name}：模板列宽被改动")
            merges = [m.get("ref") for m in root.findall("main:mergeCells/main:mergeCell", NS)]
            if merges != merge_ranges(spec["rows"]):
                problems.append(f"{name}：标题或 A/B 列合并不符")
        items = normalize_confirm_items(payload.get("confirm_items") or [])
        confirmation = [part for name, part in sheets if name == CONFIRM_SHEET]
        if bool(items) != bool(confirmation):
            problems.append("方案确认项工作表有遗漏或残留")
        if items and confirmation:
            expected = ET.fromstring(build_confirm_sheet_xml(items, config["styles"]))
            if cells(ET.fromstring(archive.read(confirmation[0])), shared) != cells(expected, []):
                problems.append("方案确认项内容与 payload 不一致")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--file", type=Path, help="复核二次处理后的最终文件；默认 payload.output")
    args = parser.parse_args()
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        problems = check_workbook(args.file or Path(payload["output"]).expanduser(), payload)
    except (OSError, ValueError, KeyError, IndexError, AttributeError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"FAIL：Excel 无法复核：{error}")
        return 1
    print("\n".join(problems) if problems else "PASS：功能行、模板、表尾和对外名称")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
