#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {"main": MAIN_NS, "rel": REL_NS, "pkg": PKG_REL_NS}

DEFAULT_ROWS = [
    {
        "类型": "用户端",
        "类型描述": "用户定制",
        "模块名称": "示例模块",
        "功能描述": "这里填写客户可读的功能描述。",
    }
]

DEFAULT_STYLES = {
    "title": ["1", "1", "1", "1"],
    "header": ["2", "2", "2", "2"],
    "body": ["3", "3", "3", "4"],
}

DEFAULT_COLS_XML = """
<cols xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <col min="1" max="1" width="12.0195" customWidth="1"/>
  <col min="2" max="2" width="17.0508" customWidth="1"/>
  <col min="3" max="3" width="23.0625" customWidth="1"/>
  <col min="4" max="4" width="58.3828" customWidth="1"/>
</cols>
""".strip()


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def normalize_rows(rows: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
    normalized = []
    for row in rows:
        normalized.append(
            (
                str(row.get("类型", "")).strip(),
                str(row.get("类型描述", "")).strip(),
                str(row.get("模块名称", "")).strip(),
                str(row.get("功能描述", "")).strip(),
            )
        )
    return normalized


def inline_cell(ref: str, style: str, value: str | None = None) -> str:
    if value is None:
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t></t></is></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def row_xml(row_num: int, cells: list[str], height: float) -> str:
    return (
        f'<row r="{row_num}" spans="1:4" ht="{height}" customHeight="1">'
        + "".join(cells)
        + "</row>"
    )


def row_height(text: str) -> float:
    length = len(text)
    if length <= 36:
        return 33
    if length <= 52:
        return 42
    if length <= 72:
        return 52.5
    return 63


def normalize_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def has_content(sheet_xml: bytes) -> bool:
    root = ET.fromstring(sheet_xml)
    for cell in root.findall(".//main:sheetData/main:row/main:c", NS):
        value_node = cell.find("main:v", NS)
        if value_node is not None and (value_node.text or "").strip():
            return True
        inline_text = cell.find("main:is/main:t", NS)
        if inline_text is not None and (inline_text.text or "").strip():
            return True
    return False


def resolve_template_sheet_path(zin: zipfile.ZipFile) -> str:
    workbook_root = ET.fromstring(zin.read("xl/workbook.xml"))
    rels_root = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: normalize_target(rel.attrib["Target"])
        for rel in rels_root.findall("pkg:Relationship", NS)
    }

    sheet_paths: list[str] = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if rel_id and rel_id in rel_map:
            sheet_paths.append(rel_map[rel_id])

    for path in sheet_paths:
        if has_content(zin.read(path)):
            return path
    return sheet_paths[0]


def first_style_for_col(rows: list[ET.Element], column: str, default: str) -> str:
    for row in rows:
        row_num = int(row.attrib.get("r", "0"))
        if row_num < 3:
            continue
        for cell in row.findall("main:c", NS):
            ref = cell.attrib.get("r", "")
            if ref.startswith(column):
                return cell.attrib.get("s", default)
    return default


def template_sheet_config(zin: zipfile.ZipFile, sheet_path: str) -> dict[str, Any]:
    root = ET.fromstring(zin.read(sheet_path))
    sheet_data = root.find("main:sheetData", NS)
    rows = sheet_data.findall("main:row", NS) if sheet_data is not None else []
    cell_styles = {cell.attrib.get("r", ""): cell.attrib.get("s", "0") for row in rows for cell in row.findall("main:c", NS)}

    title_styles = [cell_styles.get(f"{col}1", cell_styles.get("A1", "1")) for col in "ABCD"]
    header_styles = [cell_styles.get(f"{col}2", cell_styles.get("A2", "2")) for col in "ABCD"]
    body_styles = [
        first_style_for_col(rows, "A", header_styles[0]),
        first_style_for_col(rows, "B", header_styles[1]),
        first_style_for_col(rows, "C", header_styles[2]),
        first_style_for_col(rows, "D", header_styles[3]),
    ]

    preserved = {name: None for name in ("sheetPr", "sheetViews", "sheetFormatPr", "cols")}
    trailing_nodes: list[str] = []
    for child in list(root):
        name = local_name(child.tag)
        xml = ET.tostring(child, encoding="unicode")
        if name in preserved:
            preserved[name] = xml
        elif name not in {"dimension", "sheetData", "mergeCells"}:
            trailing_nodes.append(xml)

    return {
        "styles": {
            "title": title_styles,
            "header": header_styles,
            "body": body_styles,
        },
        "sheetPr": preserved["sheetPr"] or "<sheetPr/>",
        "sheetViews": preserved["sheetViews"] or '<sheetViews><sheetView showGridLines="1" workbookViewId="0"/></sheetViews>',
        "sheetFormatPr": preserved["sheetFormatPr"] or '<sheetFormatPr defaultColWidth="9" defaultRowHeight="14.1"/>',
        "cols": preserved["cols"] or DEFAULT_COLS_XML,
        "trailing": trailing_nodes or [
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>',
            '<pageSetup paperSize="9" orientation="portrait"/>',
            "<headerFooter/>",
        ],
    }


def merge_ranges(rows: list[tuple[str, str, str, str]]) -> list[str]:
    ranges = ["A1:D1"]
    if not rows:
        return ranges

    start = 3
    last_type = rows[0][0]
    for offset, row in enumerate(rows[1:], start=4):
        current_type = row[0]
        if current_type != last_type:
            if offset - 1 > start and last_type:
                ranges.append(f"A{start}:A{offset - 1}")
            start = offset
            last_type = current_type
    final_row = len(rows) + 2
    if final_row > start and last_type:
        ranges.append(f"A{start}:A{final_row}")

    start = 3
    last_key = (rows[0][0], rows[0][1])
    for offset, row in enumerate(rows[1:], start=4):
        current_key = (row[0], row[1])
        if current_key != last_key:
            if offset - 1 > start and last_key[1]:
                ranges.append(f"B{start}:B{offset - 1}")
            start = offset
            last_key = current_key
    if final_row > start and last_key[1]:
        ranges.append(f"B{start}:B{final_row}")
    return ranges


def build_sheet_xml(title: str, rows: list[tuple[str, str, str, str]], config: dict[str, Any]) -> bytes:
    styles = config["styles"]
    rows_xml: list[str] = []
    rows_xml.append(
        row_xml(
            1,
            [inline_cell(f"{col}1", style, title if col == "A" else None) for col, style in zip("ABCD", styles["title"])],
            24.55,
        )
    )
    header_values = ["类型", "类型描述", "模块名称", "功能描述"]
    rows_xml.append(
        row_xml(
            2,
            [inline_cell(f"{col}2", style, value) for col, style, value in zip("ABCD", styles["header"], header_values)],
            41.15,
        )
    )

    prev_type = None
    prev_desc = None
    for idx, (item_type, desc, module, detail) in enumerate(rows, start=3):
        show_type = item_type if item_type != prev_type else None
        show_desc = desc if (item_type, desc) != (prev_type, prev_desc) else None
        rows_xml.append(
            row_xml(
                idx,
                [
                    inline_cell(f"A{idx}", styles["body"][0], show_type),
                    inline_cell(f"B{idx}", styles["body"][1], show_desc),
                    inline_cell(f"C{idx}", styles["body"][2], module),
                    inline_cell(f"D{idx}", styles["body"][3], detail),
                ],
                row_height(detail),
            )
        )
        prev_type = item_type
        prev_desc = desc

    final_row = max(len(rows) + 2, 2)
    merges = merge_ranges(rows)
    merge_xml = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
    trailing_xml = "".join(config["trailing"])
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{MAIN_NS}">
  {config["sheetPr"]}
  <dimension ref="A1:D{final_row}"/>
  {config["sheetViews"]}
  {config["sheetFormatPr"]}
  {config["cols"]}
  <sheetData>{''.join(rows_xml)}</sheetData>
  <mergeCells count="{len(merges)}">{merge_xml}</mergeCells>
  {trailing_xml}
</worksheet>'''
    return xml.encode("utf-8")


CONFIRM_SHEET = "方案确认项"
CONFIRM_HEADERS = ["条目", "问题", "选项", "我方建议", "影响"]
CONFIRM_WIDTHS = [10, 30, 36, 24, 36]
CT_WORKSHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
REL_WORKSHEET = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"


def normalize_confirm_items(items: list[dict[str, Any]]) -> list[list[str]]:
    """客户版「方案确认项」：第N条从 1 连续编号，正文引用写“建议值，见方案确认项第N条”。"""
    normalized = []
    for number, item in enumerate(items, start=1):
        question = str(item.get("问题", "")).strip()
        if not question:
            raise ValueError(f"方案确认项第{number}条缺少问题")
        normalized.append([f"第{number}条"] + [str(item.get(key, "")).strip() for key in CONFIRM_HEADERS[1:]])
    return normalized


def build_confirm_sheet_xml(items: list[list[str]], styles: dict[str, list[str]]) -> bytes:
    cols = "ABCDE"
    header_style, body_style = styles["header"][0], styles["body"][3]
    rows_xml = [row_xml(1, [inline_cell(f"{c}1", header_style, v) for c, v in zip(cols, CONFIRM_HEADERS)], 30)]
    for idx, values in enumerate(items, start=2):
        height = max(row_height(value) for value in values)
        rows_xml.append(row_xml(idx, [inline_cell(f"{c}{idx}", body_style, v) for c, v in zip(cols, values)], height))
    cols_xml = "".join(
        f'<col min="{n}" max="{n}" width="{w}" customWidth="1"/>' for n, w in enumerate(CONFIRM_WIDTHS, start=1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{MAIN_NS}">
  <dimension ref="A1:E{len(items) + 1}"/>
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="14.1"/>
  <cols>{cols_xml}</cols>
  <sheetData>{''.join(rows_xml)}</sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>'''.encode("utf-8")


def drop_existing_confirm_sheet(files: dict[str, bytes]) -> None:
    """模板沿用旧项目的「方案确认项」时整张删掉，避免旧条目混进新交付物。"""
    workbook = files["xl/workbook.xml"].decode("utf-8")
    match = re.search(rf'<sheet\b[^>]*name="{CONFIRM_SHEET}"[^>]*?:id="(rId\d+)"[^>]*/>', workbook)
    if match is None:
        return
    rels = files["xl/_rels/workbook.xml.rels"].decode("utf-8")
    rel = re.search(rf'<Relationship\b[^>]*Id="{match.group(1)}"[^>]*/>', rels)
    if rel:
        target = re.search(r'Target="([^"]+)"', rel.group(0))
        if target:
            part = normalize_target(target.group(1))
            files.pop(part, None)
            types = files["[Content_Types].xml"].decode("utf-8")
            types = re.sub(rf'<Override\b[^>]*PartName="/{re.escape(part)}"[^>]*/>', "", types)
            files["[Content_Types].xml"] = types.encode("utf-8")
        files["xl/_rels/workbook.xml.rels"] = rels.replace(rel.group(0), "").encode("utf-8")
    files["xl/workbook.xml"] = workbook.replace(match.group(0), "").encode("utf-8")


def write_confirm_sheet(output: Path, items: list[list[str]], styles: dict[str, list[str]]) -> None:
    with zipfile.ZipFile(output, "r") as zin:
        files = {info.filename: zin.read(info.filename) for info in zin.infolist()}
    drop_existing_confirm_sheet(files)
    if not items:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in files.items():
                zout.writestr(name, data)
        return
    used = [int(m) for name in files for m in re.findall(r"^xl/worksheets/sheet(\d+)\.xml$", name)]
    number = max(used, default=0) + 1
    sheet_part = f"worksheets/sheet{number}.xml"
    files[f"xl/{sheet_part}"] = build_confirm_sheet_xml(items, styles)

    rels = files["xl/_rels/workbook.xml.rels"].decode("utf-8")
    rel_ids = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels)]
    rel_id = f"rId{max(rel_ids, default=0) + 1}"
    rels = rels.replace(
        "</Relationships>", f'<Relationship Id="{rel_id}" Type="{REL_WORKSHEET}" Target="{sheet_part}"/></Relationships>'
    )
    files["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")

    workbook = files["xl/workbook.xml"].decode("utf-8")
    sheet_ids = [int(m) for m in re.findall(r'sheetId="(\d+)"', workbook)]
    prefix = re.search(r'xmlns:(\w+)="' + re.escape(REL_NS) + '"', workbook)
    if prefix is None:
        workbook = workbook.replace("<workbook ", f'<workbook xmlns:r="{REL_NS}" ', 1)
        rel_prefix = "r"
    else:
        rel_prefix = prefix.group(1)
    workbook = workbook.replace(
        "</sheets>",
        f'<sheet name="{CONFIRM_SHEET}" sheetId="{max(sheet_ids, default=0) + 1}" {rel_prefix}:id="{rel_id}"/></sheets>',
    )
    files["xl/workbook.xml"] = workbook.encode("utf-8")

    types = files["[Content_Types].xml"].decode("utf-8")
    types = types.replace("</Types>", f'<Override PartName="/xl/{sheet_part}" ContentType="{CT_WORKSHEET}"/></Types>')
    files["[Content_Types].xml"] = types.encode("utf-8")

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)


def create_from_template(template: Path, output: Path, title: str, rows: list[tuple[str, str, str, str]]) -> Path:
    with zipfile.ZipFile(template, "r") as zin:
        sheet_path = resolve_template_sheet_path(zin)
        config = template_sheet_config(zin, sheet_path)
        sheet_xml = build_sheet_xml(title, rows, config)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == sheet_path:
                    data = sheet_xml
                zout.writestr(item, data)
    return output


def minimal_content_types_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{CONTENT_TYPE_NS}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''.encode("utf-8")


def minimal_root_rels_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''.encode("utf-8")


def minimal_workbook_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''.encode("utf-8")


def minimal_workbook_rels_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>'''.encode("utf-8")


def minimal_styles_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{MAIN_NS}">
  <fonts count="2">
    <font><sz val="11"/><name val="Microsoft YaHei"/></font>
    <font><b/><sz val="12"/><name val="Microsoft YaHei"/></font>
  </fonts>
  <fills count="5">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF8EAADB"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFB4C6E7"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE2F0D9"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FF000000"/></left><right style="thin"><color rgb="FF000000"/></right><top style="thin"><color rgb="FF000000"/></top><bottom style="thin"><color rgb="FF000000"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''.encode("utf-8")


def minimal_theme_xml() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F497D"/></a:dk2>
      <a:lt2><a:srgbClr val="EEECE1"/></a:lt2>
      <a:accent1><a:srgbClr val="4F81BD"/></a:accent1>
      <a:accent2><a:srgbClr val="C0504D"/></a:accent2>
      <a:accent3><a:srgbClr val="9BBB59"/></a:accent3>
      <a:accent4><a:srgbClr val="8064A2"/></a:accent4>
      <a:accent5><a:srgbClr val="4BACC6"/></a:accent5>
      <a:accent6><a:srgbClr val="F79646"/></a:accent6>
      <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
      <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>'''


def minimal_app_xml() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Excel</Application>
</Properties>'''


def minimal_core_xml() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
</cp:coreProperties>'''


def create_minimal_xlsx(output: Path, title: str, rows: list[tuple[str, str, str, str]]) -> Path:
    config = {
        "styles": DEFAULT_STYLES,
        "sheetPr": "<sheetPr/>",
        "sheetViews": '<sheetViews><sheetView showGridLines="1" tabSelected="1" zoomScale="80" zoomScaleNormal="80" workbookViewId="0"/></sheetViews>',
        "sheetFormatPr": '<sheetFormatPr defaultColWidth="9" defaultRowHeight="14.1"/>',
        "cols": DEFAULT_COLS_XML,
        "trailing": [
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>',
            '<pageSetup paperSize="9" orientation="portrait"/>',
            "<headerFooter/>",
        ],
    }
    sheet_xml = build_sheet_xml(title, rows, config)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("[Content_Types].xml", minimal_content_types_xml())
        zout.writestr("_rels/.rels", minimal_root_rels_xml())
        zout.writestr("docProps/app.xml", minimal_app_xml())
        zout.writestr("docProps/core.xml", minimal_core_xml())
        zout.writestr("xl/workbook.xml", minimal_workbook_xml())
        zout.writestr("xl/_rels/workbook.xml.rels", minimal_workbook_rels_xml())
        zout.writestr("xl/styles.xml", minimal_styles_xml())
        zout.writestr("xl/theme/theme1.xml", minimal_theme_xml())
        zout.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output


def create_xlsx(payload: dict[str, Any]) -> Path:
    title = str(payload.get("title") or "功能清单").strip()
    output = Path(payload["output"]).expanduser()
    rows = normalize_rows(payload.get("rows") or DEFAULT_ROWS)
    confirm_items = normalize_confirm_items(payload.get("confirm_items") or [])
    template_value = payload.get("template")

    output.parent.mkdir(parents=True, exist_ok=True)
    styles = DEFAULT_STYLES
    if template_value:
        template = Path(str(template_value)).expanduser()
        create_from_template(template, output, title, rows)
        with zipfile.ZipFile(template, "r") as zin:
            styles = template_sheet_config(zin, resolve_template_sheet_path(zin))["styles"]
    else:
        create_minimal_xlsx(output, title, rows)
    write_confirm_sheet(output, confirm_items, styles)
    return output


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: create_feature_checklist_xlsx.py input.json")
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(create_xlsx(payload))


if __name__ == "__main__":
    main()
