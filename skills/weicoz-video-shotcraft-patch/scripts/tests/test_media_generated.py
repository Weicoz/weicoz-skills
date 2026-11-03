"""AI 生成素材：本地 sheet / import / fetch 复原 / credits / check-media（离线，ffmpeg 现场造文件）。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_media import ms, cm, run, make_image, make_video

PICK = "agent:联系表第 2 张，一只放在木桌上的透明玻璃水瓶"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 ffmpeg")
class Generated(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        base = Path(self._td.name)
        self.root = base / "proj"
        (self.root / "public").mkdir(parents=True)
        self.src = base / "gen"
        make_image(self.src / "Pic One.png", 400, 200)
        make_video(self.src / "clip.mp4", fps=24, w=2400, h=1350)
        self.P = str(self.root)

    def tearDown(self):
        self._td.cleanup()

    def imp(self, f, *extra, pick="user"):
        return run(ms.main, ["import", self.P, str(self.src / f), "--shot", "s4", "--tool", "即梦网页",
                             "--prompt", "一瓶水", "--picked-by", pick, *extra])

    def items(self):
        return json.loads((self.root / "media/sources.json").read_text(encoding="utf-8"))

    def test_sheet_files(self):
        code, out = run(ms.main, ["sheet", self.P, "--name", "s4", "--files",
                                  str(self.src / "Pic One.png"), str(self.src / "clip.mp4")])
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "media/candidates/s4_sheet.jpg").stat().st_size > 0)
        self.assertIn("第  1 张 =", out)
        self.assertIn("clip.mp4", out)
        code, out = run(ms.main, ["sheet", self.P, "--name", "s4", "--files", str(self.src / "none.png")])
        self.assertEqual(code, 2)

    def test_import_photo_video(self):
        code, out = self.imp("Pic One.png", "--model", "gpt-image-2")
        self.assertEqual(code, 0, out)
        code, out = self.imp("clip.mp4", "--fps", "30")
        self.assertEqual(code, 0, out)
        by = {e["file"]: e for e in self.items()}
        p = by["media/s4/gen-pic-one.png"]
        self.assertEqual((p["source"], p["license"], p["tool"], p["model"], p["kind"]),
                         ("generated", "generated", "即梦网页", "gpt-image-2", "photo"))
        self.assertEqual(p["generated_file"], "media/generated/s4/gen-pic-one.png")
        self.assertEqual(p["attribution"], "AI 生成（即梦网页）")
        self.assertNotIn("url", p)
        v = by["media/s4/gen-clip.mp4"]
        self.assertEqual((v["kind"], v["fps"], v["w"], v["h"]), ("video", 30.0, 1920, 1080))
        for f in ("media/generated/s4/gen-clip.mp4", "public/media/s4/gen-clip.mp4",
                  "media/generated/s4/gen-pic-one.png", "public/media/s4/gen-pic-one.png"):
            self.assertTrue((self.root / f).is_file(), f)
        info = ms.probe(self.root / "public/media/s4/gen-clip.mp4")
        self.assertEqual((info["codec"], info["fps"]), ("h264", 30.0))
        self.assertEqual(ms.sha256_file(self.root / "media/generated/s4/gen-clip.mp4"), v["sha256"])
        # 重复导入按 file 去重
        self.imp("Pic One.png")
        self.assertEqual(len(self.items()), 2)

    def test_import_requires_fields(self):
        with self.assertRaises(SystemExit):
            run(ms.main, ["import", self.P, str(self.src / "Pic One.png"), "--shot", "s4"])
        code, out = run(ms.main, ["import", self.P, str(self.src / "Pic One.png"), "--shot", "s4", "--tool", " ",
                                  "--prompt", "x", "--picked-by", "user"])
        self.assertEqual(code, 2)

    def test_fetch_restores_from_tracked_copy(self):
        self.imp("clip.mp4")
        pub = self.root / "public/media/s4/gen-clip.mp4"
        pub.unlink()
        code, out = run(ms.main, ["fetch", self.P])
        self.assertEqual(code, 0, out)
        self.assertTrue(pub.is_file())
        # 入库副本缺失 → 报错
        pub.unlink()
        (self.root / "media/generated/s4/gen-clip.mp4").unlink()
        code, out = run(ms.main, ["fetch", self.P])
        self.assertEqual(code, 1)
        self.assertIn("只能从入库副本复原", out)

    def test_credits_ai_statement(self):
        self.imp("Pic One.png", "--model", "m1")
        self.assertEqual(run(ms.main, ["credits", self.P])[0], 0)
        t = (self.root / "media/CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("## AI 生成", t)
        self.assertIn("m1", t)
        self.assertIn("部分画面由 AI 生成。", t.split("## 视频简介署名文字")[1])

    def test_check_media(self):
        self.imp("Pic One.png", pick=PICK)
        run(ms.main, ["credits", self.P])
        code, out = run(cm.main, [self.P])
        self.assertEqual(code, 0, out)
        # 缺声明
        c = self.root / "media/CREDITS.md"
        txt = c.read_text(encoding="utf-8")
        c.write_text(txt.replace("部分画面由 AI 生成", "x"), encoding="utf-8")
        code, out = run(cm.main, [self.P])
        self.assertEqual(code, 1)
        self.assertIn("部分画面由 AI 生成", out)
        c.write_text(txt, encoding="utf-8")
        # 缺 tool/prompt
        items = self.items()
        items[0]["tool"], items[0]["prompt"] = "", ""
        ms.save_sources(self.root, items)
        code, out = run(cm.main, [self.P])
        self.assertIn("缺 tool", out)
        self.assertIn("缺 prompt", out)
        items[0]["tool"], items[0]["prompt"] = "t", "p"
        # agent 理由不合格
        items[0]["picked_by"] = "agent:好看"
        ms.save_sources(self.root, items)
        self.assertIn("代理挑选必须写联系表第几张", run(cm.main, [self.P])[1])
        items[0]["picked_by"] = "user"
        ms.save_sources(self.root, items)
        # sha 不一致
        gp = self.root / "media/generated/s4/gen-pic-one.png"
        orig = gp.read_bytes()
        gp.write_bytes(orig + b"0")
        code, out = run(cm.main, [self.P])
        self.assertEqual(code, 1)
        self.assertIn("sha256 与记录不一致", out)
        # 副本缺失
        gp.unlink()
        self.assertIn("generated_file 不存在", run(cm.main, [self.P])[1])
        gp.write_bytes(orig)
        # 无条目的入库文件
        shutil.copyfile(gp, self.root / "media/generated/s4/stray.png")
        code, out = run(cm.main, [self.P])
        self.assertEqual(code, 1)
        self.assertIn("stray.png 不在 sources.json", out)


if __name__ == "__main__":
    unittest.main()
