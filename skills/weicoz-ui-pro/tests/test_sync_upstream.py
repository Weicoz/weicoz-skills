#!/usr/bin/env python3
"""Unit tests for weicoz-ui-pro sync_upstream.py tool."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.sync_upstream import (
    EXCLUDED_REL_PATHS,
    scan_upstream,
    sync,
    transform_content,
    transform_image_ideation_md,
    read_version,
    transform_media_md,
    transform_readme_md,
    transform_skill_md,
)


class TestSyncUpstream(unittest.TestCase):
    def test_excluded_files_contains_prohibited(self):
        self.assertIn(Path("scripts/check_update.py"), EXCLUDED_REL_PATHS)
        self.assertIn(Path("scripts/check_update.sh"), EXCLUDED_REL_PATHS)
        self.assertIn(Path("scripts/oiloil-image.mjs"), EXCLUDED_REL_PATHS)
        self.assertIn(Path("tests/test_check_update.py"), EXCLUDED_REL_PATHS)
        self.assertIn(Path("tests/test_oiloil_image.py"), EXCLUDED_REL_PATHS)

    def test_transform_skill_md(self):
        sample = (
            "---\n"
            "name: oil-ui-pro\n"
            "allowed-tools:\n"
            "  - Bash(sh *check_update.sh*)\n"
            "  - Bash(python3 *check_update.py*)\n"
            "  - Bash(python3 *check_design_md.py*)\n"
            "metadata:\n"
            '  version: "0.31.0"\n'
            "---\n\n"
            "# oil-ui-pro\n\n"
            "## 开始前\n\n"
            '版本检查：!`sh "${CLAUDE_SKILL_DIR}/scripts/check_update.sh" 2>/dev/null || true`\n\n'
            "上面仍是一条命令时，按需运行 `scripts/check_update.sh`。\n\n"
            "## 选择范围\n\n"
            "若宿主生图工具或 `oiloil-image.mjs` 积分可用，按...\n"
        )
        out = transform_skill_md(sample)
        self.assertIn("name: weicoz-ui-pro\nversion: 0.31.0\n", out)
        self.assertIn("# weicoz-ui-pro", out)
        self.assertNotIn("check_update", out)
        self.assertNotIn("oiloil-image.mjs", out)
        # allowed-tools 保留其余条目，且与 metadata 之间仍有换行
        self.assertIn("  - Bash(python3 *check_design_md.py*)\nmetadata:", out)
        self.assertIn("Bash(python3 *upstream_refresh.py*)", out)
        # 「开始前」由预处理行驱动，且后续章节保留
        self.assertIn(
            '!`python3 "${CLAUDE_SKILL_DIR}/scripts/upstream_refresh.py" 2>/dev/null || true`', out
        )
        self.assertIn("预处理未执行", out)
        self.assertIn("## 选择范围", out)
        self.assertIn("若宿主生图工具可用，按...", out)

    def test_read_version(self):
        self.assertEqual(read_version('metadata:\n  version: "0.31.0"\n'), "0.31.0")
        self.assertEqual(read_version("version: 1.2.3\n"), "1.2.3")
        self.assertIsNone(read_version("name: x\n"))

    def test_transform_media_md_keeps_rest(self):
        sample = (
            "- **没有就做出来。** 来源顺序：宿主能生图就用宿主的。宿主不能生图且本任务已明确授权使用 oiloil 积分时，"
            "先运行 `node <skill>/scripts/oiloil-image.mjs balance`；给出 `npx github:oil-oil/oil-cli login` 和 "
            "[账户页](https://ui.oiloil.org/account/?tab=images)。已登录不等于授权消费。按所用工具自己的输入和编辑规则来。"
            "用 `curate-media.mjs` 检索。"
        )
        out = transform_media_md(sample)
        self.assertNotIn("oiloil", out)
        self.assertNotIn("oil-cli", out)
        self.assertIn("按所用工具自己的输入和编辑规则来。用 `curate-media.mjs` 检索。", out)
        self.assertIn("宿主能生图就用宿主的。宿主不能生图时", out)

    def test_transform_image_ideation_md(self):
        sample = (
            "2. **Oil 生图脚本**：若无宿主生图工具，静默调用 `oiloil-image.mjs` 的 `balance` 子命令检查积分状态……\n"
            "3. 回退（未登录、积分不足或离线环境），继续\n"
            "要走 Oil 积分时，在第 1、3 项里写明会消耗积分，用户选了就算本任务授权：\n"
            "只能走 Oil 积分时，本任务已授权使用积分才生成，没有授权就按常规代码流程推进，按 [素材](media.md) 只提示一次；用户只要设计稿。"
            "并发调用 `oiloil-image.mjs` 时最多同时运行"
        )
        out = transform_image_ideation_md(sample)
        self.assertNotIn("oiloil-image.mjs", out)
        self.assertNotIn("积分", out)
        self.assertNotIn("Oil 积分", out)
        self.assertIn("用户只要设计稿", out)

    def test_transform_readme_keeps_upstream_text(self):
        sample = (
            "中文 · [English](README.en.md)\n\n"
            "# oil-ui-pro\n\n"
            "给 AI Agent 用的界面设计方法。\n\n"
            "想看更多设计效果，可以去 [ui.oiloil.org](https://ui.oiloil.org)。\n\n"
            "## 安装\n\n运行 npx github:oil-oil/oil-cli install oil-ui-pro，用 oiloil 账号登录。\n\n"
            "## 使用\n\n“用 oil-ui-pro 给这个产品探索方向。”\n\n"
            "## 版本检查\n\n每次使用时检查一次，联网 ui.oiloil.org。\n\n"
            "## 搭配使用\n\n- oil-motion\n"
        )
        out = transform_readme_md(sample)
        self.assertIn("中文 · [English](README.en.md)", out)
        self.assertIn("# weicoz-ui-pro\n\n> weicoz 自研免登录版", out)
        self.assertIn("给 AI Agent 用的界面设计方法。", out)
        self.assertIn("“用 weicoz-ui-pro 给这个产品探索方向。”", out)
        self.assertIn("## 搭配使用", out)
        for gone in ("## 安装", "## 版本检查", "oil-cli", "ui.oiloil.org", "想看更多设计效果"):
            self.assertNotIn(gone, out)

    def test_transform_readme_en(self):
        sample = (
            "[中文](README.md) · English\n\n# oil-ui-pro\n\nAn interface design method.\n\n"
            "See more at [ui.oiloil.org](https://ui.oiloil.org).\n\n"
            "## Installation\n\nSign in.\n\n## Usage\n\nTell your agent.\n\n"
            "## Version checks\n\nChecks ui.oiloil.org.\n"
        )
        out = transform_readme_md(sample, is_en=True)
        self.assertIn("> weicoz login-free edition", out)
        self.assertIn("## Usage\n\nTell your agent.", out)
        for gone in ("## Installation", "## Version checks", "ui.oiloil.org"):
            self.assertNotIn(gone, out)

    def test_sync_deletes_removed_upstream_files_but_keeps_own(self):
        with tempfile.TemporaryDirectory() as up, tempfile.TemporaryDirectory() as lo:
            up, lo = Path(up), Path(lo)
            (up / "SKILL.md").write_text("name: oil-ui-pro\n")
            (lo / "SKILL.md").write_text("name: weicoz-ui-pro\n")
            (lo / "references").mkdir()
            (lo / "references" / "gone.md").write_text("old")
            (lo / "scripts").mkdir()
            (lo / "scripts" / "upstream_refresh.py").write_text("own")
            (lo / "LICENSE").write_text("mit")
            # 只检查模式：不删除，但返回 1
            self.assertEqual(sync(up, apply=False, skill_dir=lo), 1)
            self.assertTrue((lo / "references" / "gone.md").exists())
            self.assertEqual(sync(up, apply=True, skill_dir=lo), 0)
            self.assertFalse((lo / "references").exists())
            self.assertTrue((lo / "scripts" / "upstream_refresh.py").exists())
            self.assertTrue((lo / "LICENSE").exists())

    def test_sync_refuses_to_write_when_residue(self):
        with tempfile.TemporaryDirectory() as up, tempfile.TemporaryDirectory() as lo:
            up, lo = Path(up), Path(lo)
            (up / "SKILL.md").write_text("name: oil-ui-pro\n")
            (up / "references").mkdir()
            (up / "references" / "x.md").write_text("see scripts/oiloil-image.mjs")
            self.assertEqual(sync(up, apply=True, skill_dir=lo), 3)
            self.assertFalse((lo / "SKILL.md").exists())

    def test_scan_upstream_skips_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "scripts").mkdir()
            (tmp_path / "scripts" / "check_update.py").write_text("dummy")
            (tmp_path / "scripts" / "shoot.mjs").write_text("console.log('shoot');")
            (tmp_path / "SKILL.md").write_text("name: oil-ui-pro")

            scanned = scan_upstream(tmp_path)
            self.assertIn(Path("scripts/shoot.mjs"), scanned)
            self.assertIn(Path("SKILL.md"), scanned)
            self.assertNotIn(Path("scripts/check_update.py"), scanned)


if __name__ == "__main__":
    unittest.main()
