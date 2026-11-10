from pathlib import Path
import tempfile
import unittest

from extract_attendance_xlsx import ExtractError, extract

try:
    import openpyxl  # noqa: F401
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

HEADER = ["姓名", "应出勤天数", "应出勤时长（小时）", "实际出勤天数", "实际出勤时长（小时）", "补贴", "备注"]


def make_book(path, summary, detail=None):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "2026年10月考勤统计"
    sheet.append(["2026年10月考勤统计"])
    sheet.append(HEADER)
    for row in summary:
        sheet.append(row)
    if detail is not None:
        detail_sheet = workbook.create_sheet("统计明细")
        detail_sheet.append(["姓名", "日期", "应出勤标记", "实际出勤标记"])
        for row in detail:
            detail_sheet.append(row)
    workbook.save(path)


@unittest.skipUnless(HAS_OPENPYXL, "需要 openpyxl 才能构造测试工作簿")
class AttendanceExtract(unittest.TestCase):
    def build(self, summary, detail=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "attendance.xlsx"
        make_book(path, summary, detail)
        return path

    def test_reads_summary_and_derives_leave_hours(self):
        path = self.build([["甲", 19, 142.5, 18, 135, 63.7, "额度补贴"],
                           ["乙", 19, 142.5, 19, 142.5, None, None]],
                          [["甲", "2026-10-08", 1, 1]] * 18 + [["乙", "2026-10-08", 1, 1]] * 19)
        result = extract(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["month"], "202610")
        first, second = result["people"]
        self.assertEqual((first["due_days"], first["actual_days"]), ("19", "18"))
        self.assertEqual(first["leave_hours"], "7.50")
        self.assertEqual(first["allowance"], "63.7")
        self.assertIsNone(second["allowance"])

    def test_detail_mismatch_blocks_without_flag(self):
        path = self.build([["甲", 19, 142.5, 19, 142.5, 10, ""]],
                          [["甲", "2026-10-08", 1, 1]] * 13)
        result = extract(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["mismatched"][0]["detail"], "13")
        self.assertTrue(extract(path, allow_detail_mismatch=True)["ok"])

    def test_hours_fallback_uses_seven_and_a_half(self):
        path = self.build([["甲", 19, None, 18, None, 0, ""]], [["甲", "2026-10-08", 1, 1]] * 18)
        self.assertEqual(extract(path)["people"][0]["leave_hours"], "7.50")

    def test_missing_summary_header_is_rejected(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "bad.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(["姓名", "备注"])
        workbook.save(path)
        with self.assertRaises(ExtractError):
            extract(path)


if __name__ == "__main__":
    unittest.main()
