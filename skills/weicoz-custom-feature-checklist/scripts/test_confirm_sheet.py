#!/usr/bin/env python3
"""Tests for the 「方案确认项」 sheet in create_feature_checklist_xlsx.py."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from create_feature_checklist_xlsx import create_xlsx  # noqa: E402

ROW = {"类型": "用户端", "类型描述": "定制", "模块名称": "直推奖励", "功能描述": "直推奖励 10%（建议值，见方案确认项第1条）"}


def sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return re.findall(r'<sheet\b[^>]*name="([^"]+)"', archive.read("xl/workbook.xml").decode("utf-8"))


def all_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return "".join(archive.read(n).decode("utf-8") for n in archive.namelist() if n.startswith("xl/worksheets/"))


class ConfirmSheetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def build(self, name: str, items: list[dict], template: Path | None = None) -> Path:
        payload = {"title": "测试", "output": str(self.dir / name), "rows": [ROW], "confirm_items": items}
        if template:
            payload["template"] = str(template)
        return create_xlsx(payload)

    def test_items_numbered_in_order(self) -> None:
        path = self.build("a.xlsx", [{"问题": "直推比例", "选项": "A 10% / B 8%"}, {"问题": "结算周期"}])
        self.assertEqual(sheet_names(path), ["Sheet1", "方案确认项"])
        text = all_text(path)
        self.assertLess(text.index("第1条"), text.index("第2条"))
        self.assertIn("直推比例", text)

    def test_no_items_no_sheet(self) -> None:
        self.assertEqual(sheet_names(self.build("a.xlsx", [])), ["Sheet1"])

    def test_missing_question_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.build("a.xlsx", [{"选项": "A"}])

    def test_template_confirm_sheet_replaced(self) -> None:
        old = self.build("old.xlsx", [{"问题": "旧项目问题"}])
        new = self.build("new.xlsx", [{"问题": "新问题"}], template=old)
        self.assertEqual(sheet_names(new), ["Sheet1", "方案确认项"])
        self.assertNotIn("旧项目问题", all_text(new))

    def test_template_confirm_sheet_dropped_without_items(self) -> None:
        old = self.build("old.xlsx", [{"问题": "旧项目问题"}])
        new = self.build("new.xlsx", [], template=old)
        self.assertEqual(sheet_names(new), ["Sheet1"])
        with zipfile.ZipFile(new) as archive:
            self.assertNotIn("旧项目问题", "".join(archive.read(n).decode("utf-8", "ignore") for n in archive.namelist()))


if __name__ == "__main__":
    unittest.main()
