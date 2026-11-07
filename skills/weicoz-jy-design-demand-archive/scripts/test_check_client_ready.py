#!/usr/bin/env python3
"""Tests for check_client_ready.py: wording gate and 方案确认项 numbering."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_client_ready.py")


def run(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, paths)], capture_output=True, text=True)


def write_xlsx(path: Path, sheets: dict[str, list[str]]) -> None:
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as archive:
        entries, rels = [], []
        for index, (name, cells) in enumerate(sheets.items(), 1):
            entries.append(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>')
            rels.append(f'<Relationship Id="rId{index}" Target="worksheets/sheet{index}.xml"/>')
            rows = "".join(
                f'<row r="{n}"><c r="A{n}" t="inlineStr"><is><t>{text}</t></is></c></row>' for n, text in enumerate(cells, 1)
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", f"<worksheet {ns}><sheetData>{rows}</sheetData></worksheet>")
        archive.writestr("xl/workbook.xml", f"<workbook {ns} {rns}><sheets>{''.join(entries)}</sheets></workbook>")
        archive.writestr("xl/_rels/workbook.xml.rels", f"<Relationships>{''.join(rels)}</Relationships>")


def write_xmind(path: Path, root: dict) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.json", json.dumps([{"rootTopic": root}], ensure_ascii=False))


def topic(title: str, *kids: dict) -> dict:
    return {"title": title, "children": {"attached": list(kids)}} if kids else {"title": title}


class MarkdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def check(self, text: str, name: str = "doc.md") -> subprocess.CompletedProcess[str]:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return run(path)

    def test_blocker_in_body_fails(self) -> None:
        result = self.check("# 方案\n分佣比例待定\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("待定", result.stdout)

    def test_confirm_section_skips_wording_and_matches_refs(self) -> None:
        result = self.check(
            "# 方案\n分佣比例 10%（建议值，见方案确认项第1条）\n\n"
            "## 方案确认项\n- 第1条：分佣比例待客户确认\n  - 选项：A 10% / B 8%\n\n## 结算\n按月结算\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_confirm_item_without_invented_value(self) -> None:
        result = self.check(
            "# 功能清单\n展示奖励明细，计算口径见方案确认项第1条。\n\n"
            "## 方案确认项\n- 第1条：奖励基数需和客户确认\n"
            "  - 已知：用户授权按现有资料继续；资料没有金额依据。\n"
            "  - 影响：本稿不测算该项金额。\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_section_ends_at_next_heading(self) -> None:
        result = self.check(
            "# 方案\n见方案确认项第1条\n## 方案确认项\n- 第1条：比例\n## 结算\n结算周期待定\n"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("待定", result.stdout)

    def test_ref_without_item_fails(self) -> None:
        result = self.check("# 方案\n见方案确认项第2条\n## 方案确认项\n- 第1条：比例\n见方案确认项第1条\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("确认页没有该条", result.stdout)

    def test_item_without_ref_fails(self) -> None:
        result = self.check("# 方案\n见方案确认项第1条\n## 方案确认项\n- 第1条：比例\n- 第2条：周期\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("第2条未在正文引用", result.stdout)

    def test_duplicate_item_fails(self) -> None:
        result = self.check("# 方案\n见方案确认项第1条\n## 方案确认项\n- 第1条：比例\n- 第1条：周期\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("重复", result.stdout)

    def test_ascii_tree_section(self) -> None:
        tree = (
            "项目\n├── 奖励\n│   └── 比例 10%（建议值，见方案确认项第1条）\n"
            "├── 方案确认项\n│   └── 第1条：比例待客户确认\n└── 结算\n    └── 按月结算\n"
        )
        self.assertEqual(self.check(tree, "tree.txt").returncode, 0)
        leak = tree.replace("按月结算", "结算周期待定")
        self.assertEqual(self.check(leak, "tree.txt").returncode, 1)


class PackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def test_xlsx_confirm_sheet(self) -> None:
        path = self.dir / "list.xlsx"
        write_xlsx(path, {"功能清单": ["分佣 10%（建议值，见方案确认项第1条）"], "方案确认项": ["第1条：比例待定"]})
        self.assertEqual(run(path).returncode, 0, run(path).stdout)
        write_xlsx(path, {"功能清单": ["分佣待定"], "方案确认项": ["第1条：比例"]})
        result = run(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("未在正文引用", result.stdout)

    def test_xmind_confirm_branch(self) -> None:
        path = self.dir / "map.xmind"
        good = topic("项目", topic("奖励", topic("比例 10%（建议值，见方案确认项第1条）")), topic("方案确认项", topic("第1条：比例待定")))
        write_xmind(path, good)
        self.assertEqual(run(path).returncode, 0, run(path).stdout)
        bad = topic("项目", topic("奖励", topic("比例待定")), topic("方案确认项", topic("第1条：比例")))
        write_xmind(path, bad)
        self.assertEqual(run(path).returncode, 1)


if __name__ == "__main__":
    unittest.main()
