import json
from pathlib import Path
import tempfile
import unittest

from send_notices import NoticeError, deliver, plan, recall, render, verify

TEMPLATE = "【{title}】\n个人应承担合计 {amount} 元。\n明细：{span}（{detail}）。"
TITLE = "社保补缴个人部分｜2026 年"


def document(items, template=TEMPLATE):
    return {"title": TITLE, "template": template, "month": "202610", "items": items}


def item(name, amount="531.84", span="2026 年 1–9 月", detail="58.80 元/月"):
    return {"name": name, "amount": amount, "span": span, "detail": detail}


class TextChecks(unittest.TestCase):
    def test_render_rejects_unknown_placeholder(self):
        with self.assertRaisesRegex(NoticeError, "占位符"):
            render(item("甲"), "【{missing}】{name}", TITLE)


class PlanChecks(unittest.TestCase):
    def plan(self, items, payroll=("甲", "乙"), month=("甲", "乙"), source=None, template=TEMPLATE):
        return plan(document(items, template), set(payroll), set(month), source)

    def test_valid_items_pass(self):
        planned, issues = self.plan([item("甲"), item("乙", "294.00")])
        self.assertEqual(issues, [])
        self.assertEqual([p["amount"] for p in planned], ["531.84", "294.00"])
        self.assertIn("个人应承担合计 531.84 元", planned[0]["text"])

    def test_double_space_is_rejected(self):
        planned, issues = self.plan([item("甲")], template="【{title}】\n合计  {amount} 元。")
        self.assertEqual(planned, [])
        self.assertEqual(issues[0]["issue"], "文案异常：连续空格")

    def test_leftover_placeholder_is_rejected(self):
        # 占位符写成 {{x}} 会留下字面量 {x}，必须在发送前拦下。
        planned, issues = self.plan([item("甲")], template="【{title}】\n{amount} 元 {{unknown}}")
        self.assertEqual(planned, [])
        self.assertIn("未替换占位符", issues[0]["issue"])

    def test_person_outside_payroll_is_blocked(self):
        planned, issues = self.plan([item("丙")])
        self.assertEqual(issues[0]["issue"], "名单外人员")

    def test_person_without_month_row_is_blocked(self):
        planned, issues = self.plan([item("乙")], month=("甲",))
        self.assertEqual(issues[0]["issue"], "当月无工资行，不能代扣")

    def test_amount_must_match_source(self):
        planned, issues = self.plan([item("甲")], source={"甲": "500.00"})
        self.assertEqual(issues[0]["issue"], "金额与源数据不一致")

    def test_duplicate_and_bad_amount(self):
        _, issues = self.plan([item("甲"), item("甲")])
        self.assertEqual(issues[0]["issue"], "重复收件人")
        _, issues = self.plan([item("甲", "531.845")])
        self.assertEqual(issues[0]["issue"], "金额格式无效")


class DeliveryChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / "notices"

    def runner(self, calls):
        def run(args):
            calls.append(args)
            if args[:2] == ["contact", "+search-user"]:
                name = args[args.index("--query") + 1]
                return {"ok": True, "data": {"users": [{"localized_name": name, "open_id": "ou_" + name}]}}
            if args[:2] == ["im", "+messages-send"]:
                return {"ok": True, "data": {"message_id": f"om_{len(calls)}", "chat_id": "oc_x",
                                             "create_time": "2026-11-11 23:49"}}
            if args[:3] == ["im", "messages", "delete"]:
                return {"ok": True, "data": {}}
            raise AssertionError(args)
        return run

    def test_staging_sends_only_one_and_records_batch(self):
        calls = []
        planned, _ = plan(document([item("甲"), item("乙")]), {"甲", "乙"}, {"甲", "乙"})
        batch, path = deliver(planned, self.runner(calls), "202610", TITLE, self.state, staging="甲")
        self.assertEqual([m["name"] for m in batch["messages"]], ["甲"])
        sends = [c for c in calls if c[:2] == ["im", "+messages-send"]]
        self.assertEqual(len(sends), 1)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["messages"][0]["name"], "甲")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_recipient_must_be_exact_match(self):
        def runner(args):
            if args[:2] == ["contact", "+search-user"]:
                return {"ok": True, "data": {"users": [{"localized_name": "甲某", "open_id": "ou_x"}]}}
            raise AssertionError(args)

        planned, _ = plan(document([item("甲")]), {"甲"}, {"甲"})
        with self.assertRaisesRegex(NoticeError, "唯一"):
            deliver(planned, runner, "202610", TITLE, self.state)

    def test_recall_requires_confirm_then_deletes(self):
        calls = []
        planned, _ = plan(document([item("甲"), item("乙")]), {"甲", "乙"}, {"甲", "乙"})
        _, path = deliver(planned, self.runner(calls), "202610", TITLE, self.state)
        pending = recall(path, self.runner(calls))
        self.assertTrue(pending["need_confirm"])
        self.assertEqual(len(pending["pending"]), 2)
        self.assertFalse([c for c in calls if c[:3] == ["im", "messages", "delete"]])
        done = recall(path, self.runner(calls), confirm=True)
        self.assertTrue(done["ok"])
        self.assertEqual(len([c for c in calls if c[:3] == ["im", "messages", "delete"]]), 2)

    def test_verify_reads_back_with_one_batch_call(self):
        calls = []
        planned, _ = plan(document([item("甲"), item("乙")]), {"甲", "乙"}, {"甲", "乙"})
        batch, path = deliver(planned, self.runner(calls), "202610", TITLE, self.state)
        texts = {m["message_id"]: m["text"] for m in batch["messages"]}

        def runner(args):
            calls.append(args)
            ids = args[args.index("--message-ids") + 1].split(",")
            return {"ok": True, "data": {"messages": [
                {"message_id": i, "deleted": False, "content": texts[i]} for i in ids]}}

        result = verify(path, runner)
        self.assertTrue(result["ok"])
        self.assertEqual(len([c for c in calls if c[:2] == ["im", "+messages-mget"]]), 1)

    def test_batch_file_needs_messages(self):
        empty = Path(self.directory.name) / "empty.json"
        empty.write_text('{"messages": []}', encoding="utf-8")
        with self.assertRaisesRegex(NoticeError, "没有消息"):
            recall(empty, self.runner([]))


if __name__ == "__main__":
    unittest.main()
