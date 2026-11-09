#!/usr/bin/env python3
"""离线校验收款计划；不调用飞书、不修改账表。金额统一用 Decimal。"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys


FIELDS = {
    "contract_total": "收款总额/项目金额", "received": "已收款项",
    "channel_paid": "已返点渠道", "channel_due": "待返渠道款",
    "other_paid": "已转款莞云/其他", "other_due": "待转莞云/其他",
    "net": "实收款", "receivable": "待收款项",
}
NET_FORMULA = "[已收款项]-[已返点渠道]-[待返渠道款]-[已转款莞云/其他]-[待转莞云/其他]"
RECEIVABLE_FORMULA = 'IF(ISBLANK([收款总额/项目金额]),"",[收款总额/项目金额]-[已收款项])'
BUSINESS_BINDING_FORMULA = 'IF(ISBLANK([关联项目]),[业务（手填）]&"",[关联项目].[业务].UNIQUE().ARRAYJOIN("、"))'
MONEY_FIELDS = ("received", "channel_paid", "channel_due", "other_paid", "other_due")


class CheckError(ValueError):
    pass


def business_binding_formula(link_field):
    return f'IF(ISBLANK([{link_field}]),[业务（手填）]&"",[{link_field}].[业务].UNIQUE().ARRAYJOIN("、"))'


def money(value):
    if isinstance(value, bool) or value is None or value == "":
        raise CheckError("金额缺失或不是数字")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise CheckError("金额不是数字") from None
    try:
        valid = number.is_finite() and number == number.quantize(Decimal("0.01"))
    except InvalidOperation:
        valid = False
    if not valid:
        raise CheckError("金额必须有限且精确到分")
    return number


def amounts(project):
    # 计划中的空值代表未知，不能悄悄解释成“不欠”。
    result = {key: money(project[key]) for key in MONEY_FIELDS}
    if any(value < 0 for value in result.values()):
        raise CheckError("项目已收、已付、待付金额必须非负")
    return result


def net(project):
    values = amounts(project)
    return values["received"] - sum(values[k] for k in MONEY_FIELDS[1:])


def business(value):
    if value in (None, ""):
        return ()
    values = value.split("、") if isinstance(value, str) else value
    if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) for v in values):
        raise CheckError("业务人员格式无效")
    return tuple(sorted({v.strip() for v in values if v.strip()}))


def audit_business(snapshot):
    projects = {p["id"]: p for p in snapshot["projects"]}
    flow_schema = {f["name"]: f for f in snapshot.get("schema", {}).get("flow", [])}
    business_is_formula = flow_schema.get("业务", {}).get("type") == "formula"
    issues = []
    for flow in snapshot["flows"]:
        links = flow.get("project_ids", [flow["project_id"]] if flow.get("project_id") else [])
        if not isinstance(links, list) or any(not isinstance(link, str) for link in links):
            raise CheckError("项目关联格式无效")
        if len(links) <= 1 and flow.get("project_id") != (links[0] if links else None):
            raise CheckError("项目单值与关联列表不一致")
        code = None
        if not links:
            if business_is_formula and business(flow.get("business")) != business(flow.get("business_manual")):
                issues.append({"flow_id": flow.get("id", flow.get("source_id")),
                               "project_ids": links, "issue": "manual_business_mismatch"})
            continue  # 无项目的历史手填业务不自动覆盖。
        if len(links) != 1:
            code = "multiple_projects"
        elif links[0] not in projects:
            code = "missing_project"
        elif not business(projects[links[0]].get("business")):
            code = "project_business_missing"
        elif business(flow.get("business")) != business(projects[links[0]].get("business")):
            code = "business_mismatch"
        if code:
            issues.append({"flow_id": flow.get("id", flow.get("source_id")), "project_ids": links, "issue": code})
    return {"ok": not issues, "checked_flows": len(snapshot["flows"]), "issues": issues}


def flow_key(flow):
    # 金额相同不是重复依据；保留来源唯一键，并核对交易指纹。
    date = datetime.fromisoformat(flow["date"])
    if date.tzinfo is None:
        raise CheckError("计划及快照流水时间必须包含时区")
    return (date.astimezone(timezone.utc).isoformat(), flow["counterparty"],
            format(money(flow["amount"]), ".2f"), flow["type"])


def schema_signature(fields):
    if len({f["id"] for f in fields}) != len(fields):
        raise CheckError("字段 ID 重复")
    return sorted((json.dumps(f, sort_keys=True, ensure_ascii=False) for f in fields))


def validate_schema(before, current):
    for table in ("project", "flow"):
        if schema_signature(before[table]) != schema_signature(current[table]):
            raise CheckError("字段结构变化：重新读取含义并生成计划；dry-run 不能替代字段校验")
    fields = current["project"]
    names = {f["name"]: f for f in fields}
    if len(names) != len(fields):
        raise CheckError("字段名称重复")
    if names.get("业务", {}).get("type") != "select":
        raise CheckError("项目业务字段需核对为负责人来源")
    for role, name in FIELDS.items():
        if name not in names or names[name]["type"] != ("formula" if role in ("net", "receivable") else "number"):
            raise CheckError("字段语义不匹配：应付全额列不能自动当作已付列")
    expression = re.sub(r"\s+", "", names[FIELDS["net"]].get("expression", ""))
    if not re.fullmatch(r"\[[^\[\]]+\](?:[+-]\[[^\[\]]+\])*", expression):
        raise CheckError("实收公式需要核对已付与待付扣减")
    actual = Counter()
    for sign, name in re.findall(r"([+-]?)\[([^\[\]]+)\]", expression):
        actual[name] += -1 if sign == "-" else 1
    expected = {FIELDS[k]: (1 if k == "received" else -1) for k in MONEY_FIELDS}
    if {k: v for k, v in actual.items() if v} != expected:
        raise CheckError("实收公式漏扣或重复扣除了已付/待付金额")
    flow_fields = {f["name"]: f for f in current["flow"]}
    flow_business = flow_fields.get("业务", {})
    if flow_business.get("type") not in ("select", "formula"):
        raise CheckError("流水业务字段缺失或类型需核实")
    if flow_business.get("type") == "formula":
        expression = re.sub(r"\s+", "", flow_business.get("expression", ""))
        backup = flow_fields.get("业务（手填）", {})
        link_fields = [f["name"] for f in current["flow"] if f["type"] == "link"]
        if len(link_fields) != 1 or expression != re.sub(r"\s+", "", business_binding_formula(link_fields[0])):
            raise CheckError("流水业务公式与项目联动规则不符")
        if backup.get("type") != "select" or backup.get("multiple", False):
            raise CheckError("流水业务手填备份字段缺失或类型不符")
    for name, kind in {"交易对象": "text", "变动日期": "datetime", "资金变动": "number",
                       "变动类型": "select", "备注": "text"}.items():
        if name not in flow_fields or flow_fields[name]["type"] != kind:
            raise CheckError("流水字段缺失或类型不符")
    if sum(f["type"] == "link" for f in current["flow"]) != 1:
        raise CheckError("流水项目关联字段不唯一，需人工核对")
    choices = {o["name"] for o in flow_fields["变动类型"].get("options", [])}
    if not {"款项入账", "返点渠道", "转款莞云"}.issubset(choices):
        raise CheckError("流水分类选项缺失；不能靠写记录自动创建选项")


def validate_receivables(plan):
    fields = {f["name"]: f for f in plan["schema_current"]["project"]}
    formula = re.sub(r"\s+", "", fields[FIELDS["receivable"]].get("expression", ""))
    for project in plan["projects"]:
        total = project["contract_total"]
        if total is None:
            if project["receivable"] not in (None, ""):
                raise CheckError("合同总额未知时，待收必须留空")
            if formula != RECEIVABLE_FORMULA:
                raise CheckError("旧待收公式不保护空总额：先只记流水，或经授权修正公式后再建项目")
        else:
            if not str(project.get("contract_source", "")).startswith(("user:", "contract:")):
                raise CheckError("合同总额需用户确认或合同来源，不能用到账额自动补全")
            if money(total) < 0 or money(project["receivable"]) != money(total) - money(project["received"]):
                raise CheckError("待收金额与合同总额、累计已收不一致")


def validate_money(plan):
    projects = {p["id"]: p for p in plan["projects"]}
    if len(projects) != len(plan["projects"]):
        raise CheckError("项目 ID 重复")
    existing = plan.get("existing_flows", [])
    existing_sources = {f["source_id"] for f in existing}
    existing_keys = {flow_key(f) for f in existing}
    seen_sources, seen_keys = set(), set()
    incoming = Decimal(0)
    for flow in plan["flows"]:
        if not flow.get("source_id") or not flow.get("counterparty"):
            raise CheckError("流水缺少来源唯一键或交易对象")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2})?", flow["date"]):
            raise CheckError("流水必须有凭证支持的日期和时间")
        try:
            datetime.fromisoformat(flow["date"])
        except ValueError:
            raise CheckError("流水日期无效") from None
        if flow["type"] not in ("款项入账", "返点渠道", "转款莞云"):
            raise CheckError("本校验器仅处理收款及两类返点，其他业务单独处理")
        value = money(flow["amount"])
        if not value:
            raise CheckError("不得创建零金额流水")
        if (flow["type"] == "款项入账") != (value > 0):
            raise CheckError("入账为正，支出为负")
        key = flow_key(flow)
        if flow["source_id"] in existing_sources | seen_sources or key in existing_keys | seen_keys:
            raise CheckError("发现重复流水，先核实已写状态")
        if flow["source_id"] in plan.get("excluded_source_ids", []):
            raise CheckError("排除的凭证进入了写入计划")
        seen_sources.add(flow["source_id"])
        seen_keys.add(key)
        if flow.get("project_id") is not None and flow["project_id"] not in projects:
            raise CheckError("流水关联的项目不存在于计划")
        if value > 0:
            incoming += value
    if incoming != money(plan["expected_income_total"]):
        raise CheckError("本次入账合计与凭证合计不一致")
    combined = existing + plan["flows"]
    for project in projects.values():
        values = amounts(project)
        if money(project["net"]) != net(project):
            raise CheckError("实收漏扣或重复扣除了应付金额")
        linked = [f for f in combined if f.get("project_id") == project["id"]]
        # 使用完整项目流水核对已付，避免把“应付全额”误当“已付”。
        paid_channel = -sum((money(f["amount"]) for f in linked if f["type"] == "返点渠道"), Decimal(0))
        paid_other = -sum((money(f["amount"]) for f in linked if f["type"] == "转款莞云"), Decimal(0))
        if values["channel_paid"] != paid_channel or values["other_paid"] != paid_other:
            raise CheckError("已付金额与项目关联支出流水不一致；先补证据或核对历史")
        added = sum((money(f["amount"]) for f in plan["flows"]
                     if f.get("project_id") == project["id"] and f["type"] == "款项入账"), Decimal(0))
        if values["received"] != money(project["received_before"]) + added:
            raise CheckError("累计已收与修改前累计加本次到账不一致")
    return {"income_count": sum(money(f["amount"]) > 0 for f in plan["flows"]),
            "income_total": str(incoming), "project_count": len(projects)}


def validate(plan):
    validate_schema(plan["schema_before"], plan["schema_current"])
    validate_receivables(plan)
    if any(not business(p.get("business")) for p in plan["projects"]):
        raise CheckError("项目业务人员未确认；不能用流水备注或旧手填值替代")
    if audit_business({"projects": plan["projects"], "flows": plan["flows"]})["issues"]:
        raise CheckError("流水业务人员与关联项目不一致")
    return validate_money(plan)


def verify(plan, after):
    validate(plan)
    validate_schema(plan["schema_current"], after["schema"])
    mapping = plan.get("id_map", {})
    actual_projects = {p["id"]: p for p in after["projects"]}
    for expected in plan["projects"]:
        actual = actual_projects.get(mapping.get(expected["id"], expected["id"]))
        if actual is None:
            raise CheckError("回读缺少计划项目")
        if business(actual.get("business")) != business(expected.get("business")):
            raise CheckError("回读项目业务人员变化，重新核对当前归属")
        for key in (*MONEY_FIELDS, "net", "contract_total", "receivable"):
            a, b = actual.get(key), expected[key]
            if b is None or b == "":
                if a not in (None, ""):
                    raise CheckError("回读把未知金额变成了数值")
            elif money(a) != money(b):
                raise CheckError("回读金额与批准的计划不一致")
    keys = [flow_key(f) for f in after["flows"]]
    for expected in plan["flows"]:
        matches = [f for f, key in zip(after["flows"], keys) if key == flow_key(expected)]
        target = mapping.get(expected.get("project_id"), expected.get("project_id"))
        if len(matches) != 1 or matches[0].get("project_id") != target:
            raise CheckError("回读流水缺失、重复或项目关联错误")
        if target and business(matches[0].get("business")) != business(expected.get("business")):
            raise CheckError("回读流水业务人员与项目预期不一致")
    return {"verified_projects": len(plan["projects"]), "verified_flows": len(plan["flows"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="写入计划；--audit 时为只读快照")
    parser.add_argument("--audit", action="store_true", help="用户修改项目后，只读检查当前流水业务是否匹配")
    parser.add_argument("--after", type=Path, help="写入后只读快照；提供时校验金额和关联")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if args.audit:
            result = audit_business(plan)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        result = verify(plan, json.loads(args.after.read_text(encoding="utf-8"))) if args.after else validate(plan)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except (CheckError, KeyError, TypeError, ValueError, OSError) as error:
        # 不回显计划正文、CLI 原始响应或凭据。
        detail = str(error) if isinstance(error, CheckError) else "计划结构或文件读取失败"
        print(json.dumps({"ok": False, "error": detail}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
