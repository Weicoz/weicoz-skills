#!/usr/bin/env python3
"""check_project_tree.py: naming, date and duplicate-content gate."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_project_tree.py")


class ProjectTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def project(self, name: str, files: dict[str, bytes]) -> Path:
        root = self.root / name
        root.mkdir()
        for filename, data in files.items():
            (root / filename).write_bytes(data)
        return root

    def invoke(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root), *args],
            capture_output=True, text=True,
        )

    def test_valid_external_tree_and_exclusions(self) -> None:
        root = self.project("20261111-熊猫店长模式定制", {
            "熊猫店长模式定制-功能清单-20261111.xlsx": b"client",
            "熊猫店长模式定制-功能清单-内部版-20261111.xlsx": b"internal",
            "熊猫店长模式定制-功能清单-20261111.payload.json": b"{}",
            ".DS_Store": b"hidden",
            "生成脚本.py": b"print(1)",
        })
        (root / "子目录").mkdir()
        (root / "子目录" / "别名.xlsx").write_bytes(b"client")
        result = self.invoke(root, "--external", "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["project"], "熊猫店长模式定制")
        self.assertEqual(payload["files"], ["熊猫店长模式定制-功能清单-20261111.xlsx"])

    def test_legacy_directory_is_allowed(self) -> None:
        root = self.project("老项目-20260201", {
            "老项目-沟通记录-20260201.md": b"notes",
        })
        self.assertEqual(self.invoke(root, "--external", "--json").returncode, 0)

    def test_bad_directory_or_date_fails(self) -> None:
        for name in ["没有日期", "20261340-坏日期"]:
            with self.subTest(name=name):
                root = self.root / name
                root.mkdir(exist_ok=True)
                result = self.invoke(root, "--external", "--json")
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_wrong_prefix_or_missing_date_fails(self) -> None:
        root = self.project("20261111-熊猫店长模式定制", {
            "熊猫店长模式功能清单.xlsx": b"alias",
            "熊猫店长模式定制-功能清单.xlsx": b"missing-date",
        })
        result = self.invoke(root, "--external")
        self.assertEqual(result.returncode, 1)
        self.assertIn("前缀", result.stdout)
        self.assertIn("缺少项目日期", result.stdout)

    def test_same_content_with_different_names_fails(self) -> None:
        root = self.project("20261111-熊猫店长模式定制", {
            "熊猫店长模式定制-功能清单-20261111.xlsx": b"same",
            "熊猫店长模式定制-功能清单-副本-20261111.xlsx": b"same",
        })
        result = self.invoke(root, "--external")
        self.assertEqual(result.returncode, 1)
        self.assertIn("内容重复但文件名不同", result.stdout)

    def test_external_skips_internal_names(self) -> None:
        root = self.project("20261111-熊猫店长模式定制", {
            "熊猫店长模式定制-功能清单-20261111.xlsx": b"client",
            "错误前缀-内部版-20261111.xlsx": b"internal",
        })
        self.assertEqual(self.invoke(root, "--external").returncode, 0)
        self.assertEqual(self.invoke(root).returncode, 1)


if __name__ == "__main__":
    unittest.main()
