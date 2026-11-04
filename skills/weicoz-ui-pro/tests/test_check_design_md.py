"""Tests for scripts/check_design_md.py using only Python standard library."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_design_md.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_design_md  # noqa: E402

GOOD = """# 示例 设计规范

## 语义角色
变量在 `styles/tokens.css`。
- `--color-primary`：只用于主按钮和当前位置。（用户确认）
- 表格里的金额右对齐。（Agent 推断）

## 样板页面
- `app/index.html`：已完全按本规范完成。

```css
.demo { color: var(--not-checked-inside-fence); }
```
"""


class CheckDesignTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="oil-design-check-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "styles").mkdir()
        (self.root / "app").mkdir()
        (self.root / "styles/tokens.css").write_text(":root { --color-primary: #d9531e; }\n", encoding="utf-8")
        (self.root / "app/index.html").write_text("<!doctype html>", encoding="utf-8")
        ignored = self.root / "node_modules/pkg"
        ignored.mkdir(parents=True)
        (ignored / "x.css").write_text(":root { --from-dependency: 1px; }", encoding="utf-8")

    def write(self, text: str) -> Path:
        path = self.root / "DESIGN.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_clean_spec_passes(self) -> None:
        errors, notes = check_design_md.check(self.write(GOOD), self.root)
        self.assertEqual(errors, [])
        self.assertEqual(notes, [])

    def test_missing_path_and_undefined_variable_fail(self) -> None:
        text = GOOD + "- `--color-accent` 用于标签。（用户确认）\n- 见 `app/missing.html`。（用户确认）\n"
        errors, _ = check_design_md.check(self.write(text), self.root)
        self.assertTrue(any("--color-accent" in e for e in errors))
        self.assertTrue(any("app/missing.html" in e for e in errors))

    def test_dependency_definitions_do_not_count(self) -> None:
        errors, _ = check_design_md.check(self.write(GOOD + "- `--from-dependency`（用户确认）\n"), self.root)
        self.assertTrue(any("--from-dependency" in e for e in errors))

    def test_unmarked_rules_and_length_are_notes_only(self) -> None:
        text = GOOD + "\n## 不要做\n- 不用渐变。\n" + "\n" * 130
        errors, notes = check_design_md.check(self.write(text), self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("没标来源" in n for n in notes))
        self.assertTrue(any("100 行左右" in n for n in notes))

    def test_non_path_tokens_are_ignored(self) -> None:
        text = GOOD + "- 主色 `#d9531e`，类名 `.btn`，`npm run lint`，`<路径>`。（用户确认）\n"
        errors, _ = check_design_md.check(self.write(text), self.root)
        self.assertEqual(errors, [])

    def test_spec_under_docs_uses_git_root(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "docs/design.md").write_text(GOOD, encoding="utf-8")
        result = subprocess.run([sys.executable, SCRIPT, "docs/design.md"], cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_cli_exit_codes(self) -> None:
        self.write(GOOD)
        ok = subprocess.run([sys.executable, SCRIPT, "DESIGN.md"], cwd=self.root,
                            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.write(GOOD + "- `--nope`（用户确认）\n")
        bad = subprocess.run([sys.executable, SCRIPT, "DESIGN.md"], cwd=self.root,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("--nope", bad.stdout)
        missing = subprocess.run([sys.executable, SCRIPT, "nothing.md"], cwd=self.root,
                                 capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
