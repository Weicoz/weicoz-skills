from decimal import Decimal
import unittest

from performance_guard import check
from receipt_guard import CheckError


def row(project, developer, weight, ratio, received, month="2026-10", performance=None):
    amount = Decimal(str(received))
    if performance is None:
        performance = amount * Decimal(str(ratio)) / 100 * Decimal(str(weight)) / 100
    return {"id": "rec-" + str(abs(hash((project, developer, received)))),
            "project_ids": [project] if project else [], "developer": [developer] if developer else [],
            "month": month, "weight": weight, "ratio": ratio, "received": received,
            "deduction": 0, "performance": str(performance.quantize(Decimal("0.01"))), "note": None}


def flow(amount, project, month="2026-10", kind="款项入账"):
    return {"date": f"{month}-08T10:00:00+08:00", "amount": amount, "type": kind,
            "project_ids": [project] if project else []}


def snapshot(rows, flows, projects=()):
    return {"assignment": rows, "flows": flows, "projects": list(projects)}


class PerformanceChecks(unittest.TestCase):
    def happy(self):
        rows = [row("p-a", "甲", 100, 1, 8000), row("p-b", "乙", 100, 1, 3900),
                row(None, "丙", 100, 2, 11900)]
        return snapshot(rows, [flow(8000, "p-a"), flow(3900, "p-b")],
                        [{"id": "p-a", "name": "示例甲"}, {"id": "p-b", "name": "示例乙"}])

    def test_totals_match_projects_and_company_rows(self):
        result = check(self.happy(), "2026-10")
        self.assertTrue(result["ok"])
        self.assertEqual(result["project_received"], "11900.00")
        self.assertEqual(result["company_received"], "11900.00")
        self.assertEqual(result["totals"], {"丙": "238.00", "乙": "39.00", "甲": "80.00"})
        self.assertEqual(result["total"], "357.00")
        self.assertEqual([item["name"] for item in result["projects"]], ["示例甲", "示例乙"])
        self.assertEqual(result["projects"][0]["pool"], "80.00")

    def test_company_row_double_deduction_is_rejected(self):
        data = self.happy()
        data["assignment"][-1].update(received=10000, performance="200.00")
        with self.assertRaisesRegex(CheckError, "公司级"):
            check(data, "2026-10")

    def test_negative_received_is_rejected(self):
        data = self.happy()
        data["assignment"][-1].update(received=-33300, performance="-666.00")
        with self.assertRaisesRegex(CheckError, "重复扣减"):
            check(data, "2026-10")

    def test_weights_must_sum_to_one_hundred(self):
        data = self.happy()
        data["assignment"].append(row("p-a", "丁", 10, 1, 8000))
        with self.assertRaisesRegex(CheckError, "权重"):
            check(data, "2026-10")

    def test_performance_must_follow_formula(self):
        data = self.happy()
        data["assignment"][0].update(performance="90.00")
        with self.assertRaisesRegex(CheckError, "不一致"):
            check(data, "2026-10")

    def test_receipt_without_row_is_rejected(self):
        data = self.happy()
        data["flows"].append(flow(1234, "p-c"))
        with self.assertRaisesRegex(CheckError, "缺少分配行"):
            check(data, "2026-10")

    def test_negative_received_on_active_row_is_rejected(self):
        data = self.happy()
        data["assignment"].append(row("p-a", "戊", 0, 1, -100))
        with self.assertRaisesRegex(CheckError, "负"):
            check(data, "2026-10")

    def test_retired_rows_stay_zero_but_do_not_block(self):
        data = self.happy()
        data["assignment"].append({"id": "old", "project_ids": [], "developer": ["己"],
                                   "month": "2026-10", "weight": 100, "ratio": 0,
                                   "received": -33300, "deduction": 71200,
                                   "performance": "0.00", "note": "停用"})
        result = check(data, "2026-10")
        self.assertEqual(result["company_received"], "11900.00")

    def test_retired_row_cannot_keep_stale_performance(self):
        data = self.happy()
        data["assignment"].append({"id": "old", "project_ids": [], "developer": ["己"],
                                   "month": "2026-10", "weight": 100, "ratio": 0,
                                   "received": -33300, "deduction": 71200,
                                   "performance": "-666.00", "note": "停用"})
        with self.assertRaisesRegex(CheckError, "停用"):
            check(data, "2026-10")

    def test_row_without_developer_is_rejected(self):
        data = self.happy()
        data["assignment"][0]["developer"] = []
        with self.assertRaisesRegex(CheckError, "开发人员"):
            check(data, "2026-10")

    def test_month_without_rows_is_rejected(self):
        with self.assertRaisesRegex(CheckError, "没有该月记录"):
            check(self.happy(), "2026-11")

    def test_snapshot_without_assignment_is_rejected(self):
        with self.assertRaisesRegex(CheckError, "缺少分配表"):
            check({"flows": []}, "2026-10")

    def test_other_months_and_expenses_are_ignored(self):
        data = self.happy()
        data["flows"].append(flow(5000, "p-old", month="2026-09"))
        data["flows"].append(flow(-3000, "p-a", kind="转款莞云"))
        data["assignment"].append(row("p-old", "庚", 100, 1, 5000, month="2026-09"))
        result = check(data, "2026-10")
        self.assertEqual(result["project_received"], "11900.00")


if __name__ == "__main__":
    unittest.main()
