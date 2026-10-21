#!/usr/bin/env python3
"""临时仓库与替身命令回归；不调用真实 Codex 或安装依赖。"""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


class LocalDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dispatch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.capture = self.root / "capture.jsonl"
        self.env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                        CAPTURE=str(self.capture))
        self.env.pop("RD_MAX_LOAD_PER_CORE", None)
        self.repo = self.make_repo("repo with spaces")
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("本票提示词：$HOME `literal` {{CONTEXT}}\n")
        self.executable("codex", '''#!/usr/bin/env python3
import json, os, pathlib, signal, subprocess, sys, time
args = sys.argv[1:]
with open(os.environ["CAPTURE"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
if os.environ.get("SPAWN_CHILD"):
    child = subprocess.Popen(["sleep", "60"])
    def reap_child(signum, frame):
        child.wait(timeout=2)
        sys.exit(143)
    signal.signal(signal.SIGTERM, reap_child)
    pathlib.Path(os.environ["SPAWN_CHILD"]).write_text(str(child.pid))
if os.environ.get("NO_HEADER"):
    time.sleep(60)
print("workdir: " + args[args.index("-C") + 1], flush=True)
print("model: mock-model", flush=True)
print("sandbox: workspace-write (network access enabled)", flush=True)
print("session id: mock-session", flush=True)
pathlib.Path(args[args.index("-o") + 1]).write_text("mock result")
time.sleep(float(os.environ.get("MOCK_DELAY", "0")))
sys.exit(int(os.environ.get("MOCK_EXIT", "0")))
''')

    def executable(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)
        return path

    def run_command(self, args, **kwargs):
        return subprocess.run([str(arg) for arg in args], env=self.env, text=True,
                              capture_output=True, timeout=15, **kwargs)

    def make_repo(self, name, files=None):
        path = self.root / name
        path.mkdir()
        for relative, content in (files or {"sample.txt": "baseline"}).items():
            (path / relative).write_text(content)
        for args in (["init", "-b", "main"], ["add", "."],
                     ["-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                      "-c", "core.hooksPath=/dev/null", "commit", "-m", "baseline"]):
            result = self.run_command(["git", "-C", path, *args])
            self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def prepare(self, *repos, ticket="T01", branch="ticket/T01"):
        args = ["bash", SCRIPTS / "prepare-worktrees.sh", "--branch", branch,
                "--base", "main", "--root", self.root / "worktrees", "--ticket", ticket,
                "--log-dir", self.root / "logs"]
        for name, path in repos or [("app", self.repo)]:
            args += ["--repo", f"{name}={path}"]
        return self.run_command(args)

    def launch_args(self, *extra, workdir=None, name="T01"):
        return ["bash", SCRIPTS / "launch-local.sh", "--name", name, "--prompt", self.prompt,
                "--workdir", workdir or self.repo, "--out", self.root / "output with spaces", *extra]

    def captured(self):
        return [json.loads(line) for line in self.capture.read_text().splitlines()]

    def mock_load(self):
        self.executable("uname", "#!/bin/sh\nprintf 'Darwin\\n'\n")
        self.executable("sysctl", '#!/bin/sh\ncase "$2" in hw.ncpu) echo 4 ;; vm.loadavg) echo "{ 8.0 7.0 6.0 }" ;; esac\n')

    def stop_process(self, process):
        if process.poll() is None:
            process.terminate()
        return process.communicate(timeout=5)

    def test_prepare_and_existing_targets(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        worktree = self.root / "worktrees/T01-app"
        self.assertEqual((worktree / "sample.txt").read_text(), "baseline")
        self.assertIn("跳过", result.stdout)
        branch = self.run_command(["git", "-C", worktree, "branch", "--show-current"])
        self.assertEqual(branch.stdout.strip(), "ticket/T01")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("目标目录已存在", result.stderr)
        result = self.prepare(ticket="another")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("票据分支已存在", result.stderr)
        self.assertFalse((self.root / "worktrees/another-app").exists())

    def test_install_commands_and_failure_summary(self):
        for manager in ("pnpm", "npm", "uv"):
            self.executable(manager, '''#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ["CAPTURE"], "a") as stream:
    stream.write(json.dumps([pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
print("mock install")
sys.exit(9 if pathlib.Path(sys.argv[0]).name == os.environ.get("FAIL_MANAGER") else 0)
''')
        pnpm = self.make_repo("pnpm", {"pnpm-lock.yaml": "", "package-lock.json": "", "uv.lock": ""})
        npm = self.make_repo("npm", {"package-lock.json": ""})
        uv = self.make_repo("uv", {"uv.lock": ""})
        self.env["FAIL_MANAGER"] = "npm"
        result = self.prepare(("web", pnpm), ("api", npm), ("tool", uv))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.captured(), [["pnpm", "install", "--frozen-lockfile"],
                                          ["uv", "sync", "--frozen"], ["npm", "ci"],
                                          ["uv", "sync", "--frozen"]])
        self.assertEqual(result.stdout.count("worktree="), 3)
        self.assertIn("npm exit=9", result.stdout)
        self.assertIn("mock install", (self.root / "logs/install-T01-api.txt").read_text())

    def test_multi_repo_preflight_is_non_destructive(self):
        other = self.make_repo("other")
        self.run_command(["git", "-C", other, "branch", "ticket/T01"])
        result = self.prepare(("app", self.repo), ("other", other))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "worktrees").exists())
        self.assertNotEqual(self.run_command(["git", "-C", self.repo, "show-ref", "--verify",
                                             "refs/heads/ticket/T01"]).returncode, 0)

    def test_render_and_missing_keys(self):
        output = self.root / "rendered.md"
        extra = self.root / "extra.md"
        extra.write_text("保留多行\n保留 {{TICKET}} 与 $HOME\n")
        command = ["python3", SCRIPTS / "render-prompt.py", "--template",
                   SKILL / "templates/ticket-prompt.md", "--out", output]
        result = self.run_command(command)
        self.assertNotEqual(result.returncode, 0)
        for key in ("TICKET", "WORKDIRS", "CONTEXT", "EXTRA", "CHECKS", "IMPLEMENT_SKILL"):
            self.assertIn(key, result.stderr)
        self.assertFalse(output.exists())
        for key, value in {"TICKET": "T01", "WORKDIRS": "app=repo; api=other",
                           "CONTEXT": "spec.md", "CHECKS": "build 由编排方运行",
                           "IMPLEMENT_SKILL": str(SKILL / "SKILL.md")}.items():
            command += ["--set", f"{key}={value}"]
        command += ["--set-file", f"EXTRA={extra}"]
        result = self.run_command(command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(extra.read_text(), output.read_text())
        self.assertIn("实现票据：T01", output.read_text())
        result = self.run_command(command + ["--set", "TICKET=duplicate"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重复", result.stderr)

    def test_launch_add_dirs_network_arguments_and_header(self):
        self.assertEqual(self.prepare().returncode, 0)
        second = self.make_repo("second repo")
        plain = self.root / "context"
        plain.mkdir()
        worktree = self.root / "worktrees/T01-app"
        result = self.run_command(self.launch_args("--no-wait-load", "--add-dir", second,
                                  "--add-dir", plain, "--add-dir", self.repo,
                                  "--", "--model", "model with spaces", "-c", "x=y", workdir=worktree))
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.captured()[0]
        self.assertEqual(args[:5], ["exec", "-s", "workspace-write", "-C", str(worktree.resolve())])
        dirs = [args[i + 1] for i, arg in enumerate(args) if arg == "--add-dir"]
        expected = [second, plain, self.repo]
        self.assertCountEqual(dirs, [str(path.resolve()) for path in expected])
        self.assertIn("sandbox_workspace_write.network_access=true", args)
        self.assertEqual(args[-5:], ["--model", "model with spaces", "-c", "x=y",
                                    self.prompt.read_text().rstrip("\n")])
        for line in ("workdir:", "model:", "sandbox:", "session id:", "exit=0 result="):
            self.assertIn(line, result.stdout)
        self.assertEqual((self.root / "output with spaces/result-T01.md").read_text(), "mock result")
        self.assertNotEqual(self.run_command(self.launch_args("--no-wait-load")).returncode, 0)

    def test_offline_and_exit_code(self):
        self.env["MOCK_EXIT"] = "7"
        result = self.run_command(self.launch_args("--no-wait-load", "--offline"))
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("sandbox_workspace_write.network_access=false", self.captured()[0])
        self.assertIn("exit=7", result.stdout)

    def test_load_admission_and_environment_precedence(self):
        self.mock_load()
        self.env["RD_MAX_LOAD_PER_CORE"] = "0.000001"
        result = self.run_command(self.launch_args("--max-load-per-core", "999999"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("负载 8.0 ÷ 4 核 = 每核 2.000，阈值 999999", result.stdout)

    def test_native_load_probe(self):
        if os.uname().sysname == "Darwin":
            for key in ("hw.ncpu", "vm.loadavg"):
                probe = self.run_command(["sysctl", "-n", key])
                if probe.returncode and "Operation not permitted" in probe.stderr:
                    self.skipTest("宿主沙箱禁止 sysctl；负载逻辑由替身覆盖")
                self.assertEqual(probe.returncode, 0, probe.stderr)
        result = self.run_command(self.launch_args("--max-load-per-core", "999999"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("负载", result.stdout)

    def test_low_load_limit_waits_without_launch(self):
        self.mock_load()
        self.env["RD_MAX_LOAD_PER_CORE"] = "0.000001"
        process = subprocess.Popen([str(arg) for arg in self.launch_args("--poll-seconds", "0.05")],
                                   env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                process.communicate(timeout=1.5)
        finally:
            stdout, stderr = self.stop_process(process)
        self.assertGreaterEqual(stdout.count("阈值 0.000001"), 2, stderr)
        self.assertFalse(self.capture.exists())

    def test_header_timeout_and_signal_reap_children(self):
        for mode in ("timeout", "signal"):
            with self.subTest(mode=mode):
                pid_file = self.root / f"{mode}.pid"
                self.env.update(NO_HEADER="1", SPAWN_CHILD=str(pid_file))
                if mode == "timeout":
                    count_file = self.root / "clock-count"
                    self.executable("date", f'''#!/usr/bin/env python3
from pathlib import Path
p = Path({str(count_file)!r})
n = int(p.read_text()) + 1 if p.exists() else 0
p.write_text(str(n))
print(n * 301)
''')
                else:
                    (self.bin / "date").unlink()
                process = subprocess.Popen([str(arg) for arg in self.launch_args("--no-wait-load", name=mode)],
                                           env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    if mode == "signal":
                        deadline = time.monotonic() + 5
                        while not pid_file.exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        self.assertTrue(pid_file.exists())
                        process.send_signal(signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 1 if mode == "timeout" else 143, stdout + stderr)
                    if mode == "timeout":
                        self.assertIn("300秒", stderr)
                    if pid_file.exists():
                        pid = int(pid_file.read_text())
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                finally:
                    self.stop_process(process)

    def test_human_errors(self):
        for script in ("launch-local.sh", "prepare-worktrees.sh"):
            result = self.run_command(["bash", SCRIPTS / script])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("错误", result.stderr)
        limited = self.root / "limited"
        limited.mkdir()
        (limited / "awk").symlink_to(shutil.which("awk"))
        self.env["PATH"] = str(limited)
        result = self.run_command(["/bin/bash", *self.launch_args("--no-wait-load")[1:]])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未找到 codex", result.stderr)


if __name__ == "__main__":
    unittest.main()
