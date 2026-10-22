import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FreeBaselineTest(unittest.TestCase):
    def test_locked_release_preserves_all_original_files(self):
        lock = json.loads((ROOT / "upstream.lock.json").read_text())
        base = ROOT / "upstream/oil-ui"
        mapping = {archived: original for original, archived in lock.get("archive_paths", {}).items()}
        files = {mapping.get(str(path.relative_to(base)), str(path.relative_to(base))): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in base.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
        self.assertEqual(files, lock["files"])
        self.assertFalse(list(base.rglob("SKILL.md")), "上游入口必须归档，避免递归发现为第二个 Skill")
        for name in ["build_explorer.py"]:
            self.assertEqual((ROOT / "scripts" / name).read_bytes(), (base / "scripts" / name).read_bytes())
        for path in (base / "assets").rglob("*"):
            if path.is_file() and "readme" not in path.parts:
                self.assertEqual(path.read_bytes(), (ROOT / "assets" / path.relative_to(base / "assets")).read_bytes())
        for path in (base / "references").glob("*.md"):
            self.assertEqual(path.read_bytes(), (ROOT / "references/free" / path.name).read_bytes())

    def test_full_shoot_cli_keeps_free_options_and_headed_default(self):
        result = subprocess.run(["node", str(ROOT / "scripts/shoot.mjs"), str(ROOT / "assets/gallery/index.html"),
                                 "--evidence", "--zoom", "1,2", "--states", "idle,error", "--steps", "click #more", "--dry-run"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("evidence", data["flags"])
        self.assertNotIn("headless", data["flags"])
        self.assertEqual(data["zooms"], [1, 2])
        self.assertEqual(data["states"], ["idle", "error"])

    def test_media_endpoint_override_preserves_path_query_and_rejects_credentials(self):
        import os
        module = (ROOT / "scripts/curate-media.mjs").as_uri()
        script = f"import {{httpUrl}} from {json.dumps(module)}; console.log(httpUrl('https://images-api.nasa.gov/search?q=earth'));"
        env = dict(os.environ, UI_STUDIO_MEDIA_ORIGINS=json.dumps({"https://images-api.nasa.gov": "http://localhost:32123"}))
        result = subprocess.run(["node", "--input-type=module", "-e", script], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "http://localhost:32123/search?q=earth")
        for value in ["[]", "bad-json", json.dumps({"https://images-api.nasa.gov": "https://user:pass@example.com"})]:
            env["UI_STUDIO_MEDIA_ORIGINS"] = value
            result = subprocess.run(["node", "--input-type=module", "-e", script], env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
