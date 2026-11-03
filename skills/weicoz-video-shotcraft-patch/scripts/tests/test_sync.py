"""check-sync.py 的离线测试（临时工程）。"""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_sync", SCRIPTS / "check-sync.py")
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

TIMING = 'export const SHOTS = [{id: "s1", seg: "seg01", segStart: 0, frames: 300}];\n'
BEATS = """const BEATS = {
  a: 60,   // cue0 开头
  b: 100,  // cue1@推成 句内
  c: [60, 100], // cue0/1 两句
};
"""


def chars(text, t0):
    return [{"c": c, "start": round(t0 + i * 0.1, 3), "end": round(t0 + i * 0.1 + 0.1, 3)} for i, c in enumerate(text)]


class Sync(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "src/shots").mkdir(parents=True)
        (self.root / "vo/cues").mkdir(parents=True)
        (self.root / "src/timing.ts").write_text(TIMING, encoding="utf-8")
        (self.root / "src/shots/S1.tsx").write_text(BEATS, encoding="utf-8")
        cues = [{"text": "你好世界", "start": 2.0, "end": 2.4}, {"text": "推成一单", "start": 3.3, "end": 3.7}]
        (self.root / "vo/cues/seg01.json").write_text(json.dumps(cues, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def words(self):
        d = self.root / "vo/cues-words"
        d.mkdir()
        rows = [{"cue": 0, "text": "你好世界", "src": "x", "chars": chars("你好世界", 2.0)},
                {"cue": 1, "text": "推成一单", "src": "x", "chars": chars("推成一单", 3.3)}]
        (d / "seg01.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def run_sync(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cs.main([str(self.root)])
        return code, out.getvalue()

    def test_no_words_no_hint(self):
        code, out = self.run_sync()
        self.assertEqual(code, 0, out)
        self.assertIn("待迁移 0", out)
        self.assertNotIn("迁移)", out)

    def test_migrate_hint(self):
        self.words()
        code, out = self.run_sync()
        self.assertEqual(code, 0, out)
        self.assertIn("待迁移 2", out)  # a 与 c；b 已是锚点
        self.assertEqual(out.count("s1.a:"), 1)
        self.assertIn("改成字级锚点 cueN@词", out)
        self.assertIn("红 0", out)
        self.assertIn("句窗口（±15 帧）通过 3", out)  # 句级节拍 a、c 的两个数字仍检查


if __name__ == "__main__":
    unittest.main()
