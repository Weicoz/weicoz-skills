#!/usr/bin/env python3
"""客户交付回归：多业务表、模板保持、表尾越界与名称泄漏。"""
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from create_feature_checklist_xlsx import create_xlsx, MAIN_NS, NS
from check_feature_checklist_xlsx import check_workbook, workbook_sheets

ROW = {"类型": "用户端", "类型描述": "定制", "模块名称": "身份查询", "功能描述": "查看当前身份。"}


def mutate(path, part, change):
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(files[part])
    change(root)
    files[part] = ET.tostring(root)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.template = create_xlsx({"output": str(self.root / "参考.xlsx"), "rows": [ROW]})
        mutate(self.template, "xl/worksheets/sheet1.xml",
               lambda r: r.find("main:cols/main:col", NS).set("width", "18.75"))
        self.payload = {"output": str(self.root / "功能清单.xlsx"), "template": str(self.template),
                        "sheets": [{"name": "服务商体系", "rows": [ROW, ROW]},
                                   {"name": "招商挑战", "rows": [{**ROW, "模块名称": "战队查询"}]}]}

    def build(self):
        return create_xlsx(self.payload)

    def part(self, path):
        with zipfile.ZipFile(path) as archive:
            return workbook_sheets(archive)[0][1]

    def test_two_business_sheets_keep_template(self):
        path = self.build()
        self.assertEqual(check_workbook(path, self.payload), [])
        with zipfile.ZipFile(path) as archive, zipfile.ZipFile(self.template) as template:
            self.assertEqual([n for n, _ in workbook_sheets(archive)], ["服务商体系", "招商挑战"])
            self.assertEqual(archive.read("xl/styles.xml"), template.read("xl/styles.xml"))
            for _, part in workbook_sheets(archive):
                root = ET.fromstring(archive.read(part))
                self.assertEqual(root.find("main:cols/main:col", NS).get("width"), "18.75")

    def test_single_payload_still_supported(self):
        payload = {"output": str(self.root / "单表.xlsx"), "title": "功能清单", "rows": [ROW], "template": str(self.template)}
        self.assertEqual(check_workbook(create_xlsx(payload), payload), [])

    def test_confirmation_is_separate_and_replaces_old_items(self):
        self.payload["confirm_items"] = [{"问题": "计算基数", "影响": "相关金额不能测算"}]
        old = self.build()
        self.payload.update(template=str(old), output=str(self.root / "新版.xlsx"), confirm_items=[{"问题": "新问题"}])
        path = self.build()
        self.assertEqual(check_workbook(path, self.payload), [])
        with zipfile.ZipFile(path) as archive:
            self.assertEqual([n for n, _ in workbook_sheets(archive)], ["服务商体系", "招商挑战", "方案确认项"])
            visible = b"".join(archive.read(p) for _, p in workbook_sheets(archive))
            self.assertNotIn("计算基数".encode(), visible)

    def test_old_business_sheets_are_not_copied(self):
        old = self.build()
        self.payload.update(template=str(old), output=str(self.root / "更换范围.xlsx"),
                            sheets=[{"name": "新业务", "rows": [ROW]}])
        path = self.build()
        with zipfile.ZipFile(path) as archive:
            self.assertEqual([n for n, _ in workbook_sheets(archive)], ["新业务"])

    def test_footer_rejected(self):
        path = self.build()
        def add_footer(root):
            row = ET.SubElement(root.find("main:sheetData", NS), f"{{{MAIN_NS}}}row", {"r": "5"})
            ET.SubElement(row, f"{{{MAIN_NS}}}c", {"r": "A5"})
        mutate(path, self.part(path), add_footer)
        self.assertTrue(any("表尾" in p for p in check_workbook(path, self.payload)))

    def test_fifth_column_rejected(self):
        path = self.build()
        mutate(path, self.part(path), lambda r: ET.SubElement(r.find("main:sheetData/main:row", NS), f"{{{MAIN_NS}}}c", {"r": "E1"}))
        self.assertTrue(check_workbook(path, self.payload))

    def test_header_or_body_edit_rejected(self):
        for cell in ["A2", "D3"]:
            with self.subTest(cell=cell):
                path = self.build()
                mutate(path, self.part(path), lambda r: setattr(r.find(f'.//main:c[@r="{cell}"]/main:is/main:t', NS), "text", "擅自改写"))
                self.assertTrue(check_workbook(path, self.payload))

    def test_width_and_style_changes_rejected(self):
        path = self.build()
        mutate(path, self.part(path), lambda r: r.find("main:cols/main:col", NS).set("width", "99"))
        self.assertTrue(any("列宽" in p for p in check_workbook(path, self.payload)))
        path = self.build()
        mutate(path, "xl/styles.xml", lambda r: r.find("main:fonts/main:font/main:sz", NS).set("val", "25"))
        self.assertTrue(any("样式表" in p for p in check_workbook(path, self.payload)))

    def test_namespace_or_whitespace_only_changes_are_allowed(self):
        path = self.build()
        mutate(path, "xl/styles.xml", lambda r: setattr(r, "text", "\n  "))
        self.assertEqual(check_workbook(path, self.payload), [])

    def test_internal_names_rejected_in_external_delivery(self):
        variants = [("filename", "output", str(self.root / "功能清单-客户版.xlsx")),
                    ("title", "title", "功能清单（客户版）"), ("sheet", "name", "服务商内部版")]
        for label, key, value in variants:
            with self.subTest(label=label):
                payload = copy.deepcopy(self.payload)
                (payload if key == "output" else payload["sheets"][0])[key] = value
                with self.assertRaisesRegex(ValueError, "内部标记"):
                    create_xlsx(payload)

    def test_internal_draft_allowed_when_explicit(self):
        self.payload.update(audience="internal", output=str(self.root / "功能清单-内部版.xlsx"))
        self.assertEqual(check_workbook(self.build(), self.payload), [])

    def test_final_visible_title_is_checked(self):
        path = self.build()
        mutate(path, self.part(path), lambda r: setattr(r.find('.//main:c[@r="A1"]/main:is/main:t', NS), "text", "客户版"))
        self.assertTrue(any("内部标记" in p for p in check_workbook(path, self.payload)))

    def test_invalid_names_and_empty_sheets_rejected(self):
        for sheets in [[], [{"name": "a/b", "rows": [ROW]}], [{"name": "a", "rows": [ROW]}, {"name": "A", "rows": [ROW]}], [{"name": "业务", "rows": []}]]:
            with self.subTest(sheets=sheets):
                self.payload["sheets"] = sheets
                with self.assertRaises(ValueError):
                    self.build()

    def test_template_cannot_be_overwritten(self):
        self.payload["output"] = str(self.template)
        original = self.template.read_bytes()
        with self.assertRaisesRegex(ValueError, "覆盖参考模板"):
            self.build()
        self.assertEqual(self.template.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
