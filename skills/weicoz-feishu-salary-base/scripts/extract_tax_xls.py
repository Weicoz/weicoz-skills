#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

try:
    import xlrd
except ImportError as exc:
    raise SystemExit("缺少 xlrd；请安装 xlrd==1.2.0 后重试") from exc


SOCIAL_COLUMNS = (
    "本期基本养老保险费",
    "本期基本医疗保险费",
    "本期失业保险费",
    "本期住房公积金",
)
REQUIRED_COLUMNS = ("姓名", "税款所属期起", "税款所属期止", *SOCIAL_COLUMNS, "应补(退)税额")
CENT = Decimal("0.01")


def decimal_value(value, field, row_number):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"第 {row_number} 行字段 {field} 不是数字: {value!r}") from exc


def month_value(value, workbook):
    if isinstance(value, (int, float)):
        return xlrd.xldate_as_datetime(value, workbook.datemode).strftime("%Y%m")
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y%m"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m")
        except ValueError:
            pass
    raise ValueError(f"无法识别税款所属期: {value!r}")


def extract_declaration_report(sheet):
    period = str(sheet.cell_value(1, 0))
    match = re.search(r"(\d{4})年(\d{1,2})月\d{1,2}日至(\d{4})年(\d{1,2})月\d{1,2}日", period)
    if not match:
        raise ValueError(f"无法识别税款所属期: {period!r}")
    start = f"{match[1]}{int(match[2]):02d}"
    end = f"{match[3]}{int(match[4]):02d}"
    if start != end:
        raise ValueError(f"税款所属期跨月: {start} -> {end}")

    header = next(
        (i for i in range(sheet.nrows - 3)
         if sheet.cell_value(i, 0) == "序号" and sheet.cell_value(i, 1) == "姓名"),
        None,
    )
    if header is None:
        raise ValueError("找不到申报表姓名表头")

    def column(row, name):
        values = [str(sheet.cell_value(row, col)).strip() for col in range(sheet.ncols)]
        if name not in values:
            raise ValueError(f"缺少必要字段: {name}")
        return values.index(name)

    social_columns = {
        field: column(header + 2, field.removeprefix("本期"))
        for field in SOCIAL_COLUMNS
    }
    income_column = column(header + 2, "收入")
    tax_column = column(header + 1, "应补/退税额")
    rows = []
    names = set()
    for row_index in range(header + 4, sheet.nrows):
        if not str(sheet.cell_value(row_index, 0)).strip().isdigit():
            break
        row_number = row_index + 1
        name = str(sheet.cell_value(row_index, 1)).strip()
        if not name or name in names:
            raise ValueError(f"第 {row_number} 行姓名缺失或重复: {name!r}")
        if str(sheet.cell_value(row_index, 6)).strip() != "正常工资薪金":
            raise ValueError(f"第 {row_number} 行不是正常工资薪金")
        names.add(name)
        details = {
            field: decimal_value(sheet.cell_value(row_index, col), field, row_number)
            for field, col in social_columns.items()
        }
        rows.append({
            "name": name,
            "social_security": float(sum(details.values(), Decimal("0")).quantize(CENT)),
            "tax": float(decimal_value(sheet.cell_value(row_index, tax_column), "应补/退税额", row_number)),
            "declared_income": float(decimal_value(sheet.cell_value(row_index, income_column), "收入", row_number)),
            "social_details": {key: float(value) for key, value in details.items()},
        })
    if not rows:
        raise ValueError("没有可用申报明细")
    return {"month": start, "rows": rows}


def extract(path):
    workbook = xlrd.open_workbook(str(path), formatting_info=False, logfile=sys.stderr)
    if not workbook.sheet_names():
        raise ValueError("工作簿没有工作表")

    sheet = workbook.sheet_by_index(0)
    if sheet.nrows < 2:
        raise ValueError("工作表没有税务明细")
    if str(sheet.cell_value(0, 0)).strip() == "个人所得税扣缴申报表":
        return extract_declaration_report(sheet)

    headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ValueError(f"缺少必要字段: {', '.join(missing)}")
    columns = {name: headers.index(name) for name in REQUIRED_COLUMNS}

    rows = []
    names = set()
    months = set()
    for row_index in range(1, sheet.nrows):
        row_number = row_index + 1
        name = str(sheet.cell_value(row_index, columns["姓名"])).strip()
        if not name:
            continue
        if name in names:
            raise ValueError(f"姓名重复: {name}")
        names.add(name)

        start_month = month_value(sheet.cell_value(row_index, columns["税款所属期起"]), workbook)
        end_month = month_value(sheet.cell_value(row_index, columns["税款所属期止"]), workbook)
        if start_month != end_month:
            raise ValueError(f"第 {row_number} 行所属期跨月: {start_month} -> {end_month}")
        months.add(start_month)

        details = {
            field: decimal_value(sheet.cell_value(row_index, columns[field]), field, row_number)
            for field in SOCIAL_COLUMNS
        }
        social = sum(details.values(), Decimal("0")).quantize(CENT)
        tax = decimal_value(sheet.cell_value(row_index, columns["应补(退)税额"]), "应补(退)税额", row_number)
        rows.append({
            "name": name,
            "social_security": float(social),
            "tax": float(tax),
            "social_details": {key: float(value) for key, value in details.items()},
        })

    if not rows:
        raise ValueError("没有可用税务明细")
    if len(months) != 1:
        raise ValueError(f"文件包含多个税款所属月: {', '.join(sorted(months))}")

    return {"month": months.pop(), "rows": rows}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"用法: {Path(sys.argv[0]).name} <税款计算或综合所得申报.xls>")
    path = Path(sys.argv[1]).expanduser()
    if path.suffix.lower() != ".xls":
        raise SystemExit("仅支持 .xls 文件")
    if not path.is_file():
        raise SystemExit(f"文件不存在: {path}")
    try:
        result = extract(path)
    except (ValueError, xlrd.XLRDError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
