"""check-audio.py 的离线测试：假工程 + ffmpeg 造的分轨，走 --stems-dir 与 --skip-asr，不调 remotion、不连远端。"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
SCRIPT = SCRIPTS / "check-audio.py"
_spec = importlib.util.spec_from_file_location("check_audio", SCRIPT)
ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ca)

TIMING = """export const FPS = 30;
export const SHOTS = [
  {id: 'sa', seg: 'seg01', segStart: 0.00, segEnd: 5.00, frames: 150},
  {id: 'sb', seg: 'seg02', segStart: 0.00, segEnd: 5.00, frames: 150},
];
"""
ROOT_OK = "<Composition id=\"Main\" component={Main} defaultProps={{vo: true, sfx: true, bgm: true, captions: true}} />"
ROOT_BAD = "<Composition id=\"Main\" component={Main} defaultProps={{captions: true}} />"


def sine(path, amp, dur=10, expr=None):
    e = expr or f"{amp}*sin(2*PI*440*t)"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc={e}:s=16000:d={dur}", str(path)], check=True)


def make_project(root, root_tsx=ROOT_OK):
    (root / "src").mkdir(parents=True)
    (root / "vo/cues").mkdir(parents=True)
    (root / "src/timing.ts").write_text(TIMING, encoding="utf-8")
    (root / "src/Root.tsx").write_text(root_tsx, encoding="utf-8")
    (root / "vo/cues/seg01.json").write_text(json.dumps([{"start": 0.5, "end": 2.0, "text": "第一句测试稿子"},
                                                         {"start": 2.5, "end": 4.5, "text": "第二句测试稿子"}]), encoding="utf-8")
    (root / "vo/cues/seg02.json").write_text(json.dumps([{"start": 0.5, "end": 4.0, "text": "第三句测试稿子"}]), encoding="utf-8")


def make_stems(d, bed_amp, mix_expr=None):
    d.mkdir(parents=True)
    sine(d / "vo.wav", 0.3)
    sine(d / "bed.wav", bed_amp)
    sine(d / "mix.wav", 0.3, expr=mix_expr)


def run(root, out, stems, *extra, env=None):
    e = {**os.environ, **(env or {})}
    e.pop("ZERO_TTS_API_URL", None)
    r = subprocess.run([sys.executable, str(SCRIPT), str(root), "--out", str(out), "--stems-dir", str(stems), "--skip-asr", *extra],
                       capture_output=True, text=True, env=e)
    return r


class CheckAudio(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.root = self.tmp / "proj"

    def tearDown(self):
        self._td.cleanup()

    def test_loud_bed_red(self):
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.6)  # 背景比旁白响 6 dB
        r = run(self.root, self.tmp / "out", self.tmp / "stems")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rep = json.loads((self.tmp / "out/audio-report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertTrue(all(any(i["level"] == "red" for i in c["issues"]) for c in rep["cues"]))
        md = (self.tmp / "out/audio-report.md").read_text(encoding="utf-8")
        self.assertIn("FAIL", md)
        self.assertIn("未验证", md)
        self.assertTrue(any((self.tmp / "out/clips/named").glob("sa_seg01-0.mp3")))

    def test_close_bed_yellow(self):
        """背景与旁白一样响：声学上只判黄，退出码 0（判红要等识别确认）。"""
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.3)
        r = run(self.root, self.tmp / "out", self.tmp / "stems")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads((self.tmp / "out/audio-report.json").read_text(encoding="utf-8"))
        self.assertTrue(all(any(i["level"] == "yellow" for i in c["issues"]) for c in rep["cues"]))

    def test_quiet_bed_pass(self):
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.01)
        r = run(self.root, self.tmp / "out", self.tmp / "stems")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads((self.tmp / "out/audio-report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["verdict"], "PASS")
        self.assertEqual(rep["red"], 0)
        self.assertGreater(rep["cues"][0]["vo_minus_bed"], 20)

    def test_missing_switch_exit2(self):
        make_project(self.root, ROOT_BAD)
        make_stems(self.tmp / "stems", 0.01)
        r = run(self.root, self.tmp / "out", self.tmp / "stems")
        self.assertEqual(r.returncode, 2)
        self.assertIn("sfx", r.stdout)

    def test_silence_yellow(self):
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.01, mix_expr="0.3*sin(2*PI*440*t)*(1-between(t\\,4\\,7.5))")
        r = run(self.root, self.tmp / "out", self.tmp / "stems")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads((self.tmp / "out/audio-report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rep["silences"]), 1)
        self.assertAlmostEqual(rep["silences"][0]["start"], 4.0, delta=0.15)
        self.assertIn("mix 空白", (self.tmp / "out/audio-report.md").read_text(encoding="utf-8"))

    def fake_agy(self):
        """假 agy：从环境变量 FAKE_KEY 读映射，只在测试里用（真 agy 看不到稿子）。
        FAKE_MODE=pass：对照无人声；第一个正常片段转写错、其余转写对。fail：对照被当成人声。"""
        fake = self.tmp / "fake-agy"
        fake.write_text(f"""#!{sys.executable}
import json, glob, os
key = {{k["file"]: k for k in json.load(open(os.environ["FAKE_KEY"], encoding="utf-8"))}}
files = sorted(glob.glob("*.mp3"))
open(os.environ["FAKE_LOG"], "a", encoding="utf-8").write(os.getcwd() + "\\t" + ",".join(files) + "\\n")
assert not os.path.exists("listen.json") and not any(f.endswith(".txt") for f in os.listdir("."))
items, first = [], True
for f in files:
    k = key[f]
    if k["kind"] == "control":
        bad = os.environ["FAKE_MODE"] == "fail"
        items.append({{"file": f, "transcript": "你好" if bad else "", "has_speech": bad, "natural": 1, "emotion": "其他", "masking": "none", "notes": "噪声"}})
    else:
        t = "完全不同的内容啊" if first else k["text"]
        first = False
        items.append({{"file": f, "transcript": t, "has_speech": True, "natural": 4, "emotion": "平淡", "masking": "none", "notes": "假"}})
print(json.dumps({{"status": "SUCCESS", "response": "ok",
  "structured_output": {{"items": items, "overall": {{"voice_fit": "合适", "bgm_fit": "合适", "notes": "假脚本"}}}}}}))
""", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake

    def listen(self, mode):
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.01)
        out = self.tmp / "out"
        r = run(self.root, out, self.tmp / "stems", "--listen",
                env={"CHECK_AUDIO_AGY": str(self.fake_agy()), "FAKE_MODE": mode, "FAKE_KEY": str(out / "listen-key.json"),
                     "FAKE_LOG": str(self.tmp / "fake.log")})
        return r, out

    def test_listen_control_pass(self):
        r, out = self.listen("pass")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        md = (out / "audio-report.md").read_text(encoding="utf-8")
        self.assertIn("Gemini 试听（参考）", md)
        self.assertIn("黄 1 项", md)
        self.assertIn("Gemini 听到的与稿子不符", md)
        self.assertIn("完全不同的内容啊", md)
        self.assertIn("sa seg01#0", md)  # 报告里换回镜头与 seg#句
        cwd, names = (self.tmp / "fake.log").read_text(encoding="utf-8").splitlines()[0].split("\t")
        blind = names.split(",")
        self.assertFalse(Path(cwd).resolve().is_relative_to(out.resolve()))  # 盲听目录在证据目录外
        self.assertFalse(Path(cwd).exists())  # 结束后删除
        self.assertTrue(all(n.startswith("c") and n.endswith(".mp3") for n in blind))
        self.assertEqual(len(blind), 7)  # 3 句 + 3 接缝 + 1 对照
        self.assertTrue((out / "listen-key.json").exists())
        self.assertFalse((out / "clips/listen.json").exists())

    def test_listen_control_fail(self):
        r, out = self.listen("fail")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        md = (out / "audio-report.md").read_text(encoding="utf-8")
        self.assertIn("Gemini 未通过对照（把噪声当成人声）", md)
        self.assertIn("黄 0 项", md)
        self.assertNotIn("Gemini 听到的与稿子不符", md)
        self.assertIn("未验证", md)

    def test_listen_agy_missing(self):
        make_project(self.root)
        make_stems(self.tmp / "stems", 0.01)
        r = run(self.root, self.tmp / "out", self.tmp / "stems", "--listen", env={"CHECK_AUDIO_AGY": str(self.tmp / "nope")})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("未验证", (self.tmp / "out/audio-report.md").read_text(encoding="utf-8"))

    def test_helpers(self):
        n, rate, frags = ca.compare_text("第一句，测试稿子！", "第一句测试稿子")
        self.assertEqual((n, rate), (0, 0.0))
        n, rate, frags = ca.compare_text("今天讲送水", "")
        self.assertEqual(rate, 1.0)
        n, rate, frags = ca.compare_text("今天讲送水", "今天讲送谁")
        self.assertEqual(n, 1)
        self.assertEqual(frags, [{"script": "水", "heard": "谁"}])


if __name__ == "__main__":
    unittest.main()
