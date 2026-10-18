"""派单与清理回归：真实临时 Git 仓库，本机 shell/RPC 模拟，不连接设备。"""
import argparse
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_rd import rd, native


class DispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rd-dispatch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "repo 中文"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.repo / "tracked.txt").write_text("base\n")
        (self.repo / "remove.txt").write_text("remove\n")
        (self.repo / "binary.dat").write_bytes(bytes(range(256)))
        self.git("add", ".")
        self.git("commit", "-qm", "fixture base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("branch", "baseline")
        self.worker = self.root / "worker" / "users" / "employee_a"
        config = self.root / "config.ini"
        config.write_text(f"[host:fixture]\nssh=fixture.invalid\nworkdir={self.root / 'worker'}\nsync=direct\npath={os.environ['PATH']}\n")
        for mock in (
            patch.object(rd, "CONFIG", str(config)),
            patch.object(rd, "STATE", str(self.root / "state")),
            patch.dict(os.environ, {"RD_USER_ID": "employee_a", "RD_REPORTS_DIR": str(self.root / "saved reports")}),
            patch.object(rd, "ssh", side_effect=self.local_shell),
            patch.object(rd, "scp_path", side_effect=lambda h, rel: str(Path(h["workdir"]) / rel)),
            patch.object(native, "request", side_effect=self.local_rpc),
            patch.object(rd, "launch", side_effect=self.finish),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            mock.__enter__()
            self.addCleanup(mock.__exit__, None, None, None)
        self.cfg = rd.Config()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def local_shell(self, host, script, check=True, stdin_data=None, stdin=None, timeout=None, stdout=None):
        shared = dict(host, workdir=host.get("shared_workdir", host["workdir"]))
        pre = f'ROOT={rd.root_expr(host)}; SHARED_ROOT={rd.root_expr(shared)}; '
        result = subprocess.run(["sh", "-c", pre + script], input=stdin_data, stdin=stdin,
                                stdout=stdout if stdout is not None else subprocess.PIPE,
                                stderr=subprocess.PIPE, text=stdin_data is not None, timeout=timeout or 20)
        out = "" if stdout is not None else result.stdout
        err = result.stderr
        if isinstance(out, bytes):
            out = out.decode()
        if isinstance(err, bytes):
            err = err.decode()
        if check and result.returncode:
            rd.die(err)
        return subprocess.CompletedProcess(result.args, result.returncode, out, err)

    def local_rpc(self, host, operation, data=None, payload=None, output=None, **kwargs):
        query = dict(data or {}, operation=operation, workdir=host["workdir"],
                     shared_workdir=host["shared_workdir"], path="")
        if output is not None:
            capture = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
            with patch.object(sys, "stdout", capture):
                native.serve(query)
            capture.flush()
            capture.buffer.seek(0)
            self.assertTrue(json.loads(capture.buffer.readline())["ok"])
            for line in capture.buffer:
                output.write(base64.b64decode(line))
            return None
        if isinstance(payload, bytes):
            payload = io.BytesIO(payload)
        return native.handle(query, payload or io.BytesIO())

    def finish(self, host, rec, *args):
        directory = Path(host["workdir"]) / "jobs" / rec["job"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "exit_code").write_text("0")

    def args(self, **overrides):
        values = dict(dir=str(self.repo), agent=None, prompt_file=None, cmd="true", test=False,
                      heavy=False, host="fixture", force_host=True, tag=[], ref="baseline", wip=False,
                      branch=None, name="fixture", project=None, include=[], model=None, effort=None,
                      timeout=15, initiator_session=None)
        values.update(overrides)
        return argparse.Namespace(**values)

    def dispatch(self, **kwargs):
        rd.cmd_run(self.args(**kwargs), self.cfg)
        return rd.all_jobs()[-1]

    def test_run_refuses_network_failure_before_registering_or_launching_job(self):
        info = dict(reachable=True, memfree="50", disk="100", network={"ok": False, "error": "TLS handshake failed"})
        for host in ("fixture", "auto"):
            with self.subTest(host=host), patch.object(rd, "probe", return_value=info), \
                 patch.object(rd, "launch") as launch, self.assertRaises(SystemExit) as result:
                self.dispatch(host=host, force_host=False)
            self.assertEqual(result.exception.code, 3)
            launch.assert_not_called()
            self.assertEqual(rd.all_jobs(), [])
            self.assertFalse(self.worker.exists())

    def test_force_named_host_keeps_existing_probe_bypass_semantics(self):
        with patch.object(rd, "probe", side_effect=AssertionError("forced host must bypass probe")) as probe:
            record = self.dispatch(force_host=True)
        self.assertEqual(record["host"], "fixture")
        probe.assert_not_called()

    def clean(self, record, **overrides):
        values = dict(job=record["job"], force=True, delete_branch=True, discard_reports=False, initiator_session=None)
        values.update(overrides)
        rd.cmd_clean(argparse.Namespace(**values), self.cfg)

    def test_missing_includes_list_all_paths_before_host_probe(self):
        errors = io.StringIO()
        with patch.object(rd, "pick_host") as probe, patch.object(rd, "ssh") as ssh, \
             patch.object(native, "request") as rpc, contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            rd.cmd_run(self.args(include=["missing one", "missing two"], force_host=False), self.cfg)
        self.assertIn("missing one", errors.getvalue())
        self.assertIn("missing two", errors.getvalue())
        self.assertIn(str(self.repo), errors.getvalue())
        probe.assert_not_called()
        ssh.assert_not_called()
        rpc.assert_not_called()
        self.assertEqual(rd.all_jobs(), [])

    def test_include_pack_failure_is_local_and_names_error(self):
        (self.repo / "extra.txt").write_text("extra")
        original = subprocess.run
        def fail_tar(args, **kwargs):
            if args[0] == "tar":
                return subprocess.CompletedProcess(args, 1, b"", b"extra.txt: permission denied")
            return original(args, **kwargs)
        errors = io.StringIO()
        with patch.object(subprocess, "run", side_effect=fail_tar), patch.object(rd, "ssh") as ssh, \
             contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            self.dispatch(include=["extra.txt"])
        ssh.assert_not_called()
        self.assertIn("extra.txt: permission denied", errors.getvalue())

    def test_include_uses_selected_repository_root_with_spaces_and_option_names(self):
        for name in ["extra 中文.txt", "-extra.txt"]:
            (self.repo / name).write_text(name)
        record = self.dispatch(include=["extra 中文.txt", "-extra.txt"])
        for name in ["extra 中文.txt", "-extra.txt"]:
            self.assertEqual((self.worker / "wt" / record["job"] / name).read_text(), name)

    def test_wip_preserves_ref_and_sends_staged_unstaged_binary_and_deletions(self):
        for platform in ("posix", "windows"):
            for staged in (False, True):
                with self.subTest(platform=platform, staged=staged):
                    self.cfg.cp.set("host:fixture", "platform", platform)
                    (self.repo / "tracked.txt").write_text(f"edited {platform} {staged}\n")
                    (self.repo / "binary.dat").write_bytes(b"\x00\xff" * 50)
                    (self.repo / "remove.txt").unlink(missing_ok=True)
                    (self.repo / "untracked.txt").write_text("not included")
                    if staged:
                        self.git("add", "-u")
                    before = self.git("status", "--porcelain")
                    record = self.dispatch(wip=True)
                    wt = self.worker / "wt" / record["job"]
                    self.assertEqual(record["base"], self.base)
                    self.assertEqual(native.git(wt, "rev-parse", "HEAD").stdout.strip(), self.base)
                    self.assertEqual((wt / "tracked.txt").read_bytes(), (self.repo / "tracked.txt").read_bytes())
                    self.assertEqual((wt / "binary.dat").read_bytes(), (self.repo / "binary.dat").read_bytes())
                    self.assertFalse((wt / "remove.txt").exists())
                    self.assertFalse((wt / "untracked.txt").exists())
                    self.assertEqual(len(native.git(wt, "diff", "--cached", "--name-only").stdout.splitlines()), 3)
                    self.assertEqual(self.git("status", "--porcelain"), before)

    def test_wip_against_different_ref_includes_head_changes_and_working_tree(self):
        (self.repo / "committed.txt").write_text("after baseline")
        self.git("add", ".")
        self.git("commit", "-qm", "after baseline")
        (self.repo / "tracked.txt").write_text("index version")
        self.git("add", "tracked.txt")
        (self.repo / "tracked.txt").write_text("final worktree version")
        record = self.dispatch(wip=True, ref="baseline")
        wt = self.worker / "wt" / record["job"]
        self.assertEqual(native.git(wt, "rev-parse", "HEAD").stdout.strip(), self.base)
        self.assertEqual((wt / "committed.txt").read_text(), "after baseline")
        self.assertEqual((wt / "tracked.txt").read_text(), "final worktree version")
        self.assertEqual((self.repo / "tracked.txt").read_text(), "final worktree version")
        self.assertIn("index version", self.git("show", ":tracked.txt"))

    def test_wip_staged_addition_rename_and_custom_diff_prefix(self):
        self.git("config", "diff.noprefix", "true")
        (self.repo / "added.txt").write_text("new")
        self.git("add", "added.txt")
        self.git("mv", "tracked.txt", "renamed.txt")
        record = self.dispatch(wip=True)
        wt = self.worker / "wt" / record["job"]
        self.assertEqual((wt / "added.txt").read_text(), "new")
        self.assertEqual((wt / "renamed.txt").read_text(), "base\n")
        self.assertFalse((wt / "tracked.txt").exists())

    def test_failure_before_worktree_creation_can_remove_created_branch(self):
        def fail_worktree(host, script, **kwargs):
            if "worktree add" in script:
                rd.die("injected worktree failure")
            return self.local_shell(host, script, **kwargs)
        with patch.object(rd, "ssh", side_effect=fail_worktree), self.assertRaises(SystemExit):
            self.dispatch(branch="rd/employee_a/before-worktree")
        record = rd.all_jobs()[-1]
        self.assertFalse((self.worker / "wt" / record["job"]).exists())
        self.assertTrue(record["owns_worker_branch"])
        self.clean(record)
        self.assertNotEqual(native.git(self.worker / record["bare"], "show-ref", "--verify", "refs/heads/" + record["branch"], check=False).returncode, 0)

    def test_origin_sync_and_cleanup_use_only_local_bare_fixture(self):
        origin = self.root / "origin.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.repo), str(origin)], check=True)
        self.git("remote", "add", "origin", str(origin))
        self.cfg.cp.set("host:fixture", "sync", "origin")
        for platform in ("posix", "windows"):
            with self.subTest(platform=platform):
                self.cfg.cp.set("host:fixture", "platform", platform)
                self.worker = self.root / ("origin-worker-" + platform) / "users/employee_a"
                self.cfg.cp.set("host:fixture", "workdir", str(self.worker.parent.parent))
                record = self.dispatch(branch="rd/employee_a/origin-" + platform)
                self.assertTrue(record["owns_origin_branch"])
                self.assertEqual(native.git(origin, "rev-parse", record["branch"]).stdout.strip(), self.base)
                # Exercise normal worktree and fetched-commit gates without force.
                rd.save_job(dict(record, handoff_version=None))
                self.clean(record, force=False)
                self.assertNotEqual(native.git(origin, "show-ref", "--verify", "refs/heads/" + record["branch"], check=False).returncode, 0)
                self.assertEqual(native.git(origin, "rev-parse", "baseline").stdout.strip(), self.base)

    def test_empty_wip_stops_before_remote_even_with_untracked_files(self):
        (self.repo / "untracked.txt").write_text("untracked")
        errors = io.StringIO()
        with patch.object(rd, "ssh") as ssh, contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            self.dispatch(wip=True)
        ssh.assert_not_called()
        self.assertIn("--wip", errors.getvalue())
        self.assertIn("没有改动", errors.getvalue())
        self.assertEqual(rd.all_jobs(), [])

    def test_failure_after_worktree_creation_is_registered_and_cleanable(self):
        for platform in ("posix", "windows"):
            with self.subTest(platform=platform):
                self.cfg.cp.set("host:fixture", "platform", platform)
                def lost_ssh(host, script, **kwargs):
                    result = self.local_shell(host, script, **kwargs)
                    if "worktree add" in script:
                        rd.die("injected lost response")
                    return result
                def lost_rpc(host, operation, *args, **kwargs):
                    result = self.local_rpc(host, operation, *args, **kwargs)
                    if operation == "init":
                        raise ValueError("injected lost response")
                    return result
                with patch.object(rd, "ssh", side_effect=lost_ssh), patch.object(native, "request", side_effect=lost_rpc), \
                     self.assertRaises((SystemExit, ValueError)):
                    self.dispatch(branch="rd/employee_a/retry")
                record = rd.all_jobs()[-1]
                self.assertEqual(record["dispatch_state"], "preparation_failed")
                with self.assertRaises(SystemExit) as stopped:
                    rd.cmd_wait(argparse.Namespace(job=record["job"], timeout=1, interval=0.01), self.cfg)
                self.assertEqual(stopped.exception.code, 1)
                wt = self.worker / "wt" / record["job"]
                self.assertTrue(wt.exists())
                self.clean(record)
                self.assertFalse(wt.exists())
                self.assertFalse(Path(rd.job_path(record["job"])).exists())
                self.assertNotEqual(native.git(self.worker / record["bare"], "show-ref", "--verify", "refs/heads/" + record["branch"], check=False).returncode, 0)

    def test_existing_branch_and_other_employee_survive_failed_dispatch_cleanup(self):
        for platform in ("posix", "windows"):
            with self.subTest(platform=platform):
                self.cfg.cp.set("host:fixture", "platform", platform)
                branch = "rd/employee_a/existing-" + platform
                original = self.dispatch(branch=branch)
                other = self.root / "worker/users/employee_b/wt/other/evidence.txt"
                other.parent.mkdir(parents=True, exist_ok=True)
                other.write_text("keep")
                with self.assertRaises((SystemExit, ValueError)):
                    self.dispatch(branch=branch)
                failed = rd.all_jobs()[-1]
                self.clean(failed)
                self.assertEqual(other.read_text(), "keep")
                self.assertTrue((self.worker / "wt" / original["job"]).exists())
                self.assertEqual(native.git(self.worker / original["bare"], "rev-parse", branch).stdout.strip(), self.base)
                with patch.dict(os.environ, {"RD_USER_ID": "employee_b"}), self.assertRaises(SystemExit):
                    self.clean(original)
                self.assertTrue(Path(rd.job_path(original["job"])).exists())

    def reports(self, record):
        reports = self.worker / "jobs" / record["job"] / "reports"
        reports.mkdir(parents=True)
        (reports / "nested").mkdir()
        (reports / "nested/repro.py").write_bytes(b"print('repro')\n\x00\xff")
        (reports / "summary.md").write_text("复现报告")
        return reports

    def test_clean_backs_up_entire_reports_tree_before_removing_remote(self):
        for platform in ("posix", "windows"):
            with self.subTest(platform=platform):
                self.cfg.cp.set("host:fixture", "platform", platform)
                record = self.dispatch()
                reports = self.reports(record)
                expected = (reports / "nested/repro.py").read_bytes()
                self.clean(record)
                backup = self.root / "saved reports" / record["job"]
                self.assertEqual((backup / "nested/repro.py").read_bytes(), expected)
                self.assertEqual((backup / "summary.md").read_text(), "复现报告")
                self.assertFalse(reports.parent.exists())

    def test_failed_backup_keeps_remote_and_record_even_with_force(self):
        record = self.dispatch()
        reports = self.reports(record)
        with patch.object(rd, "backup_reports", side_effect=OSError("disk full")), self.assertRaises(SystemExit):
            self.clean(record)
        self.assertTrue(reports.exists())
        self.assertTrue((self.worker / "wt" / record["job"]).exists())
        self.assertTrue(Path(rd.job_path(record["job"])).exists())
        with patch.object(rd, "backup_reports") as backup:
            self.clean(record, discard_reports=True)
        backup.assert_not_called()
        self.assertFalse(reports.parent.exists())

    def test_reports_symlink_cannot_escape_or_trigger_remote_deletion(self):
        record = self.dispatch()
        reports = self.reports(record)
        outside = self.root / "private.txt"
        outside.write_text("keep")
        (reports / "link").symlink_to(outside)
        with self.assertRaises(SystemExit):
            self.clean(record)
        self.assertTrue(reports.exists())
        self.assertEqual(outside.read_text(), "keep")
        self.assertFalse((self.root / "saved reports" / record["job"]).exists())

    def test_repeated_backup_keeps_previous_copy(self):
        record = self.dispatch()
        reports = self.reports(record)
        first = Path(rd.backup_reports(rd.job_host(self.cfg, record), record))
        (reports / "summary.md").write_text("第二版")
        second = Path(rd.backup_reports(rd.job_host(self.cfg, record), record))
        self.assertNotEqual(first, second)
        self.assertEqual((first / "summary.md").read_text(), "复现报告")
        self.assertEqual((second / "summary.md").read_text(), "第二版")

    def test_launching_without_pid_cannot_be_cleaned_as_failed_preparation(self):
        record = self.dispatch()
        record["dispatch_state"] = "launching"
        rd.save_job(record)
        (self.worker / "jobs" / record["job"] / "exit_code").unlink()
        with self.assertRaises(SystemExit):
            self.clean(record)
        self.assertTrue((self.worker / "wt" / record["job"]).exists())


if __name__ == "__main__":
    unittest.main()
