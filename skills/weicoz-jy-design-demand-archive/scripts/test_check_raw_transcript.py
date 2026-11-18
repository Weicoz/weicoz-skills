#!/usr/bin/env python3
"""回归：拼接进原文归档的源文件自带二级标题，不能被当成区段结束。"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import check_raw_transcript as ct

HEADER = "# 归档\n\n## 原文\n\n"


class RawSectionTest(unittest.TestCase):
    def _archive(self, tmp: Path, body: str) -> Path:
        path = tmp / "原文.md"
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def test_nested_level_two_heading_is_kept(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            raw = self._archive(tmp, "### 【1/2】文件A\n\n## 一、需求边界\n\n内容A1\n")
            ok, reason, _ = ct.check_file(raw, None, None)
            self.assertTrue(ok, reason)
            sections = "\n".join(ct.extract_sections(raw.read_text(encoding="utf-8")))
            self.assertIn("## 一、需求边界", sections)

    def test_source_lines_after_nested_heading_are_matched(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            raw = self._archive(
                tmp,
                "### 【1/2】A\n\n## 一、边界\n\n内容A1\n\n## 二、范围\n\n内容B\n",
            )
            source = "## 一、边界\n内容A1\n## 二、范围\n内容B\n"
            lines = ct.normalize_lines(source)
            ok, reason, _ = ct.check_file(raw, source, lines)
            self.assertTrue(ok, reason)

    def test_summary_heading_closes_section(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            raw = self._archive(tmp, "原文内容\n\n## 摘要\n\n摘要内容不应计入\n")
            sections = "\n".join(ct.extract_sections(raw.read_text(encoding="utf-8")))
            self.assertIn("原文内容", sections)
            self.assertNotIn("摘要内容不应计入", sections)

    def test_level_one_heading_closes_section(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            raw = self._archive(tmp, "原文内容\n\n# 附录\n\n附录内容\n")
            sections = "\n".join(ct.extract_sections(raw.read_text(encoding="utf-8")))
            self.assertIn("原文内容", sections)
            self.assertNotIn("附录内容", sections)


if __name__ == "__main__":
    unittest.main()
