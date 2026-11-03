"""align-words.py 回读试听页的离线测试。"""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("align_words", SCRIPTS / "align-words.py")
aw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aw)


class Readback(unittest.TestCase):
    def test_page(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mp3 = root / "seg01.mp3"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=2", str(mp3)], check=True)
            rows = [("seg01", 1, "用户<从>哪来", "用户从哪儿来", [{"script": "", "heard": "儿"}], 0.2, 1.0)]
            page = aw.write_readback(root, {"seg01": mp3}, rows)
            text = page.read_text(encoding="utf-8")
            self.assertTrue((root / "out/readback/seg01-1.m4a").stat().st_size > 0)
            self.assertIn('src="seg01-1.m4a"', text)
            self.assertIn("&lt;从&gt;", text)
            self.assertIn("稿子「（无）」→ 听成「<b>儿</b>」", text)
            self.assertIn("prefers-color-scheme:dark", text)


if __name__ == "__main__":
    unittest.main()
