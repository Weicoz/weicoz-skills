import unittest

from salary_month import MonthError, records, render

FIELDS = ["文本", "时间", "姓名", "基本薪资", "应缴社保", "个税", "应上天数", "实上天数",
          "请假小时", "加班天数", "绩效奖金", "补贴", "实发薪资"]


def config():
    return {"token": "example-token", "table": "example-table", "time": "时间", "columns": FIELDS}


def page(rows, ids, has_more=False, fields=None):
    return {"fields": fields or FIELDS, "data": rows, "record_id_list": ids, "has_more": has_more}


class SalaryMonth(unittest.TestCase):
    def test_keeps_only_requested_month_and_totals_net(self):
        rows = [["202609-甲", "202609", ["甲"], 8000, 414.93, 385.07, 24, 24, 0, 0, 100, 0, "7300.00"],
                ["202610-甲", "202610", ["甲"], 8000, None, None, 19, 19, 0, 0, None, 63.7, "8063.70"],
                ["202610-乙", "202610", ["乙"], 5500, None, None, 19, 18.5, 3.75, 0, None, 763.67, "6118.93"]]
        pages = [page(rows, ["r1", "r2", "r3"])]
        output, selected = render("202610", records(config(), lambda args: pages.pop(0)), FIELDS)
        self.assertEqual(len(selected), 2)
        self.assertNotIn("202609-甲", output)
        self.assertIn("共 2 人｜实发薪资合计 14182.63", output)

    def test_paginates_until_done(self):
        first = page([["a", "202610", ["甲"], 1, 1, 1, 1, 1, 0, 0, 1, 1, "1.00"]], ["r1"], has_more=True)
        second = page([["b", "202610", ["乙"], 1, 1, 1, 1, 1, 0, 0, 1, 1, "2.00"]], ["r2"])
        calls = []

        def runner(args):
            calls.append(args)
            return [first, second][len(calls) - 1]

        rows = records(config(), runner)
        self.assertEqual([row["文本"] for row in rows], ["a", "b"])
        self.assertEqual(calls[1][calls[1].index("--offset") + 1], "1")

    def test_missing_record_ids_are_rejected(self):
        bad = page([["a", "202610", ["甲"], 1, 1, 1, 1, 1, 0, 0, 1, 1, "1.00"]], [])
        with self.assertRaisesRegex(MonthError, "记录 ID"):
            records(config(), lambda args: bad)


if __name__ == "__main__":
    unittest.main()
