import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('check_links', Path(__file__).with_name('check_links.py'))
check_links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_links)


class EntryLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / '.agents').mkdir()
        self.source = self.home / '.agents/AGENTS.md'
        self.source.write_text('规则一\n规则二\n', encoding='utf-8')
        for name in ('.codex', '.dsh'):
            (self.home / name).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_hard_and_soft_links_pass(self):
        os.link(self.source, self.home / '.codex/AGENTS.md')
        (self.home / '.dsh/AGENTS.md').symlink_to(self.source)
        drift, ok = check_links.check(self.home, '.agents/AGENTS.md', ['.codex/AGENTS.md', '.dsh/AGENTS.md'])
        self.assertEqual(drift, [])
        self.assertEqual(ok, ['.codex/AGENTS.md', '.dsh/AGENTS.md'])

    def test_replaced_source_is_reported_as_drift(self):
        os.link(self.source, self.home / '.codex/AGENTS.md')
        replacement = self.home / '.agents/AGENTS.md.tmp'
        replacement.write_text('规则一\n规则二\n规则三\n', encoding='utf-8')
        replacement.replace(self.source)  # 编辑器整文件替换：维护源换了 inode
        drift, _ = check_links.check(self.home, '.agents/AGENTS.md', ['.codex/AGENTS.md'])
        self.assertEqual(len(drift), 1)
        self.assertIn('内容不同', drift[0])
        self.assertIn('多 1 行', drift[0])

    def test_missing_entry_is_skipped(self):
        drift, ok = check_links.check(self.home, '.agents/AGENTS.md', ['.grok/AGENTS.md'])
        self.assertEqual((drift, ok), ([], []))


if __name__ == '__main__':
    unittest.main()
