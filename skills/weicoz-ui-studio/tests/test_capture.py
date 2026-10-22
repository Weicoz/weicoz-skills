import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("capture", Path(__file__).resolve().parents[1] / "scripts/capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CaptureTest(unittest.TestCase):
    def test_manifest_boundaries_and_unicode_filenames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "页#1.html").write_text("<p>内容</p>")
            path = root / "manifest.json"
            case = {"id": "默认状态", "path": "页#1.html"}
            path.write_text(json.dumps({"cases": [case]}))
            data, _ = capture.prepare(path, root / "out")
            self.assertEqual(data["cases"][0]["relative_url"], "%E9%A1%B5%231.html")
            for bad in [{"id": "bad", "path": "../escape.html"}, {"id": "bad", "url": "file:///tmp/x"}, {"id": "bad", "path": "页#1.html", "viewport": {"width": -1, "height": 1000}}, {"id": "bad", "path": "页#1.html", "actions": [{"type": "execute-shell"}]}]:
                path.write_text(json.dumps({"cases": [bad]}))
                with self.assertRaises(ValueError): capture.prepare(path, root / "out")
            path.write_text(json.dumps({"cases": [case, case]}))
            with self.assertRaises(ValueError): capture.prepare(path, root / "out")


if __name__ == "__main__":
    unittest.main()
