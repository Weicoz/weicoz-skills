#!/usr/bin/env python3
"""离线校验月度开发绩效；只读快照，不调用飞书、不写工资表。金额统一用 Decimal。"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

from receipt_guard import CheckError, money


CENT = Decimal("0.01")


def ratio_of(row):
    return money(row.get("ratio") or 0)


def weight_of(row):
    return money(row.get("weight") or 0)


def received_by_project(snapshot, month):
    """按项目汇总当月到账；返回 (分项目字典, 有关联项目的到账合计)。"""
    per_project, linked = defaultdict(Decimal), Decimal(0)
    for flow in snapshot.get("flows", []):
        if (flow.get("date") or "")[:7] != month or flow.get("type") != "款项入账":
            continue
        amount = money(flow["amount"])
        projects = flow.get("project_ids") or []
        if not projects:
            continue
        linked += amount
        for project in projects:
            per_project[project] += amount
    return per_project, linked


def close(left, right):
    return abs(left - right) <= CENT


def check(snapshot, month):
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise CheckError("月份必须是 YYYY-MM")
    rows = snapshot.get("assignment")
    if not rows:
        raise CheckError("快照缺少分配表；先用 lark_snapshot.py --performance 取快照")
    selected = [row for row in rows if row.get("month") == month]
    if not selected:
        raise CheckError("分配表没有该月记录；先补齐项目行")

    by_project, company = defaultdict(list), []
    for row in selected:
        projects = row.get("project_ids") or []
        if len(projects) > 1:
            raise CheckError("一条分配行只能关联一个项目")
        if projects:
            by_project[projects[0]].append(row)
        else:
            company.append(row)

    for row in selected:
        active = ratio_of(row) > 0
        performance, received = money(row["performance"]), money(row["received"])
        if not active:
            # 停用的行（比例 0）只允许 0，避免用停用掩耳盗铃地留着旧数。
            if performance != 0:
                raise CheckError("已停用的分配行绩效不为 0")
            continue
        if not row.get("developer"):
            raise CheckError("绩效行缺少开发人员")
        if received < 0:
            raise CheckError("当月实收为负：分配口径重复扣减，先修口径再算")
        if performance < 0:
            raise CheckError("绩效金额为负：不得写入工资表")
        expected = received * ratio_of(row) / 100 * weight_of(row) / 100
        if not close(performance, expected):
            raise CheckError("绩效金额与实收、比例、权重不一致")

    per_project, linked = received_by_project(snapshot, month)
    for project, group in by_project.items():
        if not per_project.get(project):
            raise CheckError("分配行指向当月无到账的项目")
        active = [row for row in group if ratio_of(row) > 0]
        if active and not close(sum((weight_of(row) for row in active), Decimal(0)), Decimal(100)):
            raise CheckError("项目权重合计不等于 100")
        for row in active:
            if money(row["received"]) > per_project[project] + CENT:
                raise CheckError("项目行实收超过该项目当月到账")
    for project, amount in per_project.items():
        if project not in by_project and amount > 0:
            raise CheckError("当月到账项目缺少分配行")

    project_total = sum((money(row["received"]) for rows in by_project.values() for row in rows), Decimal(0))
    active_company = [row for row in company if ratio_of(row) > 0]
    company_total = None
    if active_company:
        company_total = money(active_company[0]["received"])
        if any(not close(money(row["received"]), company_total) for row in active_company):
            raise CheckError("公司级行实收不一致，同一口径算出多个值")
        if not close(company_total, project_total):
            raise CheckError("公司级实收与项目合计不一致：口径疑似重复扣减，先修口径")
        if not close(company_total, linked):
            raise CheckError("公司级实收超过当月有关联项目的到账")

    totals, active_rows = defaultdict(Decimal), 0
    for row in selected:
        if ratio_of(row) <= 0:
            continue
        for name in row.get("developer") or []:
            totals[name] += money(row["performance"])
        active_rows += 1
    names = {project["id"]: project.get("name") for project in snapshot.get("projects") or []}
    projects = [{"name": names.get(project) or project,
                 "received": str(money(group[0]["received"]).quantize(CENT)),
                 "pool": str(sum((money(row["performance"]) for row in group), Decimal(0)).quantize(CENT))}
                for project, group in sorted(by_project.items(), key=lambda item: str(item[0]))]
    return {"ok": True, "month": month, "rows": len(selected), "active_rows": active_rows,
            "project_received": str(project_total.quantize(CENT)),
            "company_received": None if company_total is None else str(company_total.quantize(CENT)),
            "projects": projects,
            "totals": {name: str(value.quantize(CENT)) for name, value in sorted(totals.items())},
            "total": str(sum(totals.values(), Decimal(0)).quantize(CENT))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="lark_snapshot.py --performance 产出的私有快照")
    parser.add_argument("--month", required=True, help="绩效月份，YYYY-MM")
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        print(json.dumps(check(snapshot, args.month), ensure_ascii=False))
    except (CheckError, KeyError, TypeError, ValueError, OSError) as error:
        detail = str(error) if isinstance(error, CheckError) else "快照结构或文件读取失败"
        print(json.dumps({"ok": False, "error": detail}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
