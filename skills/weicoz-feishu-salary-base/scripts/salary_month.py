#!/usr/bin/env python3
"""按月份打印工资表的紧凑一行一人视图；只读，写入仍由人工确认后执行。"""
import argparse
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import subprocess
import sys

AMOUNT_FIELDS = {"基本薪资", "应缴社保", "个税", "绩效奖金", "补贴", "实发薪资", "基本实发薪资", "加班奖金"}


class MonthError(ValueError):
    pass


def invoke(args):
    try:
        proc = subprocess.run(["lark-cli", *args], capture_output=True, text=True, timeout=45)
        body = json.loads(proc.stdout or proc.stderr)
        if not isinstance(body, dict) or not body.get("ok"):
            raise MonthError("飞书只读查询失败；检查身份、权限或限流")
        return body["data"]
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise MonthError("飞书 CLI 不可用、超时或响应无效") from None


def load_config(path):
    try:
        import yaml
    except ImportError:
        raise MonthError("读取 YAML 私有配置需要 PyYAML；先按本机依赖约定安装") from None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        base, fields = raw["base"], raw["fields"]
        columns = [fields["text"], fields["time"], fields["name"], *fields["writable"], *fields["formula"]]
        if not isinstance(base.get("token"), str) or not isinstance(base.get("table"), str):
            raise ValueError()
        return {"token": base["token"], "table": base["table"], "time": fields["time"], "columns": columns}
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        raise MonthError("私有配置缺失或不完整；未回显配置") from None


def records(config, runner=invoke):
    rows, offset = [], 0
    while True:
        page = runner(["base", "+record-list", "--base-token", config["token"], "--table-id", config["table"],
                       "--as", "user", "--format", "json", "--limit", "200", "--offset", str(offset)])
        names, ids, data = page["fields"], page.get("record_id_list", []), page["data"]
        if data and len(names) != len(data[0]):
            raise MonthError("字段列序或行宽异常")
        if len(ids) != len(data):
            raise MonthError("记录 ID 缺失或分页异常")
        rows.extend({name: value for name, value in zip(names, row)} for row in data)
        if not page.get("has_more"):
            return rows
        if not data:
            raise MonthError("记录分页没有前进，停止读取")
        offset += len(data)


def show(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item.get("name", item.get("text", item)) if isinstance(item, dict) else item)
                        for item in value)
    return str(value)


def decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(0)


def render(month, rows, columns, time_field="时间"):
    selected = [row for row in rows if show(row.get(time_field)) == month]
    lines = ["\t".join(columns)]
    for row in selected:
        lines.append("\t".join(show(row.get(column)) for column in columns))
    total = sum((decimal(row.get("实发薪资")) for row in selected), Decimal(0))
    return "\n".join(lines + ["", f"{month} 共 {len(selected)} 人｜实发薪资合计 {total:.2f}"]), selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("month", help="YYYYMM")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get(
        "WEICOZ_SALARY_CONFIG", str(Path.home() / ".config/weicoz-feishu-salary-base/config.yaml"))))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        config["columns"] = list(dict.fromkeys(config["columns"]))
        text, selected = render(args.month, records(config), config["columns"], config["time"])
        print(text)
        if not selected:
            return 1
    except (MonthError, KeyError, TypeError, ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error) if isinstance(error, MonthError)
                          else "工资表读取或配置解析失败；未回显数据"}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
