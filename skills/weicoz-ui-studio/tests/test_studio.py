import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio", ROOT / "scripts/studio.py")
studio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio)


class StudioTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def manifest(self, value):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_compare_copies_resources_and_escapes_untrusted_metadata(self):
        (self.root / "one").mkdir()
        (self.root / "one/index.html").write_text('<link rel="stylesheet" href="theme.css">')
        (self.root / "one/theme.css").write_text("body{color:green}")
        manifest = self.manifest({"title": "<script>bad()</script>", "candidates": [{"name": '<img onerror="bad()">', "path": "one/index.html"}]})
        output = self.root / "comparison"
        result = studio.compare(manifest, output)
        self.assertEqual(result["candidates"], 1)
        page = (output / "index.html").read_text()
        self.assertIn("&lt;script&gt;bad()", page)
        self.assertIn("candidate-1/index.html", page)
        self.assertTrue((output / "candidate-1/theme.css").is_file())
        with self.assertRaises(ValueError):
            studio.compare(manifest, output)

    def test_compare_rejects_escape_symlink_and_overlap_before_writing(self):
        for entry in [{"name": "bad", "path": "../outside.html"}, {"name": "bad", "url": "javascript:alert(1)"}, {"name": "bad", "url": "https://user:secret@example.com"}]:
            with self.assertRaises(ValueError):
                studio.compare(self.manifest({"candidates": [entry]}), self.root / "output")
            self.assertFalse((self.root / "output").exists())
        (self.root / "one").mkdir()
        (self.root / "one/index.html").write_text("hello")
        manifest = self.manifest({"candidates": [{"name": "one", "path": "one/index.html"}]})
        with self.assertRaises(ValueError):
            studio.compare(manifest, self.root / "one/output")
        (self.root / "one/linked").symlink_to(self.root / "manifest.json")
        with self.assertRaises(ValueError):
            studio.compare(manifest, self.root / "output")

    def test_candidate_filename_is_encoded_for_browser_navigation(self):
        (self.root / "one").mkdir()
        (self.root / "one/order#mobile?.html").write_text("内容")
        manifest = self.manifest({"candidates": [{"name": "mobile", "path": "one/order#mobile?.html"}]})
        studio.compare(manifest, self.root / "output")
        self.assertIn("order%23mobile%3F.html", (self.root / "output/index.html").read_text())
        self.assertTrue((self.root / "output/candidate-1/order#mobile?.html").is_file())

    def parity_spec(self):
        for name in ["reference.png", "candidate.png"]:
            Image.new("RGBA", (3, 2), (20, 40, 60, 255)).save(self.root / name)
        env = {"browser": "test-browser", "os": "test-os", "fonts": "test-fonts", "dpr": 1, "zoom": 1, "reduced_motion": True}
        return {"scope": "self-regression", "reference_source": "unit fixture", "expected_states": ["idle"], "cases": [{"id": "idle", "reference": "reference.png", "candidate": "candidate.png", "reference_environment": env.copy(), "candidate_environment": env.copy(), "reference_task_passed": True, "candidate_task_passed": True}]}

    def test_parity_exact_pixels_pass_and_rgb_or_alpha_differences_fail(self):
        data = self.parity_spec()
        self.assertTrue(studio.parity(self.manifest(data))["passed"])
        for pixel in [(21, 40, 60, 255), (20, 40, 60, 254)]:
            image = Image.new("RGBA", (3, 2), (20, 40, 60, 255))
            image.putpixel((1, 1), pixel)
            image.save(self.root / "candidate.png")
            result = studio.parity(self.manifest(data))
            self.assertFalse(result["passed"])
            self.assertEqual(result["cases"][0]["different_pixels"], 1)

    def test_missing_state_duplicate_environment_task_or_source_never_pass(self):
        for kind in ["missing-state", "duplicate", "environment", "missing-env", "task", "source", "missing-image", "dimensions"]:
            with self.subTest(kind=kind):
                data = self.parity_spec()
                if kind == "missing-state": data["expected_states"].append("error")
                if kind == "duplicate": data["cases"].append(data["cases"][0].copy())
                if kind == "environment": data["cases"][0]["candidate_environment"]["fonts"] = "different"
                if kind == "missing-env": data["cases"][0]["candidate_environment"].pop("fonts")
                if kind == "task": data["cases"][0]["candidate_task_passed"] = False
                if kind == "source": data["reference_source"] = ""
                if kind == "missing-image": data["cases"][0]["candidate"] = "missing.png"
                if kind == "dimensions": Image.new("RGB", (1, 1)).save(self.root / "candidate.png")
                self.assertFalse(studio.parity(self.manifest(data))["passed"])

    def test_review_output_does_not_overwrite_without_explicit_force(self):
        target = self.root / "review.json"
        studio.write_json(target, {"kept": True})
        with self.assertRaises(FileExistsError): studio.write_json(target, {})
        self.assertEqual(json.loads(target.read_text()), {"kept": True})

    def test_media_sheet_preserves_dimensions_transparency_and_attribution(self):
        Image.new("RGBA", (10, 20), (1, 2, 3, 80)).save(self.root / "source.png")
        entry = {"title": "本地生成图", "path": "source.png", "license": "CC0", "usage": "page", "source_url": "local-generated"}
        manifest = self.manifest({"sources": [entry]})
        result = studio.sheet(manifest, self.root / "media")
        self.assertEqual(result["assets"], 1)
        with Image.open(self.root / "media/asset-01.png") as image:
            self.assertEqual(image.size, (10, 20))
            self.assertEqual(image.getpixel((0, 0)), (1, 2, 3, 80))
        self.assertIn("CC0", (self.root / "media/SOURCES.md").read_text())
        entry["license"] = "unknown"
        with self.assertRaises(ValueError):
            studio.sheet(self.manifest({"sources": [entry]}), self.root / "rejected")
        self.assertFalse((self.root / "rejected").exists())


if __name__ == "__main__":
    unittest.main()
