#!/usr/bin/env python3
"""远端 TTS 工作站的运维入口：上传并执行 PowerShell、后台长任务看进度、部署服务端代码、重启服务。

用法：
  zero_remote.py run <名称> <脚本.ps1>      后台执行（断开 SSH 不中断），输出写远端日志，立即返回
  zero_remote.py tail <名称> [-n 20]        看该任务日志最后几行
  zero_remote.py wait <名称> [--timeout 1800]  等任务结束，打印日志尾部；退出码 = 远端退出码
  zero_remote.py exec <脚本.ps1> [--timeout 120]  同步执行短脚本，打印输出
  zero_remote.py restart page|qwen          重启试听页服务（9881）或合成服务（9880）
  zero_remote.py deploy <文件>... [--restart page,qwen]  部署 server/ 下的文件到远端服务目录（旧文件留 .bak），可顺带重启

环境变量：
  ZERO_TTS_SSH_HOST     ~/.ssh/config 里的主机别名，逗号分隔多个，按顺序尝试（必需）
  ZERO_TTS_REMOTE_HOME  远端服务根目录，默认 D:\\TTS_Services
  ZERO_TTS_PAGE_TASK    试听页服务的计划任务名，默认 tts_voices_page
  ZERO_TTS_START_TASK   合成服务的计划任务名，默认 tts_qwen
远端布局：脚本放 <根>\\ops\\，日志放 <根>\\logs\\ops\\<名称>.log，任务结束时日志末行写 __DONE__ <退出码>。
退出码：0 成功；1 远端失败或超时；2 参数或连接错误。
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = os.environ.get("ZERO_TTS_REMOTE_HOME", r"D:\TTS_Services")
SSH_OPTS = ["-o", "ConnectTimeout=8", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=15"]
DONE = "__DONE__"
SERVICES = {
    "page": ("voices_server.py", os.environ.get("ZERO_TTS_PAGE_TASK", "tts_voices_page")),
    "qwen": ("qwen_server.py", os.environ.get("ZERO_TTS_START_TASK", "tts_qwen")),
}


class Err(Exception):
    pass


def hosts():
    hs = [h.strip() for h in os.environ.get("ZERO_TTS_SSH_HOST", "").split(",") if h.strip()]
    if not hs:
        raise Err("未设置 ZERO_TTS_SSH_HOST（~/.ssh/config 里的主机别名，可逗号分隔多个）。")
    return hs


_host = None


def host():
    """第一个能连上的主机，本进程内缓存。"""
    global _host
    if _host:
        return _host
    for h in hosts():
        try:
            r = subprocess.run(["ssh", *SSH_OPTS, h, "echo ok"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and "ok" in r.stdout:
                _host = h
                return h
        except subprocess.TimeoutExpired:
            pass
        print(f"提示：{h} 连不上，试下一个。", file=sys.stderr)
    raise Err("所有主机都连不上：" + ", ".join(hosts()))


def win(*parts):
    return "\\".join([HOME.rstrip("\\"), *parts])


def scp_to(local, remote_win):
    r = subprocess.run(["scp", *SSH_OPTS, "-q", str(local), f"{host()}:{remote_win.replace(chr(92), '/')}"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise Err(f"上传失败 {local}：{r.stderr.strip()[:200]}")


UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "


def decode(b):
    """远端控制台可能仍按 GBK 输出：先按 UTF-8 解，失败再按 GBK。"""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("gbk", errors="replace")


def ps(command, timeout=120):
    """在远端执行一段 PowerShell，返回 (退出码, 输出)。"""
    r = subprocess.run(["ssh", *SSH_OPTS, host(), f'pwsh -NoProfile -Command "{UTF8}{command}"'],
                       capture_output=True, timeout=timeout)
    return r.returncode, decode(r.stdout + r.stderr).replace("\r", "")


def ps_file(local_ps1, timeout=120):
    remote = win("ops", "exec_" + Path(local_ps1).name)
    ps(f"New-Item -ItemType Directory -Force '{win('ops')}' | Out-Null")
    scp_to(local_ps1, remote)
    r = subprocess.run(["ssh", *SSH_OPTS, host(), f'pwsh -NoProfile -Command "{UTF8}& {remote}"'],
                       capture_output=True, timeout=timeout)
    return r.returncode, decode(r.stdout + r.stderr).replace("\r", "")


def cmd_run(a):
    name, script = a.name, Path(a.script)
    if not script.is_file():
        raise Err(f"脚本不存在：{script}")
    log = win("logs", "ops", f"{name}.log")
    target = win("ops", f"{name}.ps1")
    wrapper = win("ops", f"{name}.run.ps1")
    ps(f"New-Item -ItemType Directory -Force '{win('ops')}','{win('logs', 'ops')}' | Out-Null; "
       f"Remove-Item -Force -ErrorAction SilentlyContinue '{log}'")
    scp_to(script, target)
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(f"$code = 0\ntry {{ & '{target}' *>> '{log}'; if ($LASTEXITCODE) {{ $code = $LASTEXITCODE }} }}\n"
                f"catch {{ $_ | Out-String | Add-Content '{log}'; $code = 1 }}\n"
                f"Add-Content '{log}' \"{DONE} $code\"\n")
        tmp = f.name
    try:
        scp_to(tmp, wrapper)
    finally:
        os.unlink(tmp)
    # 用 WMI 建进程：不属于 SSH 会话，断开后继续跑
    code, out = ps(f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
                   f"@{{CommandLine='pwsh -NoProfile -File {wrapper}'}}; $r.ReturnValue")
    if code != 0 or out.strip().splitlines()[-1:] != ["0"]:
        raise Err(f"远端启动失败：{out.strip()[:200]}")
    print(f"已在 {host()} 后台启动「{name}」，日志 {log}。看进度：zero_remote.py tail {name}；等结束：zero_remote.py wait {name}")


def read_log(name, n):
    log = win("logs", "ops", f"{name}.log")
    code, out = ps(f"if (Test-Path '{log}') {{ Get-Content '{log}' -Tail {n} -Encoding utf8 }} else {{ '__NOLOG__' }}")
    if code != 0:
        raise Err(out.strip()[:200])
    return out.rstrip("\n").splitlines()


def cmd_tail(a):
    lines = read_log(a.name, a.n)
    print("\n".join(lines) if lines != ["__NOLOG__"] else f"还没有「{a.name}」的日志。")


def cmd_wait(a):
    t0 = time.time()
    while True:
        lines = read_log(a.name, 1)
        if lines and lines[-1].startswith(DONE):
            print("\n".join(read_log(a.name, a.n)))
            return int(lines[-1].split()[-1] or 0)
        if time.time() - t0 > a.timeout:
            print("\n".join(read_log(a.name, a.n)))
            print(f"等待超时（{a.timeout} 秒），任务仍在远端运行。", file=sys.stderr)
            return 1
        time.sleep(a.interval)


def cmd_exec(a):
    code, out = ps_file(a.script, a.timeout)
    print(out.rstrip())
    return 0 if code == 0 else 1


def restart(which):
    proc, task = SERVICES[which]
    code, out = ps(f"$p = Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | "
                   f"? {{ $_.CommandLine -like '*{proc}*' }}; $p | % {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}; "
                   f"schtasks /run /tn {task} | Out-Null; 'stopped ' + @($p).Count")
    if code != 0:
        raise Err(f"重启 {which} 失败：{out.strip()[:200]}")
    print(f"已重启 {which}（{out.strip().splitlines()[-1]}，计划任务 {task}）。")


def cmd_restart(a):
    restart(a.which)


def cmd_deploy(a):
    server = win("qwen3tts", "server")
    for f in map(Path, a.files):
        if not f.is_file():
            raise Err(f"文件不存在：{f}")
        dest = server + "\\" + f.name
        ps(f"if (Test-Path '{dest}') {{ Copy-Item '{dest}' '{dest}.bak' -Force }}")
        scp_to(f, dest)
        print(f"已部署 {f.name} → {dest}（旧文件 {f.name}.bak）")
    for w in [x for x in (a.restart or "").split(",") if x]:
        if w not in SERVICES:
            raise Err(f"--restart 只能是 page、qwen：{w}")
        restart(w)


def main(argv=None):
    ap = argparse.ArgumentParser(description="远端 TTS 工作站运维")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("name"); r.add_argument("script")
    t = sub.add_parser("tail"); t.add_argument("name"); t.add_argument("-n", type=int, default=20)
    w = sub.add_parser("wait"); w.add_argument("name"); w.add_argument("--timeout", type=int, default=1800)
    w.add_argument("--interval", type=int, default=10); w.add_argument("-n", type=int, default=20)
    e = sub.add_parser("exec"); e.add_argument("script"); e.add_argument("--timeout", type=int, default=120)
    s = sub.add_parser("restart"); s.add_argument("which", choices=list(SERVICES))
    d = sub.add_parser("deploy"); d.add_argument("files", nargs="+"); d.add_argument("--restart")
    a = ap.parse_args(argv)
    try:
        rc = {"run": cmd_run, "tail": cmd_tail, "wait": cmd_wait, "exec": cmd_exec,
              "restart": cmd_restart, "deploy": cmd_deploy}[a.cmd](a)
        return rc or 0
    except Err as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("错误：远端命令超时（连接不稳时换 ZERO_TTS_SSH_HOST 里的下一个主机重试）。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
