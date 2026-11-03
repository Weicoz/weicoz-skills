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
            page = aw.write_readback(root, {"seg01": mp3}, rows, ["seg01"])
            text = page.read_text(encoding="utf-8")
            self.assertTrue((root / "out/readback/seg01-1.m4a").stat().st_size > 0)
            self.assertIn('src="seg01-1.m4a"', text)
            self.assertIn("&lt;从&gt;", text)
            self.assertIn("稿子「（无）」→ 听成「<b>儿</b>」", text)
            self.assertIn("prefers-color-scheme:dark", text)

    def test_other_segments_kept(self):
        """只处理 seg02 且它没有差异时，seg01 的试听与页面保留；seg01 也没差异时删除页面。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mp3 = root / "a.mp3"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=2", str(mp3)], check=True)
            rows = [("seg01", 0, "甲", "甲儿", [{"script": "", "heard": "儿"}], 0.1, 0.9)]
            aw.write_readback(root, {"seg01": mp3}, rows, ["seg01"])
            page = aw.write_readback(root, {"seg02": mp3}, [], ["seg02"])
            self.assertIsNotNone(page)
            self.assertTrue((root / "out/readback/seg01-0.m4a").exists())
            self.assertIn("seg01 第 0 句", page.read_text(encoding="utf-8"))
            self.assertIsNone(aw.write_readback(root, {"seg01": mp3}, [], ["seg01"]))
            self.assertFalse((root / "out/readback/index.html").exists())
            self.assertFalse((root / "out/readback/seg01-0.m4a").exists())


if __name__ == "__main__":
    unittest.main()
