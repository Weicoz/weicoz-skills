from pathlib import Path
import tempfile
import unittest

from lark_snapshot import Reader, save_private
from receipt_guard import CheckError


class SnapshotChecks(unittest.TestCase):
    def reader(self, responses, sleeps=None):
        calls = []
        def runner(args):
            calls.append(args)
            return responses.pop(0)
        return Reader({"token": "example-token", "project_table": "example-project",
                       "flow_table": "example-flow"}, runner, (sleeps if sleeps is not None else []).append), calls

    def test_bounded_read_only_rate_limit_retry(self):
        sleeps = []
        reader, calls = self.reader([{"ok": False, "error": {"subtype": "rate_limit"}},
                                    {"ok": True, "data": {"fields": []}}], sleeps)
        reader.call("+field-list", "project", [])
        self.assertEqual(sleeps, [1])
        self.assertEqual(len(calls), 2)
        with self.assertRaises(CheckError):
            reader.call("+record-batch-create", "project", [])

    def test_retry_limit_and_other_errors_do_not_loop(self):
        for subtype, count in (("rate_limit", 3), ("api", 1)):
            reader, calls = self.reader([{"ok": False, "error": {"subtype": subtype}}] * count)
            with self.assertRaises(CheckError):
                reader.call("+record-list", "flow", [])
            self.assertEqual(len(calls), count)

    def test_pagination_uses_response_field_order_and_ids(self):
        reader, calls = self.reader([
            {"ok": True, "data": {"data": [[10, "甲"]], "record_id_list": ["one"],
                                  "fields": ["金额", "项目"], "has_more": True}},
            {"ok": True, "data": {"data": [["乙", 20]], "record_id_list": ["two"],
                                  "fields": ["项目", "金额"], "has_more": False}}])
        rows = reader.records("project", ["项目", "金额"])
        self.assertEqual(rows, [{"id": "one", "项目": "甲", "金额": 10},
                                {"id": "two", "项目": "乙", "金额": 20}])
        self.assertEqual(calls[1][calls[1].index("--offset") + 1], "1")

    def test_repeated_records_or_missing_ids_fail(self):
        page = {"ok": True, "data": {"data": [[1]], "record_id_list": ["same"],
                                      "fields": ["金额"], "has_more": True}}
        reader, calls = self.reader([page, page])
        with self.assertRaisesRegex(CheckError, "ID"):
            reader.records("project", ["金额"])
        self.assertEqual(len(calls), 2)

    def test_repeated_field_pages_fail_before_an_infinite_loop(self):
        page = {"ok": True, "data": {"fields": [{"id": "same"}], "has_more": True}}
        reader, calls = self.reader([page, page])
        with self.assertRaisesRegex(CheckError, "分页重复"):
            reader.fields("project")
        self.assertEqual(len(calls), 2)

    def test_private_snapshot_permissions_and_repository_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = save_private(root / "config.yaml", {"schema": {}, "projects": [], "flows": []})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            (root / ".git").mkdir()
            with self.assertRaisesRegex(CheckError, "Git"):
                save_private(root / "config.yaml", {})

    def test_snapshot_reads_business_on_both_sides_and_keeps_full_links(self):
        class Source(Reader):
            def fields(self, table):
                names = ["项目", "业务"] if table == "project" else [
                    "交易对象", "变动日期", "资金变动", "变动类型", "项目收款表", "业务"]
                return [{"id": str(i), "name": n, "type": "text"} for i, n in enumerate(names)]

            def records(self, table, fields):
                assert "业务" in fields
                if table == "project":
                    return [{"id": "p", "项目": "示例项目", "业务": ["示例业务甲"]}]
                return [{"id": "f", "交易对象": "示例客户", "变动日期": "2026-01-01T10:00:00+00:00",
                         "资金变动": 100, "变动类型": ["款项入账"], "业务": "示例业务甲",
                         "项目收款表": [{"id": "p"}, {"id": "other"}]}]

        snapshot = Source({}).snapshot()
        self.assertEqual(snapshot["projects"][0]["business"], ["示例业务甲"])
        self.assertEqual(snapshot["flows"][0]["business"], ["示例业务甲"])
        self.assertEqual(snapshot["flows"][0]["project_ids"], ["p", "other"])
        self.assertIsNone(snapshot["flows"][0]["project_id"])


if __name__ == "__main__":
    unittest.main()
