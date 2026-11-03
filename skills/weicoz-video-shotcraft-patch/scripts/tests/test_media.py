"""media-source.py / check-media.py 的离线测试（fixture JSON + 本地 ffmpeg 生成的小文件，不联网）。"""
import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
FIX = HERE / "fixtures"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ms = load("media_source", "media-source.py")
cm = load("check_media", "check-media.py")


def fx(n):
    return json.loads((FIX / n).read_text(encoding="utf-8"))


def run(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue() + err.getvalue()


def make_video(path, fps=30, codec="libx264", w=320, h=180):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate={fps}:duration=1",
                    "-c:v", codec, "-pix_fmt", "yuv420p", str(path)], check=True)


def make_image(path, w=320, h=180):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}", "-frames:v", "1",
                    str(path)], check=True)


class Parse(unittest.TestCase):
    def test_pexels(self):
        p = ms.parse_pexels(fx("pexels_photo.json"), "photo")[0]
        self.assertEqual((p["key"], p["author"], p["license"], p["w"]), ("pexels:101", "Ann", "pexels", 4000))
        v = ms.parse_pexels(fx("pexels_video.json"), "video")[0]
        self.assertEqual(len(v["files"]), 2)  # hls 被排除
        self.assertEqual(v["dur"], 12)
        self.assertEqual(ms.choose_file(v)["w"], 1920)

    def test_pixabay(self):
        p = ms.parse_pixabay(fx("pixabay_photo.json"), "photo")[0]
        self.assertEqual(p["w"], 1280)  # 无原图权限，按 1280 版本计
        self.assertEqual(p["author_url"], "https://pixabay.com/users/carl-9/")
        v = ms.parse_pixabay(fx("pixabay_video.json"), "video")[0]
        self.assertEqual((len(v["files"]), v["w"], v["dur"]), (2, 1920, 20))
        self.assertIn("555_640x360", v["thumb"])

    def test_unsplash(self):
        c = ms.parse_unsplash(fx("unsplash.json"))[0]
        self.assertEqual((c["key"], c["license"], c["author"]), ("unsplash:abcDEF", "unsplash", "Eve"))
        self.assertTrue(c["download_location"].endswith("/download"))

    def test_wikimedia(self):
        photos = ms.parse_wikimedia(fx("wikimedia.json"), "photo")
        self.assertEqual([c["id"] for c in photos], ["1", "2", "3", "4"])  # pdf 被排除
        self.assertEqual(photos[0]["author"], "Fay & Co")
        self.assertEqual(photos[0]["license"], "cc-by-4.0")
        self.assertEqual(photos[0]["author_url"], "https://commons.wikimedia.org/wiki/User:Fay".replace("https:", "https:"))
        self.assertEqual(photos[1]["license"], "cc-by-sa-3.0")
        self.assertEqual(photos[2]["license"], "unknown")
        videos = ms.parse_wikimedia(fx("wikimedia.json"), "video")
        self.assertEqual((videos[0]["license"], videos[0]["dur"]), ("pd", 8.5))
        big = ms.parse_wikimedia(fx("wikimedia.json"), "photo", big_thumb=True)
        self.assertEqual(big[0]["files"][0]["url"], "https://upload.example/t1.jpg")  # 4000 宽超 3840，用缩略图
        self.assertEqual(big[3]["files"][0]["url"], "https://upload.example/4")  # 3000 宽用原图
    

class License(unittest.TestCase):
    def test_normalize(self):
        n = ms.normalize_license
        self.assertEqual(n("pexels", "x"), "pexels")
        self.assertEqual(n("wikimedia", "CC BY 4.0"), "cc-by-4.0")
        self.assertEqual(n("wikimedia", "CC BY-SA 3.0"), "cc-by-sa-3.0")
        self.assertEqual(n("wikimedia", "CC0 1.0"), "cc0")
        self.assertEqual(n("wikimedia", "Public domain"), "pd")
        self.assertEqual(n("wikimedia", "CC BY-NC-SA 4.0"), "unknown")
        self.assertEqual(n("wikimedia", "CC BY-ND 2.0"), "unknown")
        self.assertEqual(n("wikimedia", "GFDL"), "unknown")
        self.assertEqual(n("wikimedia", ""), "unknown")

    def test_policy(self):
        ok = ms.license_ok
        for lic in ("pexels", "pixabay", "unsplash", "cc0", "pd", "cc-by-4.0"):
            self.assertTrue(ok(lic), lic)
        self.assertFalse(ok("cc-by-sa-4.0"))
        self.assertTrue(ok("cc-by-sa-4.0", True))
        self.assertFalse(ok("unknown", True))
        self.assertFalse(ok("cc-by-nc-4.0", True))


class Score(unittest.TestCase):
    def mk(self, w, h, dur=None, rank=0, kind="video"):
        return ms.cand("pexels", kind, 1, w=w, h=h, dur=dur, rank=rank)

    def test_ordering(self):
        good = self.mk(1920, 1080, 10)
        lowres = self.mk(1280, 720, 10)
        portrait = self.mk(1080, 1920, 10)
        short = self.mk(1920, 1080, 2)
        kw = dict(min_width=1920, orientation="landscape", min_dur=5)
        s = {k: ms.score(v, **kw) for k, v in dict(good=good, lowres=lowres, portrait=portrait, short=short).items()}
        self.assertGreater(s["good"], s["lowres"])
        self.assertGreater(s["good"], s["portrait"])
        self.assertGreater(s["good"], s["short"])
        self.assertLess(s["short"], s["good"] - 15)  # 时长不足大幅扣分

    def test_rank_and_lowres_penalty(self):
        a = self.mk(1920, 1080, 10, rank=0)
        b = self.mk(1920, 1080, 10, rank=8)
        self.assertGreater(ms.score(a), ms.score(b))
        low = self.mk(1000, 562, 10)
        self.assertLess(ms.score(low, allow_lowres=True), ms.score(low))


class Sources(unittest.TestCase):
    def test_upsert(self):
        items = []
        ms.upsert_source(items, {"file": "media/a.jpg", "v": 1})
        ms.upsert_source(items, {"file": "media/b.jpg", "v": 1})
        ms.upsert_source(items, {"file": "media/a.jpg", "v": 2})
        self.assertEqual([(e["file"], e["v"]) for e in items], [("media/a.jpg", 2), ("media/b.jpg", 1)])


def entry(file, lic="cc-by-4.0", **kw):
    e = {"file": file, "kind": "photo", "source": "wikimedia", "id": "1", "url": "https://x/1", "download_url": "",
         "author": "Fay", "author_url": "", "license": lic, "license_url": "", "retrieved": "2026-01-01",
         "src_sha256": "a", "sha256": "b", "w": 2000, "h": 1000, "dur": None, "fps": None, "shot": "s1",
         "query": "", "picked_by": "user", "attribution": f'"T" by Fay, CC BY 4.0, via Wikimedia Commons'}
    e.update(kw)
    return e


class Credits(unittest.TestCase):
    def test_credits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ms.save_sources(root, [entry("media/s1/a.jpg"), entry("media/s1/b.jpg", "pexels", source="pexels",
                                    attribution="Photo by Ann on Pexels"),
                                   entry("media/s1/c.jpg", "unsplash", source="unsplash", attribution="Photo by Eve on Unsplash")])
            a = ms.build_parser().parse_args(["credits", td])
            ms.cmd_credits(a)
            t = (root / "media" / "CREDITS.md").read_text(encoding="utf-8")
            head, tail = t.split("## 全部素材来源")
            self.assertIn("media/s1/a.jpg", head)
            self.assertIn("media/s1/c.jpg", head)
            self.assertNotIn("media/s1/b.jpg", head)  # pexels 不需要署名
            self.assertIn("media/s1/b.jpg", tail)
            self.assertIn("Photo by Eve on Unsplash", tail)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 ffmpeg")
class CheckMedia(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "src").mkdir()
        (self.root / "public").mkdir()

    def tearDown(self):
        self._td.cleanup()

    def chk(self, *extra):
        return run(cm.main, [str(self.root), *extra])

    def good_project(self):
        make_image(self.root / "public/media/s1/a.png", 2000, 1000)
        make_video(self.root / "public/media/s1/v.mp4")
        ms.save_sources(self.root, [entry("media/s1/a.png"),
                                    entry("media/s1/v.mp4", "pexels", kind="video", source="pexels")])
        (self.root / "media" / "CREDITS.md").write_text("`media/s1/a.png`\n", encoding="utf-8")

    def test_no_media(self):
        code, out = self.chk()
        self.assertEqual(code, 0)
        self.assertIn("本工程没有真实素材", out)

    def test_missing_dir(self):
        code, _ = run(cm.main, [str(self.root / "nope")])
        self.assertEqual(code, 2)

    def test_pass_with_warning(self):
        self.good_project()
        (self.root / "src/a.tsx").write_text('staticFile("media/s1/a.png")\n', encoding="utf-8")
        code, out = self.chk()
        self.assertEqual(code, 0, out)
        self.assertIn("宽度 320 < 1920", out)  # 视频 320 宽

    def test_untracked_file(self):
        self.good_project()
        make_image(self.root / "public/media/s1/stray.png")
        code, out = self.chk()
        self.assertEqual(code, 1)
        self.assertIn("stray.png 不在 sources.json", out)

    def test_bad_license(self):
        self.good_project()
        ms.save_sources(self.root, [entry("media/s1/a.png", "unknown"), entry("media/s1/v.mp4", "cc-by-sa-4.0", kind="video")])
        code, out = self.chk()
        self.assertEqual(code, 1)
        self.assertIn("许可 unknown 不合策略", out)
        self.assertIn("SA 需 --allow-sa", out)
        code, out = self.chk("--allow-sa")
        self.assertNotIn("SA 需", out)

    def test_video_codec_fps(self):
        make_video(self.root / "public/media/s1/v.mp4", fps=24, codec="mpeg4")
        ms.save_sources(self.root, [entry("media/s1/v.mp4", "pexels", kind="video")])
        code, out = self.chk()
        self.assertEqual(code, 1)
        self.assertIn("必须是 H.264", out)
        self.assertIn("帧率", out)

    def test_credits_missing_or_incomplete(self):
        self.good_project()
        (self.root / "media" / "CREDITS.md").unlink()
        code, out = self.chk()
        self.assertEqual(code, 1)
        self.assertIn("CREDITS.md 缺失", out)
        (self.root / "media" / "CREDITS.md").write_text("nothing\n", encoding="utf-8")
        code, out = self.chk()
        self.assertIn("没有包含它", out)

    def test_src_hotlink_and_unknown_ref(self):
        self.good_project()
        (self.root / "src/b.tsx").write_text(
            'const u="https://example.com/pic.jpg";\nconst v=staticFile("media/s9/ghost.mp4");\n', encoding="utf-8")
        code, out = self.chk()
        self.assertEqual(code, 1)
        self.assertIn("盗链", out)
        self.assertIn("media/s9/ghost.mp4，但它不在 sources.json", out)

    def test_missing_file_warns(self):
        self.good_project()
        (self.root / "public/media/s1/a.png").unlink()
        code, out = self.chk()
        self.assertEqual(code, 0, out)
        self.assertIn("media-source.py fetch", out)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 ffmpeg")
class GetFetch(unittest.TestCase):
    """用本地文件替代网络，走完 get → fetch 流程。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name) / "proj"
        (self.root / "public").mkdir(parents=True)
        self.srcdir = Path(self._td.name) / "origin"
        make_video(self.srcdir / "v.mp4", fps=25, w=640, h=360)
        make_image(self.srcdir / "p.png", 400, 200)
        self.orig = (ms.api_detail, ms.download, ms.http_json)
        self.detail = ms.parse_pexels(fx("pexels_video.json"), "video")[0]
        self.photo = ms.parse_wikimedia(fx("wikimedia.json"), "photo")[0]
        self.photo["files"] = [{"url": "local://p", "w": 400, "h": 200, "type": "image/png"}]
        self.detail["files"] = [{"url": "local://v", "w": 1920, "h": 1080, "type": "video/mp4"}]

        def api_detail(source, id_, kind):
            return self.detail if kind == "video" else self.photo

        def download(url, dest, headers=None):
            src = self.srcdir / ("v.mp4" if url.endswith("v") else "p.png")
            shutil.copyfile(src, dest)
            return ms.sha256_file(dest)

        ms.api_detail, ms.download = api_detail, download

    def tearDown(self):
        ms.api_detail, ms.download, ms.http_json = self.orig
        self._td.cleanup()

    def test_get_fetch_credits_check(self):
        P = str(self.root)
        code, out = run(ms.main, ["get", P, "wikimedia:1", "--picked-by", "agent:测试", "--shot", "s1"])
        self.assertEqual(code, 0, out)
        code, out = run(ms.main, ["get", P, "pexels:202", "--kind", "video", "--picked-by", "user", "--shot", "s2", "--fps", "30"])
        self.assertEqual(code, 0, out)
        items = json.loads((self.root / "media/sources.json").read_text(encoding="utf-8"))
        self.assertEqual({e["file"] for e in items}, {"media/s1/wikimedia-1.png", "media/s2/pexels-202.mp4"})
        v = next(e for e in items if e["kind"] == "video")
        self.assertEqual((v["fps"], v["picked_by"], v["w"]), (30.0, "user", 640))
        # 重复 get 不产生重复条目
        run(ms.main, ["get", P, "wikimedia:1", "--picked-by", "user", "--shot", "s1"])
        self.assertEqual(len(json.loads((self.root / "media/sources.json").read_text(encoding="utf-8"))), 2)
        self.assertEqual(run(ms.main, ["credits", P])[0], 0)
        code, out = run(cm.main, [P])
        self.assertEqual(code, 0, out)
        # 删除后 fetch 复原
        (self.root / "public/media/s2/pexels-202.mp4").unlink()
        code, out = run(ms.main, ["fetch", P])
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "public/media/s2/pexels-202.mp4").exists())
        # 来源文件变化 → 退出 1
        items = json.loads((self.root / "media/sources.json").read_text(encoding="utf-8"))
        for e in items:
            e["src_sha256"] = "0" * 64
        ms.save_sources(self.root, items)
        code, out = run(ms.main, ["fetch", P, "--all"])
        self.assertEqual(code, 1)
        self.assertIn("来源文件已变化", out)

    def test_get_rejects_bad_license(self):
        self.photo["license"] = "cc-by-sa-4.0"
        code, out = run(ms.main, ["get", str(self.root), "wikimedia:1", "--picked-by", "user"])
        self.assertEqual(code, 1)
        self.assertIn("许可不合策略", out)
        code, out = run(ms.main, ["get", str(self.root), "wikimedia:1", "--picked-by", "user", "--allow-sa"])
        self.assertEqual(code, 0, out)


class SearchFlow(unittest.TestCase):
    def test_search_filters_and_writes(self):
        orig = ms.http_json
        ms.http_json = lambda url, headers=None: fx("wikimedia.json")
        try:
            with tempfile.TemporaryDirectory() as td:
                code, out = run(ms.main, ["search", td, "--q", "water bottle", "--kind", "photo", "--sources",
                                          "wikimedia", "--shot", "s1"])
                self.assertEqual(code, 0, out)
                data = json.loads((Path(td) / "media/candidates/s1.json").read_text(encoding="utf-8"))
                ids = {c["id"] for c in data["candidates"]}
                self.assertEqual(ids, {"1", "4"})  # NC 与 SA 被过滤；2 条
                self.assertEqual(data["filtered"]["license"], 2)
                page = (Path(td) / "media/candidates/s1.html").read_text(encoding="utf-8")
                self.assertIn("复制下载命令", page)
                self.assertIn("wikimedia:1", page)
                self.assertIn("prefers-color-scheme: dark", page.replace("prefers-color-scheme:dark", "prefers-color-scheme: dark"))
        finally:
            ms.http_json = orig

    def test_missing_key_prompt(self):
        import os
        old = os.environ.pop("PEXELS_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                code, out = run(ms.main, ["search", td, "--q", "x", "--kind", "photo", "--sources", "pexels"])
                self.assertEqual(code, 1)  # 无结果
                self.assertIn("PEXELS_API_KEY", out)
                self.assertNotIn("Traceback", out)
        finally:
            if old is not None:
                os.environ["PEXELS_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
