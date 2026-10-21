#!/usr/bin/env python3
"""飞书任务评论：按固定模板写评论、自动 @ 负责人、回读校验。

用法：
  # 写新评论（自动 @ 任务负责人）
  python3 scripts/task_comment.py --task-guid <guid> \
      --status 进行中 --progress "前端对接未完成" \
      --risk "暂无" --next "今日 17:30 前出基础流程结果" --eta "2026-10-21"

  # 只看会发什么，不写入
  python3 scripts/task_comment.py --task-guid <guid> ... --dry-run

  # 改已有评论（保留 id）
  python3 scripts/task_comment.py --task-guid <guid> --comment-id <id> ...

  # 只校验某任务评论的 @ 是否生效
  python3 scripts/task_comment.py --task-guid <guid> --verify

配置：$WEICOZ_TASK_TRACKER_CONFIG 或 ~/.config/weicoz-feishu-task-tracker/config.yaml
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


def load_config():
    path = os.environ.get("WEICOZ_TASK_TRACKER_CONFIG") or DEFAULT_CONFIG
    if not os.path.isfile(path):
        die(
            "未找到配置 " + path + "\n"
            "  请先建配置：\n"
            "    mkdir -p ~/.config/weicoz-feishu-task-tracker\n"
            "    cp config.example.yaml ~/.config/weicoz-feishu-task-tracker/config.yaml\n"
            "    chmod 600 ~/.config/weicoz-feishu-task-tracker/config.yaml\n"
            "  或用 export WEICOZ_TASK_TRACKER_CONFIG=/path/to/config.yaml 指过去。"
        )
    if not shutil.which("ruby"):
        die("读 YAML 需要 ruby，未找到。")
    p = subprocess.run(["ruby", "-ryaml", "-rjson", "-e",
                        "puts JSON.generate(YAML.load_file(ARGV[0]) || {})", path],
                       capture_output=True, text=True)
    if p.returncode != 0:
        die("配置解析失败：" + p.stderr.strip())
    return json.loads(p.stdout)


def lark(args):
    if not shutil.which("lark-cli"):
        die("未找到 lark-cli，请先安装并登录。")
    p = subprocess.run(["lark-cli"] + args, capture_output=True, text=True)
    if p.returncode != 0:
        die("lark-cli 调用失败：" + (p.stderr or p.stdout).strip()[:400])
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        die("lark-cli 返回非 JSON：" + p.stdout[:400])


def parse_args(argv):
    opts = {"dry_run": False, "verify": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            opts["dry_run"] = True
        elif a == "--verify":
            opts["verify"] = True
        elif a.startswith("--"):
            if i + 1 >= len(argv):
                die("参数 " + a + " 缺值。")
            opts[a[2:].replace("-", "_")] = argv[i + 1]
            i += 1
        else:
            die("无法识别的参数：" + a)
        i += 1
    return opts


def get_task(tguid):
    d = lark(["task", "tasks", "get", "--task-guid", tguid,
              "--as", "user", "--format", "json"])
    task = (d.get("data") or {}).get("task")
    if not task:
        die("取不到任务详情：" + tguid)
    return task


def assignees_of(task):
    return [m.get("id") for m in (task.get("members") or [])
            if m.get("role") == "assignee" and m.get("type") == "user"]


def at_tags(open_ids):
    # 唯一有效写法：<at id=ou_xxx></at>，id 值不得加引号
    return " ".join("<at id=%s></at>" % oid for oid in open_ids)


def build_content(cfg, open_ids, fields):
    tpl = ((cfg.get("comment") or {}).get("template") or
           "【任务跟踪｜{date}】\n状态：{status}\n进展：{progress}\n问题/风险：{risk}\n"
           "下一步：{next}\n预计完成：{eta}")
    body = tpl
    for k, v in fields.items():
        body = body.replace("{" + k + "}", str(v))
    head = at_tags(open_ids)
    return (head + " " if head else "") + body.strip()


def v1_comments(tguid):
    d = lark(["api", "GET", "/open-apis/task/v1/tasks/%s/comments" % tguid,
              "--params", '{"page_size":50}', "--as", "user"])
    return (d.get("data") or {}).get("items") or []


def v2_comments(tguid):
    d = lark(["api", "GET", "/open-apis/task/v2/comments",
              "--params", json.dumps({"resource_type": "task",
                                      "resource_id": tguid, "page_size": 50}),
              "--as", "user"])
    return (d.get("data") or {}).get("items") or []


def find_comment_id(tguid, content):
    """+comment 不回传 comment id，用最近一条内容匹配反查。"""
    items = v2_comments(tguid)
    for c in sorted(items, key=lambda x: int(x.get("created_at") or 0), reverse=True):
        if (c.get("content") or "").strip() == content.strip():
            return c.get("id")
    return None


def verify(tguid, comment_id=None):
    """v2 回读仍是原始 <at> 标签；v1 会渲染成人名，是唯一可靠判据。

    指定 --comment-id 时只校验那一条，缺 @ 判失败。
    不指定时列出全部评论：有 @ 标 OK，无 @ 标「无@」（历史评论属正常），
    只有残留原始 <at> 标签才算失败。
    """
    v1 = v1_comments(tguid)
    if not v1:
        print("v1 回读无评论")
        return 0 if comment_id is None else 1
    ok = True
    checked = 0
    for c in v1:
        cid = c.get("id")
        if comment_id and str(cid) != str(comment_id):
            continue
        checked += 1
        body = c.get("content") or ""
        has_at = "@" in body
        has_raw = "<at" in body
        if has_raw:
            state = "FAIL-残留原始标签"
            ok = False
        elif has_at:
            state = "OK"
        elif comment_id:
            state = "FAIL-未形成提及"
            ok = False
        else:
            state = "无@"
        print("%s  %s  %s" % (cid, state, body.splitlines()[0][:70] if body else ""))
    if comment_id and checked == 0:
        print("未找到评论 " + str(comment_id))
        return 1
    return 0 if ok else 1


def main():
    o = parse_args(sys.argv[1:])
    tguid = o.get("task_guid")
    if not tguid:
        die("必须给 --task-guid。")

    if o["verify"]:
        sys.exit(verify(tguid, o.get("comment_id")))

    cfg = load_config()
    task = get_task(tguid)
    open_ids = assignees_of(task)
    if not open_ids:
        sys.stderr.write("警告：该任务没有负责人，评论将不带 @。\n")

    fields = {
        "date": o.get("date") or datetime.now(TZ).strftime("%Y-%m-%d"),
        "status": o.get("status", "进行中"),
        "progress": o.get("progress", "—"),
        "risk": o.get("risk", "暂无"),
        "next": o.get("next", "—"),
        "eta": o.get("eta", "待确认"),
    }
    content = build_content(cfg, open_ids, fields)

    if o["dry_run"]:
        print("--- 预览（未写入）---")
        print(content)
        print("--- 预览结束 ---")
        return

    if o.get("comment_id"):
        payload = json.dumps({"comment": {"content": content},
                              "update_fields": ["content"]}, ensure_ascii=False)
        lark(["api", "PATCH", "/open-apis/task/v2/comments/%s" % o["comment_id"],
              "--data", payload, "--as", "user"])
        cid = o["comment_id"]
        print("已更新评论 " + str(cid))
    else:
        d = lark(["task", "+comment", "--task-id", tguid,
                  "--content", content, "--as", "user", "--format", "json"])
        cid = ((d.get("data") or {}).get("comment") or {}).get("id")
        if not cid:
            # +comment 的返回体不含 comment id，回读最近一条按内容匹配
            cid = find_comment_id(tguid, content)
        print("已写入评论 " + str(cid or "（未能定位 id，见下方回读）"))

    print("回读校验：")
    rc = verify(tguid, cid)
    if rc != 0:
        sys.stderr.write("校验失败：@ 未生效或残留原始标签，检查 open_id 与写法。\n")
    sys.exit(rc)


if __name__ == "__main__":
    main()
