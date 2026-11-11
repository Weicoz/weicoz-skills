#!/usr/bin/env python3
"""check_scope_diff.py: block deletion must not remove neighbouring rows."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_scope_diff.py")
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
RNS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    body = []
    for number, values in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{chr(65 + column)}{number}" t="inlineStr"><is><t>{value}</t></is></c>'
            for column, value in enumerate(values)
            if value
        )
        body.append(f'<row r="{number}">{cells}</row>')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook {NS} {RNS}><sheets><sheet name="功能清单" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"<worksheet {NS}><sheetData>{''.join(body)}</sheetData></worksheet>",
        )


HEADER = ["类型", "类型描述", "模块名称", "功能描述"]
TITLE = ["测试功能清单", "", "", ""]
SOURCE = [
    TITLE,
    HEADER,
    ["用户端", "抢购列表", "抢购商品", "抢购商品"],
    ["", "数据塑造", "数据塑造", "进度和额度"],
    ["", "", "选择渠道产品", "渠道商品列表"],
    ["", "", "申请塑造", "在其他平台交易"],
    ["", "用户加盟", "用户加盟", "缴纳加盟费"],
    ["", "订单列表", "订单列表", "查看订单"],
    ["店长端", "我的店铺", "我的店铺", "查看店铺"],
    ["", "", "我的收益", "查看收益"],
    ["", "", "店铺设置", "设置店铺"],
]


class ScopeDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.xlsx"
        self.target = self.root / "target.xlsx"
        write_xlsx(self.source, SOURCE)

    def invoke(self, rows: list[list[str]]) -> subprocess.CompletedProcess[str]:
        write_xlsx(self.target, rows)
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), str(self.target),
             "--remove-block", "数据塑造"],
            capture_output=True, text=True,
        )

    def test_exact_block_removal_passes(self) -> None:
        rows = SOURCE[:3] + SOURCE[6:]
        result = self.invoke(rows)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("共 3 行", result.stdout)

    def test_neighbouring_row_removal_fails(self) -> None:
        rows = SOURCE[:3] + SOURCE[7:]
        result = self.invoke(rows)
        self.assertEqual(result.returncode, 1)
        self.assertIn("用户加盟", result.stdout)
        self.assertIn("指定板块外", result.stdout)

    def test_partial_block_removal_fails(self) -> None:
        rows = SOURCE[:3] + SOURCE[4:]
        result = self.invoke(rows)
        self.assertEqual(result.returncode, 1)
        self.assertIn("保留", result.stdout)

    def test_description_edit_fails(self) -> None:
        rows = [row[:] for row in SOURCE[:3] + SOURCE[6:]]
        rows[-1][3] = "改写"
        result = self.invoke(rows)
        self.assertEqual(result.returncode, 1)

    def test_reorder_fails(self) -> None:
        rows = [row[:] for row in SOURCE[:3] + SOURCE[6:]]
        rows[-2], rows[-1] = rows[-1], rows[-2]
        result = self.invoke(rows)
        self.assertEqual(result.returncode, 1)
        self.assertIn("顺序", result.stdout)

    def test_json_reports_block_size(self) -> None:
        write_xlsx(self.target, SOURCE[:3] + SOURCE[6:])
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), str(self.target),
             "--remove-block", "数据塑造", "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('"blockRows": 3', result.stdout)


if __name__ == "__main__":
    unittest.main()
