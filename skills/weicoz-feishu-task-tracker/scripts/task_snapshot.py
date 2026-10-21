#!/usr/bin/env python3
"""飞书任务盘点：只读。输出逾期 / 临期 / 停滞 / 已完成四类，供催办与汇报使用。

用法：
  python3 scripts/task_snapshot.py                # 文本表格
  python3 scripts/task_snapshot.py --json         # JSON
  python3 scripts/task_snapshot.py --now 2026-10-21T14:30:00   # 指定"现在"

配置来源（按优先级）：
  1. $WEICOZ_TASK_TRACKER_CONFIG
  2. ~/.config/weicoz-feishu-task-tracker/config.yaml

依赖：lark-cli 已登录；ruby（读 YAML，python3 无 yaml 模块时兜底）。
只读：本脚本不写任何飞书数据。
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
DEFAULT_CONFIG = os.path.expanduser("~/.config/weicoz-feishu-task-tracker/config.yaml")


def die(msg):
    sys.stderr.write("错误：" + msg + "\n")
    sys.exit(2)


def config_path():
    return os.environ.get("WEICOZ_TASK_TRACKER_CONFIG") or DEFAULT_CONFIG


def load_config(path):
    if not os.path.isfile(path):
        die(
            "未找到配置 " + path + "\n"
            "  请先建配置：\n"
            "    mkdir -p ~/.config/weicoz-feishu-task-tracker\n"
            "    cp config.example.yaml ~/.config/weicoz-feishu-task-tracker/config.yaml\n"
            "    chmod 600 ~/.config/weicoz-feishu-task-tracker/config.yaml\n"
            "  或用 export WEICOZ_TASK_TRACKER_CONFIG=/path/to/config.yaml 指过去。\n"
            "  取值方式见 references/field-discovery.md。"
        )
    if not shutil.which("ruby"):
        die("读 YAML 需要 ruby（本机 python3 无 yaml 模块），未找到 ruby。")
    out = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e",
         "puts JSON.generate(YAML.load_file(ARGV[0]) || {})", path],
        capture_output=True, text=True)
    if out.returncode != 0:
        die("配置解析失败：" + out.stderr.strip())
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as e:
        die("配置不是合法 YAML/JSON：" + str(e))


def lark(args):
    if not shutil.which("lark-cli"):
        die("未找到 lark-cli，请先安装并登录（lark-cli auth status）。")
    p = subprocess.run(["lark-cli"] + args, capture_output=True, text=True)
    if p.returncode != 0:
        die("lark-cli 调用失败：" + (p.stderr or p.stdout).strip()[:400])
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        die("lark-cli 返回非 JSON：" + p.stdout[:400])


def ms_to_dt(ms):
    try:
        v = int(ms)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return datetime.fromtimestamp(v / 1000, TZ)


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def parse_now(s):
    if not s:
        return datetime.now(TZ)
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f).replace(tzinfo=TZ)
        except ValueError:
            continue
    die("--now 格式无法识别：" + s)


def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    now = parse_now(argv[argv.index("--now") + 1]) if "--now" in argv else datetime.now(TZ)

    cfg = load_config(config_path())
    guid = (cfg.get("tasklist") or {}).get("guid")
    if not guid or "<" in str(guid):
        die("配置里 tasklist.guid 未填真实值。")
    members = cfg.get("members") or {}
    id2name = {v: k for k, v in members.items()}
    followers_default = (cfg.get("followers") or {}).get("default") or []
    remind = cfg.get("reminder") or {}
    due_soon_hours = int(remind.get("due_soon_hours") or 24)
    stale_days = int(remind.get("stale_days") or 3)

    data = lark(["task", "tasklists", "tasks", "--tasklist-guid", guid,
                 "--as", "user", "--page-all", "--format", "json"])
    items = (data.get("data") or {}).get("items") or []

    rows = []
    for t in items:
        tg = t.get("guid")
        detail = lark(["task", "tasks", "get", "--task-guid", tg,
                       "--as", "user", "--format", "json"])
        task = (detail.get("data") or {}).get("task") or {}
        cf = {c.get("name"): c for c in (task.get("custom_fields") or [])}

        def pick(name):
            c = cf.get(name) or {}
            return c.get("single_select_value") or c.get("number_value") or c.get("text_value")

        status_opt = pick("状态")
        status_name = (cfg.get("fields", {}).get("status", {}).get("options") or {})
        status_name = {v: k for k, v in status_name.items()}.get(status_opt, status_opt)

        due = ms_to_dt((task.get("due") or {}).get("timestamp"))
        completed = ms_to_dt(task.get("completed_at"))
        assignees = [id2name.get(m.get("id"), m.get("id"))
                     for m in (task.get("members") or []) if m.get("role") == "assignee"]
        followers = [m.get("id") for m in (task.get("members") or []) if m.get("role") == "follower"]
        missing_followers = [id2name.get(f, f) for f in followers_default if f not in followers]

        rows.append({
            "guid": tg,
            "summary": task.get("summary") or "",
            "assignees": assignees,
            "status": status_name or "—",
            "progress": pick("任务/开发进度%"),
            "due": due,
            "completed": completed,
            "missing_followers": missing_followers,
        })

    overdue, due_soon, done = [], [], []
    for r in rows:
        if r["completed"]:
            done.append(r)
            continue
        if r["due"] and r["due"] < now:
            r["overdue_days"] = (now - r["due"]).days
            overdue.append(r)
        elif r["due"] and r["due"] - now <= timedelta(hours=due_soon_hours):
            due_soon.append(r)

    overdue.sort(key=lambda r: r["due"])
    due_soon.sort(key=lambda r: r["due"])

    if as_json:
        def enc(r):
            return {k: (fmt(v) if isinstance(v, datetime) else v) for k, v in r.items()}
        print(json.dumps({
            "now": fmt(now),
            "total": len(rows),
            "overdue": [enc(r) for r in overdue],
            "due_soon": [enc(r) for r in due_soon],
            "completed": [enc(r) for r in done],
            "missing_followers": [{"summary": r["summary"], "missing": r["missing_followers"]}
                                  for r in rows if r["missing_followers"]],
        }, ensure_ascii=False, indent=1))
        return

    print("盘点时间：" + fmt(now) + "    任务总数：" + str(len(rows)))
    print()

    def table(title, rs, extra=None):
        print("## " + title + "（" + str(len(rs)) + "）")
        if not rs:
            print("  无")
            print()
            return
        print("  | 任务 | 负责人 | 状态 | 进度 | 截止 |" + (" 逾期 |" if extra else ""))
        print("  | --- | --- | --- | --- | --- |" + (" --- |" if extra else ""))
        for r in rs:
            prog = r["progress"]
            prog = ("%.0f%%" % (float(prog) * 100)) if prog not in (None, "") else "—"
            line = "  | %s | %s | %s | %s | %s |" % (
                r["summary"], "、".join(r["assignees"]) or "—", r["status"], prog, fmt(r["due"]))
            if extra:
                line += " %d 天 |" % r["overdue_days"]
            print(line)
        print()

    table("逾期未完成", overdue, extra=True)
    table("临期（%d 小时内）" % due_soon_hours, due_soon)

    gaps = [r for r in rows if r["missing_followers"]]
    print("## 关注人缺默认名单（" + str(len(gaps)) + "）")
    if not gaps:
        print("  无")
    else:
        for r in gaps:
            print("  - %s：缺 %s" % (r["summary"], "、".join(r["missing_followers"])))
    print()
    print("已完成：" + str(len(done)) + " 条（不催办）")
    if not overdue:
        print("今日无逾期未完成任务")


if __name__ == "__main__":
    main()
