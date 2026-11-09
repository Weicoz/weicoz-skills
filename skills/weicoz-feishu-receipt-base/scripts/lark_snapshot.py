#!/usr/bin/env python3
"""顺序、分页读取飞书财务快照；只输出本机私有产物路径，不提供写 API。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from receipt_guard import CheckError, FIELDS, business


def invoke(args):
    try:
        proc = subprocess.run(["lark-cli", *args], capture_output=True, text=True, timeout=45)
        body = json.loads(proc.stdout or proc.stderr)
        if not isinstance(body, dict):
            raise CheckError("飞书 CLI 响应不是对象")
        return body
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise CheckError("飞书 CLI 不可用、超时或响应无效；未输出原始响应") from None


class Reader:
    def __init__(self, config, runner=invoke, sleeper=time.sleep):
        self.config, self.runner, self.sleeper = config, runner, sleeper

    def call(self, command, table, extra):
        if command not in ("+field-list", "+record-list"):
            raise CheckError("快照工具只允许读取字段和记录")
        args = ["base", command, "--base-token", self.config["token"], "--table-id",
                self.config[table + "_table"], "--as", "user", "--format", "json", *extra]
        for attempt in range(3):
            result = self.runner(args)
            if result.get("ok"):
                return result["data"]
            if result.get("error", {}).get("subtype") == "rate_limit" and attempt < 2:
                self.sleeper(2 ** attempt)
                continue
            raise CheckError("飞书只读查询失败；检查身份、权限或限流状态")

    def fields(self, table):
        result, seen, offset = [], set(), 0
        while True:
            page = self.call("+field-list", table, ["--limit", "200", "--offset", str(offset)])
            items = page["fields"]
            ids = [f["id"] for f in items]
            if len(set(ids)) != len(ids) or seen.intersection(ids):
                raise CheckError("字段分页重复，停止读取")
            seen.update(ids)
            result.extend(items)
            if not page.get("has_more") and len(result) >= page.get("total", len(result)):
                break
            if not items:
                raise CheckError("字段分页没有前进，停止读取")
            offset += len(items)
        if len({f["id"] for f in result}) != len(result):
            raise CheckError("字段分页重复，停止读取")
        return [{k: f[k] for k in ("id", "name", "type", "expression", "multiple", "options") if k in f}
                for f in result]

    def records(self, table, fields):
        result, seen, offset = [], set(), 0
        while True:
            page = self.call("+record-list", table, ["--limit", "200", "--offset", str(offset),
                              *[arg for f in fields for arg in ("--field-id", f)]])
            rows, ids, names = page["data"], page.get("record_id_list", []), page["fields"]
            if len(rows) != len(ids) or len(set(ids)) != len(ids) or seen.intersection(ids):
                raise CheckError("记录 ID 缺失或分页重复；不能按行号猜测 ID")
            for rid, row in zip(ids, rows):
                if len(row) != len(names):
                    raise CheckError("字段列序或行宽异常")
                result.append({"id": rid, **dict(zip(names, row))})
            seen.update(ids)
            if not page.get("has_more"):
                return result
            if not rows:
                raise CheckError("记录分页没有前进，停止读取")
            offset += len(rows)

    def snapshot(self):
        schema = {table: self.fields(table) for table in ("project", "flow")}
        project_names = {f["name"] for f in schema["project"]}
        if "业务" not in project_names:
            raise CheckError("项目业务字段缺失，不能核对业务归属")
        projects = self.records("project", [n for n in ("项目", "客户/渠道公司", "业务", *FIELDS.values()) if n in project_names])
        flow_names = {f["name"] for f in schema["flow"]}
        needed = ("交易对象", "变动日期", "资金变动", "变动类型", "项目收款表", "业务")
        if not set(needed).issubset(flow_names):
            raise CheckError("流水字段变化，先核对字段语义")
        flows = self.records("flow", needed)
        normalized_flows = []
        for row in flows:
            kinds, links = row["变动类型"] or [], row["项目收款表"] or []
            if isinstance(kinds, str):
                kinds = [kinds]
            if len(kinds) != 1:
                raise CheckError("流水分类缺失，需人工核对")
            normalized_flows.append({"id": row["id"], "source_id": "existing:" + row["id"],
                                     "counterparty": row["交易对象"], "date": row["变动日期"],
                                     "amount": row["资金变动"], "type": kinds[0],
                                     "project_id": links[0]["id"] if len(links) == 1 else None,
                                     "project_ids": [link["id"] for link in links],
                                     "business": list(business(row.get("业务")))})
        return {"schema": schema, "projects": [{"id": p["id"], "name": p.get("项目"),
                "business": list(business(p.get("业务"))),
                **{role: p.get(name) for role, name in FIELDS.items()}} for p in projects],
                "flows": normalized_flows}


def load_config(path):
    try:
        import yaml
    except ImportError:
        raise CheckError("读取 YAML 私有配置需要 PyYAML；先按本机依赖约定安装") from None
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))["base"]["receipt"]
        if not all(isinstance(config.get(k), str) and config[k] for k in ("token", "project_table", "flow_table")):
            raise ValueError()
        return config
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        raise CheckError("私有配置缺失或收款配置不完整；未回显配置") from None


def save_private(config_path, snapshot):
    reports = config_path.resolve().parent / "reports"
    if any((p / ".git").exists() for p in (reports, *reports.parents)):
        raise CheckError("快照目录位于 Git 工作区；请把私有配置放在仓库之外")
    reports.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="snapshot-", dir=reports))
    output = directory / "snapshot.json"
    with open(output, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(snapshot, stream, ensure_ascii=False, indent=2)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(os.environ.get(
        "WEICOZ_RECEIPT_CONFIG", str(Path.home() / ".config/weicoz-feishu-receipt-base/config.yaml"))))
    args = parser.parse_args()
    try:
        snapshot = Reader(load_config(args.config)).snapshot()
        print(json.dumps({"ok": True, "output": str(save_private(args.config, snapshot)),
                          "projects": len(snapshot["projects"]), "flows": len(snapshot["flows"])}, ensure_ascii=False))
    except (CheckError, KeyError, TypeError, ValueError, OSError):
        print(json.dumps({"ok": False, "error": "快照读取失败：检查私有配置、CLI 状态、分页或字段结构；不回显原始数据"}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
