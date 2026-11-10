from pathlib import Path
import tempfile
import unittest

from lark_snapshot import Reader, save_private
from receipt_guard import BUSINESS_BINDING_FORMULA, CheckError


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
                    "交易对象", "变动日期", "资金变动", "变动类型", "关联项目", "业务"]
                return [{"id": str(i), "name": n, "type": "link" if n == "关联项目" else "text"}
                        for i, n in enumerate(names)]

            def records(self, table, fields):
                assert "业务" in fields
                if table == "project":
                    return [{"id": "p", "项目": "示例项目", "业务": ["示例业务甲"]}]
                return [{"id": "f", "交易对象": "示例客户", "变动日期": "2026-01-01T10:00:00+00:00",
                         "资金变动": 100, "变动类型": ["款项入账"], "业务": "示例业务甲",
                         "关联项目": [{"id": "p"}, {"id": "other"}]}]

        snapshot = Source({}).snapshot()
        self.assertEqual(snapshot["projects"][0]["business"], ["示例业务甲"])
        self.assertEqual(snapshot["flows"][0]["business"], ["示例业务甲"])
        self.assertEqual(snapshot["flows"][0]["project_ids"], ["p", "other"])
        self.assertIsNone(snapshot["flows"][0]["project_id"])

    def test_formula_snapshot_reads_manual_backup(self):
        class Source(Reader):
            def fields(self, table):
                if table == "project":
                    return [{"id": "p", "name": "项目", "type": "text"},
                            {"id": "pb", "name": "业务", "type": "select"}]
                names = ("交易对象", "变动日期", "资金变动", "变动类型", "关联项目", "业务", "业务（手填）")
                fields = [{"id": str(i), "name": name,
                           "type": "link" if name == "关联项目" else "text"} for i, name in enumerate(names)]
                fields[-2].update(type="formula", expression=BUSINESS_BINDING_FORMULA)
                fields[-1].update(type="select", multiple=False)
                return fields

            def records(self, table, fields):
                if table == "project":
                    return [{"id": "p", "项目": "示例项目", "业务": ["示例业务甲"]}]
                if "业务（手填）" not in fields:
                    raise AssertionError("快照漏读手填备份字段")
                return [{"id": "f", "交易对象": "示例客户", "变动日期": "2026-01-01T10:00:00+00:00",
                         "资金变动": 100, "关联项目": [], "变动类型": ["款项入账"],
                         "业务": "示例业务甲", "业务（手填）": "示例业务甲"}]

        snapshot = Source({}).snapshot()
        self.assertEqual(snapshot["flows"][0]["business"], ["示例业务甲"])
        self.assertEqual(snapshot["flows"][0]["business_manual"], ["示例业务甲"])


    def test_assignment_snapshot_normalizes_links_and_people(self):
        class Source(Reader):
            def fields(self, table):
                self.assert_table = table
                return [{"id": str(i), "name": name, "type": kind}
                        for i, (name, kind) in enumerate({
                            "项目": "link", "开发人员": "select", "权重(%)": "number",
                            "绩效比例(%)": "number", "生效月份": "text", "备注": "text",
                            "当月实收": "formula", "返点及转款扣减": "formula",
                            "绩效金额": "formula"}.items())]

            def records(self, table, fields):
                return [{"id": "a1", "项目": [{"id": "p-a"}], "开发人员": ["甲"], "权重(%)": 100,
                         "绩效比例(%)": 1, "生效月份": "2026-10", "备注": None,
                         "当月实收": "8000", "返点及转款扣减": "0", "绩效金额": "80"}]

        source = Source({})
        data = source.assignment()
        self.assertEqual(source.assert_table, "assignment")
        self.assertEqual(data["assignment"][0]["project_ids"], ["p-a"])
        self.assertEqual(data["assignment"][0]["developer"], ["甲"])
        self.assertEqual(data["assignment"][0]["performance"], "80")

    def test_assignment_snapshot_rejects_changed_field_types(self):
        class Source(Reader):
            def fields(self, table):
                return [{"id": "1", "name": "项目", "type": "text"}]

            def records(self, table, fields):
                raise AssertionError("字段语义不符时不应读记录")

        with self.assertRaisesRegex(CheckError, "字段"):
            Source({}).assignment()


if __name__ == "__main__":
    unittest.main()
