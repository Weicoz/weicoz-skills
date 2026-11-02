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
    transform_media_md,
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
            "---\n\n"
            "# oil-ui-pro\n\n"
            "## 开始前\n\n"
            '版本检查：!`sh "${CLAUDE_SKILL_DIR}/scripts/check_update.sh" 2>/dev/null || true`\n\n'
            "上面仍是一条命令时，按需运行本目录的 `scripts/check_update.sh`\n"
            "若宿主生图工具或 `oiloil-image.mjs` 积分可用，按..."
        )
        out = transform_skill_md(sample)
        self.assertIn("name: weicoz-ui-pro", out)
        self.assertIn("# weicoz-ui-pro", out)
        self.assertNotIn("check_update", out)
        self.assertNotIn("oiloil-image.mjs", out)
        self.assertIn("python3 scripts/sync_upstream.py", out)

    def test_transform_media_md(self):
        sample = (
            "宿主不能生图且本任务已明确授权使用 oiloil 积分时，先运行 `node <skill>/scripts/oiloil-image.mjs balance` 检查登录状态；"
            "未登录或登录失效时，明确告诉用户需要登录，给出 `npx github:oil-oil/oil-cli login` 和 [账户页](https://ui.oiloil.org/account/?tab=images)……"
            "？下载自动生成 `SOURCES.md`"
        )
        out = transform_media_md(sample)
        self.assertNotIn("oiloil-image.mjs", out)
        self.assertNotIn("oil-cli login", out)
        self.assertIn("100% 离线免登录", out)

    def test_transform_image_ideation_md(self):
        sample = (
            "2. **Oil 生图脚本**：若无宿主生图工具，静默调用 `oiloil-image.mjs` 的 `balance` 子命令检查积分状态……\n"
            "并发调用 `oiloil-image.mjs` 时最多同时运行"
        )
        out = transform_image_ideation_md(sample)
        self.assertNotIn("oiloil-image.mjs", out)
        self.assertIn("本地扩展生图", out)

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
