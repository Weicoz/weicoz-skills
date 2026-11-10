#!/usr/bin/env python3
"""从考勤统计 .xlsx 提取工资表要用的四列；只读文件，不写表、不联网。"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys


SUMMARY = {"name": "姓名", "due_days": "应出勤天数", "due_hours": "应出勤时长（小时）",
           "actual_days": "实际出勤天数", "actual_hours": "实际出勤时长（小时）",
           "allowance": "补贴", "note": "备注"}
DETAIL = {"name": "姓名", "due": "应出勤标记", "actual": "实际出勤标记"}
HOURS_PER_DAY = Decimal("7.5")


class ExtractError(ValueError):
    pass


def number(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ExtractError("考勤表出现非数字单元格") from None


def text(value):
    return "" if value is None else str(value).strip()


def header_index(rows, required, limit=6):
    for index, row in enumerate(rows[:limit]):
        names = [text(cell) for cell in row]
        if all(name in names for name in required):
            return index, names
    return None, None


def read_workbook(path):
    try:
        import openpyxl
    except ImportError:
        raise ExtractError("读取 .xlsx 需要 openpyxl；先按本机依赖约定安装") from None
    try:
        return openpyxl.load_workbook(path, data_only=True)
    except (OSError, ValueError, KeyError):
        raise ExtractError("无法打开考勤文件；确认是 .xlsx 且未加密") from None


def month_of(workbook, fallback=None):
    for sheet in workbook.worksheets:
        match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", sheet.title)
        if match:
            return f"{match.group(1)}{int(match.group(2)):02d}"
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(min_row=1, max_row=2, values_only=True))
        for row in rows:
            for cell in row:
                match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", text(cell))
                if match:
                    return f"{match.group(1)}{int(match.group(2)):02d}"
    return fallback


def summary_people(sheet):
    rows = list(sheet.iter_rows(values_only=True))
    index, names = header_index(rows, (SUMMARY["name"], SUMMARY["actual_days"]))
    if index is None:
        raise ExtractError("找不到考勤汇总表头（姓名 / 应出勤天数 / 实际出勤天数）")
    column = {role: names.index(name) for role, name in SUMMARY.items() if name in names}
    for required in ("name", "due_days", "actual_days"):
        if required not in column:
            raise ExtractError("考勤汇总缺少必要列")
    people = []
    for row in rows[index + 1:]:
        name = text(row[column["name"]])
        if not name:
            continue
        due_days, actual_days = number(row[column["due_days"]]), number(row[column["actual_days"]])
        if due_days is None or actual_days is None:
            raise ExtractError("考勤汇总有人员缺天数")
        due_hours = number(row[column["due_hours"]]) if "due_hours" in column else None
        actual_hours = number(row[column["actual_hours"]]) if "actual_hours" in column else None
        if due_hours is not None and actual_hours is not None:
            leave_hours = due_hours - actual_hours
        else:
            leave_hours = (due_days - actual_days) * HOURS_PER_DAY
        leave_hours = max(leave_hours, Decimal(0))
        allowance = None
        if "allowance" in column:
            value = number(row[column["allowance"]])
            allowance = None if value is None else str(value)
        people.append({"name": name, "due_days": str(due_days), "actual_days": str(actual_days),
                       "leave_hours": str(leave_hours.quantize(Decimal("0.01"))),
                       "allowance": allowance,
                       "note": text(row[column["note"]]) if "note" in column else ""})
    if not people:
        raise ExtractError("考勤汇总没有人员行")
    return people


def detail_sums(workbook):
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        index, names = header_index(rows, (DETAIL["name"], DETAIL["actual"]))
        if index is None:
            continue
        column = {role: names.index(name) for role, name in DETAIL.items()}
        sums = {}
        for row in rows[index + 1:]:
            name = text(row[column["name"]])
            if not name:
                continue
            bucket = sums.setdefault(name, {"due": Decimal(0), "actual": Decimal(0)})
            for role in ("due", "actual"):
                value = number(row[column[role]])
                if value is not None:
                    bucket[role] += value
        return sheet.title, sums
    return None, {}


def extract(path, month=None, allow_detail_mismatch=False):
    workbook = read_workbook(path)
    summary = None
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(min_row=1, max_row=6, values_only=True))
        if header_index(rows, (SUMMARY["name"], SUMMARY["actual_days"]))[0] is not None:
            summary = sheet
            break
    if summary is None:
        raise ExtractError("工作簿里没有考勤汇总表")
    people = summary_people(summary)
    title, sums = detail_sums(workbook)
    warnings, mismatched = [], []
    if title is None:
        warnings.append("未找到逐日明细，未做交叉核对")
    else:
        for person in people:
            detail = sums.get(person["name"])
            if detail is None:
                mismatched.append({"name": person["name"], "summary": person["actual_days"], "detail": None})
            elif detail["actual"] != Decimal(person["actual_days"]):
                mismatched.append({"name": person["name"], "summary": person["actual_days"],
                                   "detail": str(detail["actual"])})
        if mismatched:
            warnings.append(f"明细实际出勤与汇总不一致（对照表 {title}）：以汇总为准，需人工确认")
    result = {"ok": not mismatched or allow_detail_mismatch,
              "source": str(path), "month": month_of(workbook, month),
              "detail_sheet": title, "people": people, "warnings": warnings,
              "mismatched": mismatched}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="考勤统计 .xlsx")
    parser.add_argument("--month", help="文件里读不出月份时用它兜底，YYYYMM")
    parser.add_argument("--allow-detail-mismatch", action="store_true",
                        help="明细与汇总不一致时仍返回成功，只带警告")
    args = parser.parse_args()
    try:
        result = extract(args.xlsx, args.month, args.allow_detail_mismatch)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1
    except (ExtractError, OSError, KeyError, IndexError):
        print(json.dumps({"ok": False, "error": "考勤表结构或读取失败：确认汇总列与人员行；不回显表格正文"},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
