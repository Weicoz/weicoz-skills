#!/usr/bin/env python3
"""Unit tests for weicoz-ui-pro upstream_refresh.py (no network, temp dirs only)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import sync_upstream, upstream_refresh as ur

T0 = 10_000_000
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}
CHECK_UPDATE = (
    'CLI = "github:example-org/example-cli#' + "a" * 40 + '"\n'
    'UPDATE_ENV_KEYS = {"PATH", "HOME", "OIL_TOKEN"}\n'
)


def skill_md(version: str, name: str = "oil-ui-pro") -> str:
    return (
        f"---\nname: {name}\nallowed-tools:\n  - Bash(python3 *check_update.py*)\n"
        f'metadata:\n  version: "{version}"\n---\n\n# {name}\n\n'
        "## 开始前\n\n版本检查：!`sh check_update.sh`\n\n## 选择范围\n\n正文\n"
    )


def make_upstream(root: Path, version: str) -> Path:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(skill_md(version), encoding="utf-8")
    (root / "scripts" / "check_update.py").write_text(CHECK_UPDATE, encoding="utf-8")
    (root / "README.md").write_text("# oil-ui-pro\n\n介绍\n", encoding="utf-8")
    return root


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        env = {
            **GIT_ENV,
            "HOME": str(self.tmp / "home"),
            "XDG_STATE_HOME": str(self.tmp / "state"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        }
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("WEICOZ_UI_PRO_NO_REFRESH", None)
        self.up = make_upstream(self.tmp / "upstream", "0.31.0")
        os.environ["OIL_UI_PRO_UPSTREAM"] = str(self.up)
        # 任何测试都不得真正联网
        f = mock.patch.object(ur, "fetch_latest", side_effect=AssertionError("network"))
        self.fetch = f.start()
        self.addCleanup(f.stop)

    def make_skill(self, git: bool = True) -> Path:
        repo = self.tmp / "repo"
        skill = repo / "skills" / "weicoz-ui-pro"
        skill.mkdir(parents=True)
        with mock.patch("sys.stdout"):
            sync_upstream.sync(self.up, apply=True, skill_dir=skill)
        if git:
            sh(repo, "git", "init", "-q")
            sh(repo, "git", "config", "commit.gpgsign", "false")
            sh(repo, "git", "add", ".")
            sh(repo, "git", "commit", "-qm", "init")
        return skill


class TestGating(Base):
    def test_no_upstream_is_silent_and_offline(self):
        os.environ["OIL_UI_PRO_UPSTREAM"] = "/nonexistent"
        skill = self.tmp / "skill"
        skill.mkdir()
        self.assertIsNone(ur.refresh(skill))  # fetch_latest 会抛 AssertionError
        self.assertFalse((self.tmp / "state").exists())

    def test_disabled_by_env(self):
        os.environ["WEICOZ_UI_PRO_NO_REFRESH"] = "1"
        self.assertIsNone(ur.refresh(self.make_skill()))

    def test_main_never_raises(self):
        with mock.patch.object(ur, "refresh", side_effect=RuntimeError("boom")):
            self.assertEqual(ur.main(), 0)


class TestThrottle(Base):
    def test_checks_at_most_once_per_interval(self):
        skill = self.make_skill()
        with mock.patch.object(ur, "fetch_latest", return_value="0.31.0") as f:
            ur.refresh(skill, now=T0)
            ur.refresh(skill, now=T0 + 599)
            self.assertEqual(f.call_count, 1)
            ur.refresh(skill, now=T0 + 601)
            self.assertEqual(f.call_count, 2)

    def test_network_failure_not_retried_within_one_hour(self):
        skill = self.make_skill()
        with mock.patch.object(ur, "fetch_latest", side_effect=OSError("down")) as f:
            self.assertIsNone(ur.refresh(skill, now=T0))
            ur.refresh(skill, now=T0 + 1800)
            self.assertEqual(f.call_count, 1)
            ur.refresh(skill, now=T0 + 3601)
            self.assertEqual(f.call_count, 2)


class TestVersions(Base):
    def test_version_compare_numeric(self):
        self.assertGreater(ur.parse_version("0.10.0"), ur.parse_version("0.9.9"))

    def test_up_to_date_is_silent_and_no_update(self):
        skill = self.make_skill()
        with mock.patch.object(ur, "fetch_latest", return_value="0.31.0"), \
                mock.patch.object(ur, "update_upstream") as upd:
            self.assertIsNone(ur.refresh(skill, now=T0))
            upd.assert_not_called()

    def test_stale_upstream_is_updated_then_synced(self):
        skill = self.make_skill()

        def fake_update(upstream, name, latest):
            make_upstream(upstream, latest)
            return True

        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"), \
                mock.patch.object(ur, "update_upstream", side_effect=fake_update) as upd:
            msg = ur.refresh(skill, now=T0)
        upd.assert_called_once()
        self.assertIn("0.31.0→0.32.0", msg)

    def test_update_failure_cooldown(self):
        skill = self.make_skill()
        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"), \
                mock.patch.object(ur, "update_upstream", return_value=False) as upd:
            self.assertIsNone(ur.refresh(skill, now=T0))
            self.assertIsNone(ur.refresh(skill, now=T0 + 700))
            self.assertEqual(upd.call_count, 1)
            ur.refresh(skill, now=T0 + ur.UPDATE_RETRY_AFTER_FAILURE + 1)
            self.assertEqual(upd.call_count, 2)


class TestUpdateUpstream(Base):
    def test_constants_parsed_from_upstream_not_hardcoded(self):
        cli, keys = ur.parse_upstream_constants(self.up)
        self.assertEqual(cli, "github:example-org/example-cli#" + "a" * 40)
        self.assertEqual(keys, {"PATH", "HOME", "OIL_TOKEN"})

    def test_env_whitelist(self):
        with mock.patch.dict(os.environ, {"SECRET_KEY": "x", "OIL_TOKEN": "t"}):
            env = ur.clean_env({"PATH", "HOME", "OIL_TOKEN"})
        self.assertNotIn("SECRET_KEY", env)
        self.assertEqual(env["OIL_TOKEN"], "t")
        self.assertEqual(env["CI"], "1")

    def test_falls_back_to_clone_when_upstream_script_fails(self):
        with mock.patch.object(ur, "update_via_upstream_script", side_effect=OSError("npx")), \
                mock.patch.object(ur, "update_via_cli_clone",
                                  side_effect=lambda up, n, cli, env: make_upstream(up, "0.32.0") and True) as clone:
            self.assertTrue(ur.update_upstream(self.up, "oil-ui-pro", "0.32.0"))
        clone.assert_called_once()
        self.assertEqual(clone.call_args[0][2], "github:example-org/example-cli#" + "a" * 40)

    def test_skips_clone_when_upstream_script_succeeds(self):
        with mock.patch.object(ur, "update_via_upstream_script",
                               side_effect=lambda up, env: make_upstream(up, "0.32.0")), \
                mock.patch.object(ur, "update_via_cli_clone") as clone:
            self.assertTrue(ur.update_upstream(self.up, "oil-ui-pro", "0.32.0"))
        clone.assert_not_called()

    def test_clone_commands(self):
        calls = []
        sha = "a" * 40

        def fake_run(cmd, env, timeout, cwd=None):
            calls.append((cmd, cwd))
            out = sha + "\n" if "rev-parse" in cmd else ""
            if cmd[1:3] == ["bin/oil.js", "update"]:
                out = '{"ok":true,"status":"updated"}\n'
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, 0, out, "")

        with mock.patch.object(ur, "run", side_effect=fake_run), \
                mock.patch.object(shutil, "which", side_effect=lambda n, path=None: "/bin/" + n):
            ok = ur.update_via_cli_clone(self.up, "oil-ui-pro", "github:example-org/example-cli#" + sha, {"PATH": "/bin"})
        self.assertTrue(ok)
        flat = [" ".join(c) for c, _ in calls]
        self.assertTrue(any("clone" in f and "https://github.com/example-org/example-cli.git" in f for f in flat))
        node_call = [c for c in calls if c[0][0] == "/bin/node"][0]
        self.assertEqual(node_call[0][1:], ["bin/oil.js", "update", "oil-ui-pro", "--path", str(self.up), "--json"])
        self.assertIsNotNone(node_call[1])

    def test_rejects_malformed_cli(self):
        self.assertFalse(ur.update_via_cli_clone(self.up, "oil-ui-pro", "github:x/y#main", {"PATH": "/bin"}))


class TestSyncAndCommit(Base):
    def bump(self, v="0.32.0"):
        make_upstream(self.up, v)

    def test_commits_only_skill_dir(self):
        skill = self.make_skill()
        repo = skill.parents[1]
        (repo / "outside.txt").write_text("unrelated")
        self.bump()
        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"):
            msg = ur.refresh(skill, now=T0)
        self.assertRegex(msg, r"weicoz-ui-pro 已同步上游 0\.31\.0→0\.32\.0 并提交 [0-9a-f]+，请推送主仓库后重新读取 SKILL\.md")
        self.assertEqual(sync_upstream.read_version((skill / "SKILL.md").read_text()), "0.32.0")
        files = sh(repo, "git", "show", "--name-only", "--format=%B", "HEAD")
        self.assertIn("同步上游 oil-ui-pro 0.31.0 → 0.32.0", files)
        self.assertTrue(files.rstrip().splitlines()[0].startswith("chore"))
        self.assertIn("Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", files)
        self.assertNotIn("outside.txt", files)
        self.assertIn("outside.txt", sh(repo, "git", "status", "--porcelain"))
        # 不推送、无多余远端
        self.assertEqual(sh(repo, "git", "remote"), "")

    def test_dirty_tree_only_notifies_once(self):
        skill = self.make_skill()
        (skill / "local-note.md").write_text("wip")
        self.bump()
        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"):
            msg = ur.refresh(skill, now=T0)
            self.assertIn("未提交改动，未自动同步", msg)
            self.assertIn("0.31.0→0.32.0", msg)
            self.assertIsNone(ur.refresh(skill, now=T0 + 60))
        self.assertEqual(sync_upstream.read_version((skill / "SKILL.md").read_text()), "0.31.0")
        self.assertEqual(sh(skill.parents[1], "git", "rev-list", "--count", "HEAD"), "1")

    def test_non_git_dir_syncs_without_commit(self):
        skill = self.make_skill(git=False)
        self.bump()
        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"):
            msg = ur.refresh(skill, now=T0)
        self.assertIn("0.31.0→0.32.0", msg)
        self.assertIn("未提交", msg)

    def test_offline_still_syncs_when_upstream_already_newer(self):
        skill = self.make_skill()
        self.bump()
        with mock.patch.object(ur, "fetch_latest", side_effect=OSError("down")):
            msg = ur.refresh(skill, now=T0)
        self.assertIn("并提交", msg)

    def test_sync_failure_is_silent(self):
        skill = self.make_skill()
        self.bump()
        with mock.patch.object(ur, "fetch_latest", return_value="0.32.0"), \
                mock.patch.object(sync_upstream, "sync", return_value=3):
            self.assertIsNone(ur.refresh(skill, now=T0))


if __name__ == "__main__":
    unittest.main()
