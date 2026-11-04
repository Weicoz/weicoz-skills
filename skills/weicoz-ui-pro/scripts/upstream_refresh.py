#!/usr/bin/env python3
"""使用 weicoz-ui-pro 时自动检查并同步上游 oil-ui-pro。

流程：本机没有上游 -> 静默退出，不联网；有上游 -> 节流后读公开版本列表，
上游落后就更新上游目录，上游比本 Skill 新就执行 sync_upstream 并在本地提交（不推送）。
无更新、网络失败、任何异常都不输出、不中断任务（退出码恒为 0）。

环境变量：
  WEICOZ_UI_PRO_NO_REFRESH=1        关闭本脚本
  WEICOZ_UI_PRO_VERSIONS_URL        覆盖公开版本列表地址（默认官方公开地址）
  OIL_UI_PRO_UPSTREAM               指定上游目录（同 sync_upstream.py）
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import sync_upstream  # 直接运行脚本时 scripts/ 在 sys.path 中
except ImportError:  # pragma: no cover - 以包方式导入（测试）
    from scripts import sync_upstream

VERSIONS_URL = "https://ui.oiloil.org/api/store/versions"
CHECK_INTERVAL = 10 * 60
RETRY_AFTER_FAILURE = 3600
UPDATE_RETRY_AFTER_FAILURE = 6 * 3600
NOTICE_INTERVAL = 24 * 3600
FETCH_TIMEOUT = 2
CLONE_TIMEOUT = 90
UPDATE_TIMEOUT = 180
LOCK_STALE = 15 * 60
SEMVER = re.compile(r"\d+\.\d+\.\d+")
# 上游脚本读取失败时的保底白名单（正常情况从上游 check_update.py 解析）
DEFAULT_ENV_KEYS = {
    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_STATE_HOME",
    "SYSTEMROOT", "WINDIR", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_MESSAGES",
    "OIL_API", "OIL_TOKEN",
}


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "weicoz-ui-pro"


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "weicoz-ui-pro"


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def read_skill_info(skill_md: Path) -> tuple[str, str] | None:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    name = re.search(r'^name:\s*"?([\w-]+)"?\s*$', text, re.MULTILINE)
    version = sync_upstream.read_version(text)
    if not name or not version:
        return None
    return name.group(1), version


def fetch_latest(name: str) -> str | None:
    url = os.environ.get("WEICOZ_UI_PRO_VERSIONS_URL") or VERSIONS_URL
    req = urllib.request.Request(url, headers={"User-Agent": "weicoz-ui-pro-refresh"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        entry = json.load(resp).get("skills", {}).get(name)
    latest = str(entry.get("latest", "")) if isinstance(entry, dict) else ""
    return latest if SEMVER.fullmatch(latest) else None


def parse_upstream_constants(upstream: Path) -> tuple[str | None, set[str]]:
    """从上游 check_update.py 解析固定 CLI 常量与环境白名单，不硬编码提交号。"""
    cli, keys = None, set(DEFAULT_ENV_KEYS)
    try:
        tree = ast.parse((upstream / "scripts" / "check_update.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return cli, keys
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if node.targets[0].id == "CLI" and isinstance(value, str):
            cli = value
        elif node.targets[0].id == "UPDATE_ENV_KEYS" and isinstance(value, (set, list, tuple)):
            keys = {str(k) for k in value}
    return cli, keys


def clean_env(keys: set[str]) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in keys}
    env["CI"] = "1"
    return env


def run(cmd: list[str], env: dict[str, str], timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=timeout, check=False, encoding="utf-8", errors="replace")


def upstream_version(upstream: Path) -> str | None:
    info = read_skill_info(upstream / "SKILL.md")
    return info[1] if info else None


def update_via_upstream_script(upstream: Path, env: dict[str, str]) -> None:
    script = upstream / "scripts" / "check_update.py"
    if script.is_file():
        run([sys.executable, str(script), "--update"], env, UPDATE_TIMEOUT)


def update_via_cli_clone(upstream: Path, name: str, cli: str, env: dict[str, str]) -> bool:
    """npx 取不到 GitHub 源时：克隆固定提交到缓存目录，用 node 直接运行 update。"""
    m = re.fullmatch(r"github:([\w.-]+/[\w.-]+)#([0-9a-f]{40})", cli)
    node, git = shutil.which("node", path=env.get("PATH")), shutil.which("git", path=env.get("PATH"))
    if not (m and node and git):
        return False
    repo, sha = m.groups()
    target = cache_dir() / f"cli-{sha[:12]}"

    def head_ok() -> bool:
        r = run([git, "-C", str(target), "rev-parse", "HEAD"], env, 20)
        return r.returncode == 0 and r.stdout.strip() == sha

    if not (target.is_dir() and head_ok()):
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if run([git, "clone", "--quiet", f"https://github.com/{repo}.git", str(target)], env, CLONE_TIMEOUT).returncode != 0:
            return False
        if run([git, "-C", str(target), "checkout", "--quiet", sha], env, 30).returncode != 0 or not head_ok():
            shutil.rmtree(target, ignore_errors=True)
            return False
    r = run([node, "bin/oil.js", "update", name, "--path", str(upstream), "--json"], env, UPDATE_TIMEOUT, cwd=target)
    for line in reversed((r.stdout + "\n" + r.stderr).splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return bool(data.get("ok")) and r.returncode == 0
    return False


def update_upstream(upstream: Path, name: str, latest: str) -> bool:
    """更新上游目录；返回上游版本是否已达到 latest。只作用于上游目录。"""
    cli, keys = parse_upstream_constants(upstream)
    env = clean_env(keys)
    try:
        update_via_upstream_script(upstream, env)
    except Exception:
        pass
    cur = upstream_version(upstream)
    if cur and parse_version(cur) >= parse_version(latest):
        return True
    if cli:
        try:
            update_via_cli_clone(upstream, name, cli, env)
        except Exception:
            pass
    cur = upstream_version(upstream)
    return bool(cur and parse_version(cur) >= parse_version(latest))


def git(skill_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=skill_dir, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=60, check=False, encoding="utf-8", errors="replace")


def is_git_repo(skill_dir: Path) -> bool:
    try:
        return git(skill_dir, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def tree_dirty(skill_dir: Path) -> bool:
    return bool(git(skill_dir, "status", "--porcelain", "--", ".").stdout.strip())


def commit_sync(skill_dir: Path, old: str, new: str) -> str | None:
    if git(skill_dir, "add", "-A", "--", ".").returncode != 0:
        return None
    if not git(skill_dir, "diff", "--cached", "--name-only", "--", ".").stdout.strip():
        return ""
    msg = (f"chore(weicoz-ui-pro): 同步上游 oil-ui-pro {old} → {new}\n\n"
           "由 scripts/upstream_refresh.py 自动同步并提交，未推送。\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    if git(skill_dir, "commit", "-q", "-m", msg, "--", ".").returncode != 0:
        return None
    return git(skill_dir, "rev-parse", "--short", "HEAD").stdout.strip()


class Lock:
    def __init__(self, path: Path):
        self.path, self.held = path, False

    def __enter__(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and time.time() - self.path.stat().st_mtime > LOCK_STALE:
                shutil.rmtree(self.path, ignore_errors=True)
            self.path.mkdir()
            self.held = True
        except OSError:
            self.held = False
        return self

    def __exit__(self, *exc):
        if self.held:
            shutil.rmtree(self.path, ignore_errors=True)


def notify_once(state: dict, key: str, now: float) -> bool:
    notes = state.setdefault("notices", {})
    if now - float(notes.get(key, 0)) < NOTICE_INTERVAL:
        return False
    notes[key] = now
    return True


def refresh(skill_dir: Path | None = None, now: float | None = None) -> str | None:
    """返回要打印的一行提示或 None。"""
    skill_dir = skill_dir or sync_upstream.SKILL_DIR
    now = time.time() if now is None else now
    if os.environ.get("WEICOZ_UI_PRO_NO_REFRESH"):
        return None
    upstream = sync_upstream.find_default_upstream()
    if upstream is None:
        return None
    up_info = read_skill_info(upstream / "SKILL.md")
    if not up_info:
        return None
    name, up_ver = up_info

    sdir = state_dir()
    with Lock(sdir / "refresh.lock") as lock:
        if not lock.held:
            return None
        state_path = sdir / "refresh.json"
        state = load_json(state_path)

        # 1. 节流联网查最新版
        if now - float(state.get("checked_at", 0)) >= CHECK_INTERVAL and \
                now - float(state.get("fetch_failed_at", 0)) >= RETRY_AFTER_FAILURE:
            try:
                latest = fetch_latest(name)
            except Exception:
                latest = None
            if latest:
                state.update(latest=latest, checked_at=now)
                state.pop("fetch_failed_at", None)
            else:
                state["fetch_failed_at"] = now
            save_json(state_path, state)

        # 2. 上游落后则更新上游目录
        latest = state.get("latest")
        if isinstance(latest, str) and SEMVER.fullmatch(latest) and parse_version(up_ver) < parse_version(latest):
            same = state.get("update_failed_latest") == latest
            if not (same and now - float(state.get("update_failed_at", 0)) < UPDATE_RETRY_AFTER_FAILURE):
                try:
                    ok = update_upstream(upstream, name, latest)
                except Exception:
                    ok = False
                if ok:
                    state.pop("update_failed_at", None)
                    state.pop("update_failed_latest", None)
                else:
                    state.update(update_failed_at=now, update_failed_latest=latest)
                save_json(state_path, state)
            up_ver = upstream_version(upstream) or up_ver

        # 3. 上游比本 Skill 新则同步
        local = read_skill_info(skill_dir / "SKILL.md")
        if not local or not SEMVER.fullmatch(up_ver) or parse_version(up_ver) <= parse_version(local[1]):
            return None
        old = local[1]
        repo = is_git_repo(skill_dir)
        if repo and tree_dirty(skill_dir):
            msg = (f"weicoz-ui-pro 上游已有新版 {old}→{up_ver}，但本 Skill 目录有未提交改动，未自动同步；"
                   "请先提交或清理，再运行 python3 scripts/sync_upstream.py --apply")
            if notify_once(state, f"dirty-{up_ver}", now):
                save_json(state_path, state)
                return msg
            return None
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = sync_upstream.sync(upstream, apply=True, skill_dir=skill_dir)
        if rc != 0:
            return None
        if not repo:
            return f"weicoz-ui-pro 已同步上游 {old}→{up_ver}（目录不是 git 仓库，未提交），请重新读取 SKILL.md"
        sha = commit_sync(skill_dir, old, up_ver)
        if sha is None:
            return f"weicoz-ui-pro 已同步上游 {old}→{up_ver}，但提交失败，请手动提交并推送主仓库后重新读取 SKILL.md"
        if not sha:
            return None
        return f"weicoz-ui-pro 已同步上游 {old}→{up_ver} 并提交 {sha}，请推送主仓库后重新读取 SKILL.md"


def main() -> int:
    try:
        for stream in (sys.stdout,):
            if hasattr(stream, "reconfigure") and not stream.isatty():
                stream.reconfigure(encoding="utf-8")
        msg = refresh()
        if msg:
            print(msg)
    except BaseException:  # 任何异常都不得中断任务
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
