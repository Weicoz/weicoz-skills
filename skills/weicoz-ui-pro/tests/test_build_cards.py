"""The card gallery builder only rebuilds when it is run without arguments."""

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_cards.py"
GALLERY = ROOT / "assets" / "cards" / "gallery.html"


@unittest.skipUnless(SCRIPT.is_file() and GALLERY.is_file(), "card gallery is not part of this edition")
class CardGalleryBuilderTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")

    def test_help_explains_the_script_without_rebuilding(self):
        before = GALLERY.stat().st_mtime_ns
        run = self.run_script("--help")
        self.assertEqual(run.returncode, 0)
        self.assertIn("gallery.html", run.stdout)
        self.assertNotIn("Built", run.stdout)
        self.assertEqual(GALLERY.stat().st_mtime_ns, before)

    def test_stray_arguments_are_rejected_without_rebuilding(self):
        before = GALLERY.stat().st_mtime_ns
        run = self.run_script("cards.json")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(GALLERY.stat().st_mtime_ns, before)

    def test_committed_gallery_matches_the_sources(self):
        generated = [GALLERY, GALLERY.parent / "shared" / "land-mask.js"]
        before = {path: path.read_bytes() for path in generated}
        try:
            run = self.run_script()
            self.assertEqual(run.returncode, 0, run.stderr)
            for path in generated:
                self.assertEqual(path.read_bytes(), before[path], f"{path.name} is stale; rebuild it with scripts/build_cards.py")
        finally:
            for path, content in before.items():
                path.write_bytes(content)


if __name__ == "__main__":
    unittest.main()
