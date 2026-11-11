#!/usr/bin/env python3
"""校验并逐条发送个人通知：先预演、再按批次发送、可整批撤回与回读。

不做模板以外的自由排版；正文一律由模板渲染，发送前跑断言。
"""
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from salary_month import MonthError, invoke as salary_invoke, load_config, records

DEFAULT_STATE = Path(os.environ.get("WEICOZ_SALARY_STATE", str(Path.home() / ".local/state/weicoz-salary")))
CENT = Decimal("0.01")
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


class NoticeError(ValueError):
    pass


def invoke(args):
    try:
        proc = subprocess.run(["lark-cli", *args], capture_output=True, text=True, timeout=45)
        body = json.loads(proc.stdout or proc.stderr)
        if not isinstance(body, dict):
            raise NoticeError("飞书 CLI 响应不是对象")
        return body
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise NoticeError("飞书 CLI 不可用、超时或响应无效") from None


def amount_of(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise NoticeError("金额不是数字") from None
    if not number.is_finite() or number != number.quantize(CENT):
        raise NoticeError("金额必须精确到分")
    return number


def text_issues(text):
    issues = []
    if "  " in text:
        issues.append("连续空格")
    if "\t" in text:
        issues.append("制表符")
    if PLACEHOLDER.search(text):
        issues.append("未替换占位符")
    if any(line and line != line.strip() for line in text.splitlines()):
        issues.append("行首行尾空格")
    if text != text.rstrip():
        issues.append("末尾空行")
    return issues


def render(item, template, title):
    fields = {"title": title, "name": item["name"], "amount": item["amount"],
              "span": item.get("span", ""), "detail": item.get("detail", "")}
    try:
        return template.format(**fields)
    except (KeyError, IndexError):
        raise NoticeError("模板占位符没有对应字段") from None


def plan(document, payroll_names, month_names, source_amounts=None):
    """返回 (可发送项, 问题列表)。任何一项不合格都不该发出。"""
    title, template, items = document.get("title"), document.get("template"), document.get("items")
    if not title or not template or not items:
        raise NoticeError("通知文件缺少 title / template / items")
    planned, issues, seen = [], [], set()
    for item in items:
        name = str(item.get("name", "")).strip()
        label = name or "<缺姓名>"
        if not name:
            issues.append({"name": label, "issue": "缺少姓名"})
            continue
        if name in seen:
            issues.append({"name": label, "issue": "重复收件人"})
            continue
        seen.add(name)
        if name not in payroll_names:
            issues.append({"name": label, "issue": "名单外人员"})
            continue
        if name not in month_names:
            issues.append({"name": label, "issue": "当月无工资行，不能代扣"})
            continue
        try:
            amount = amount_of(item.get("amount"))
        except NoticeError:
            issues.append({"name": label, "issue": "金额格式无效"})
            continue
        if source_amounts is not None:
            expected = source_amounts.get(name)
            if expected is None:
                issues.append({"name": label, "issue": "源数据里没有该人金额"})
                continue
            if amount_of(expected) != amount:
                issues.append({"name": label, "issue": "金额与源数据不一致"})
                continue
        text = render(item, template, title)
        problems = text_issues(text)
        if problems:
            issues.append({"name": label, "issue": "文案异常：" + "、".join(problems)})
            continue
        planned.append({"name": name, "amount": f"{amount:.2f}", "text": text})
    return planned, issues


def resolve(name, runner):
    found = runner(["contact", "+search-user", "--as", "user", "--query", name])
    users = (found.get("data") or {}).get("users") or []
    exact = [user for user in users if user.get("localized_name") == name]
    if len(exact) != 1:
        raise NoticeError(f"{name} 的飞书账号不是唯一精确匹配")
    return exact[0]["open_id"]


def save_batch(batch, state_dir):
    directory = Path(state_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    path = directory / f"{stamp}-{batch['month']}.json"
    with open(path, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(batch, stream, ensure_ascii=False, indent=2)
    return path


def deliver(planned, runner, month, title, state_dir, staging=None):
    targets = [item for item in planned if staging is None or item["name"] == staging]
    if staging is not None and not targets:
        raise NoticeError("预演对象不在计划内")
    batch = {"created_at": datetime.now().isoformat(timespec="seconds"), "month": month,
             "title": title, "staging": staging, "messages": []}
    for item in targets:
        open_id = resolve(item["name"], runner)
        sent = runner(["im", "+messages-send", "--as", "user", "--user-id", open_id,
                       "--text", item["text"],
                       "--idempotency-key", f"{month}-{item['name']}-{len(batch['messages'])}"])
        data = sent.get("data") or {}
        if not sent.get("ok") or not data.get("message_id"):
            raise NoticeError(f"{item['name']} 发送失败")
        batch["messages"].append({"name": item["name"], "open_id": open_id, "amount": item["amount"],
                                  "message_id": data["message_id"], "chat_id": data.get("chat_id"),
                                  "create_time": data.get("create_time"), "text": item["text"]})
    return batch, save_batch(batch, state_dir)


def read_batch(path):
    try:
        batch = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise NoticeError("批次文件缺失或不是 JSON") from None
    if not batch.get("messages"):
        raise NoticeError("批次里没有消息")
    return batch


def recall(path, runner, confirm=False):
    batch = read_batch(path)
    if not confirm:
        return {"ok": True, "need_confirm": True,
                "pending": [{"name": m["name"], "message_id": m["message_id"]} for m in batch["messages"]]}
    results = []
    for message in batch["messages"]:
        out = runner(["im", "messages", "delete", "--message-id", message["message_id"],
                      "--as", "user", "--yes"])
        results.append({"name": message["name"], "message_id": message["message_id"],
                        "ok": bool(out.get("ok"))})
    return {"ok": all(item["ok"] for item in results), "recalled": results}


def verify(path, runner):
    batch = read_batch(path)
    ids = ",".join(message["message_id"] for message in batch["messages"])
    out = runner(["im", "+messages-mget", "--as", "user", "--message-ids", ids])
    fetched = {m.get("message_id"): m for m in (out.get("data") or {}).get("messages") or []}
    rows = []
    for message in batch["messages"]:
        actual = fetched.get(message["message_id"], {})
        rows.append({"name": message["name"], "message_id": message["message_id"],
                     "deleted": actual.get("deleted"),
                     "text_matches": actual.get("content") == message["text"]})
    return {"ok": all(row["deleted"] is False and row["text_matches"] for row in rows), "messages": rows}


def load_payroll(path, month, runner=salary_invoke):
    """返回 (工资表名单, 当月有工资行的人)。名单外或当月缺行都不许发。"""
    config = load_config(path)
    import yaml
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    in_month = set()
    for row in records(config, runner):
        if str(row.get(config["time"])) != month:
            continue
        value = row.get(config["name"])
        if isinstance(value, list) and value:
            in_month.add(str(value[0]))
        elif isinstance(value, str) and value:
            in_month.add(value)
    payroll = raw.get("name_options") or []
    return (set(payroll) if payroll else in_month), in_month


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notices", nargs="?", type=Path, help="通知 JSON（title / template / items）")
    parser.add_argument("--recall", type=Path, help="撤回该批次文件里的全部消息；未加 --yes 只列清单")
    parser.add_argument("--verify", type=Path, help="回读该批次，核对未撤回且正文一致")
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印正文，不发送")
    parser.add_argument("--staging", help="只发给该姓名的本人，用于确认样式")
    parser.add_argument("--yes", action="store_true", help="确认执行撤回")
    parser.add_argument("--source-amounts", type=Path, help="姓名→金额 JSON，用于核对金额来源")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE / "notices")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get(
        "WEICOZ_SALARY_CONFIG", str(Path.home() / ".config/weicoz-feishu-salary-base/config.yaml"))))
    args = parser.parse_args()
    try:
        if args.recall:
            print(json.dumps(recall(args.recall, invoke, args.yes), ensure_ascii=False))
            return 0
        if args.verify:
            result = verify(args.verify, invoke)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        if not args.notices:
            raise NoticeError("需要通知文件，或用 --recall / --verify 指定批次")
        document = json.loads(args.notices.read_text(encoding="utf-8"))
        month = str(document.get("month", ""))
        payroll, in_month = load_payroll(args.config, month)
        source = None
        if args.source_amounts:
            source = json.loads(args.source_amounts.read_text(encoding="utf-8"))
        planned, issues = plan(document, payroll, in_month, source)
        if issues:
            print(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False))
            return 1
        if args.dry_run:
            print(json.dumps({"ok": True, "dry_run": True,
                              "messages": [{"name": item["name"], "text": item["text"]} for item in planned]},
                             ensure_ascii=False, indent=2))
            return 0
        batch, path = deliver(planned, invoke, month, document["title"], args.state_dir, args.staging)
        print(json.dumps({"ok": True, "batch": str(path),
                          "messages": [{"name": m["name"], "message_id": m["message_id"]}
                                       for m in batch["messages"]]}, ensure_ascii=False))
    except (NoticeError, MonthError, KeyError, TypeError, ValueError, OSError) as error:
        detail = str(error) if isinstance(error, (NoticeError, MonthError)) else "配置、表结构或文件读取失败"
        print(json.dumps({"ok": False, "error": detail}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
