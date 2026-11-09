import copy
import unittest

from receipt_guard import (CheckError, FIELDS, NET_FORMULA, RECEIVABLE_FORMULA,
                           audit_business, money, net, validate, validate_money, verify)


def fixture():
    fields = [{"id": "field_" + role, "name": name,
               "type": "formula" if role in ("net", "receivable") else "number"}
              for role, name in FIELDS.items()]
    for f in fields:
        if f["name"] == "实收款":
            f["expression"] = NET_FORMULA
        if f["name"] == "待收款项":
            f["expression"] = RECEIVABLE_FORMULA
    fields.append({"id": "project_business", "name": "业务", "type": "select", "multiple": False})
    flow_fields = [{"id": "flow_" + str(i), "name": name, "type": kind}
                   for i, (name, kind) in enumerate({"交易对象": "text", "变动日期": "datetime",
                   "资金变动": "number", "变动类型": "select", "项目收款表": "link", "备注": "text", "业务": "select"}.items())]
    next(f for f in flow_fields if f["name"] == "变动类型")["options"] = [
        {"name": n} for n in ("款项入账", "返点渠道", "转款莞云")]
    schema = {"project": fields, "flow": flow_fields}
    return {
        "schema_before": copy.deepcopy(schema), "schema_current": schema,
        "expected_income_total": "100.10", "excluded_source_ids": ["excluded"],
        "projects": [{"id": "demo", "business": ["示例业务甲"], "received_before": 0, "received": "100.10",
                      "contract_total": "200", "contract_source": "contract:demo",
                      "receivable": "99.90",
                      "channel_paid": "10", "channel_due": "20",
                      "other_paid": "3", "other_due": "4", "net": "63.10"}],
        "flows": [
            {"source_id": "income", "project_id": "demo", "date": "2026-01-01 10:00:00+00:00",
             "counterparty": "示例客户", "amount": "100.10", "type": "款项入账", "business": ["示例业务甲"]},
            {"source_id": "channel", "project_id": "demo", "date": "2026-01-01 11:00:00+00:00",
             "counterparty": "示例渠道", "amount": "-10", "type": "返点渠道", "business": ["示例业务甲"]},
            {"source_id": "other", "project_id": "demo", "date": "2026-01-01 12:00:00+00:00",
             "counterparty": "示例服务方", "amount": "-3", "type": "转款莞云", "business": ["示例业务甲"]}],
        "existing_flows": [],
    }


class MoneyChecks(unittest.TestCase):
    def test_paid_and_due_are_both_deducted(self):
        plan = fixture()
        self.assertEqual(validate_money(plan)["income_total"], "100.10")
        plan["projects"][0]["net"] = "87.10"
        with self.assertRaisesRegex(CheckError, "实收"):
            validate_money(plan)

    def test_moving_due_to_paid_keeps_net(self):
        plan = fixture()
        old_net = net(plan["projects"][0])
        plan["projects"][0].update(channel_paid="30", channel_due="0")
        plan["flows"].append({**plan["flows"][1], "source_id": "paid-later",
                              "date": "2026-01-02 11:00:00+00:00", "amount": "-20"})
        self.assertEqual(net(plan["projects"][0]), old_net)
        validate_money(plan)

    def test_wrong_payment_project_or_total_is_rejected(self):
        for update in ({"channel_paid": "30"}, {"received": "200.10", "net": "163.10"}):
            with self.subTest(update=update):
                plan = fixture()
                plan["projects"][0].update(update)
                with self.assertRaises(CheckError):
                    validate_money(plan)

    def test_duplicate_and_excluded_sources(self):
        for source in ("income", "excluded"):
            plan = fixture()
            duplicate = copy.deepcopy(plan["flows"][0])
            duplicate["source_id"] = source
            plan["flows"].append(duplicate)
            with self.assertRaises(CheckError):
                validate_money(plan)

    def test_existing_payment_cannot_be_replayed(self):
        plan = fixture()
        plan["existing_flows"] = [copy.deepcopy(plan["flows"][1])]
        with self.assertRaisesRegex(CheckError, "重复"):
            validate_money(plan)

    def test_decimal_precision_and_unknown_values(self):
        for value in (True, None, "", "NaN", "Infinity", "0.001"):
            with self.subTest(value=value), self.assertRaises(CheckError):
                money(value)
        self.assertEqual(money("0.10") + money("0.20"), money("0.30"))


class SchemaChecks(unittest.TestCase):
    def test_unchanged_schema_and_reordered_fields(self):
        plan = fixture()
        plan["schema_current"]["project"].reverse()
        validate(plan)

    def test_renamed_field_with_same_id_is_not_safe(self):
        plan = fixture()
        plan["schema_current"]["project"][2]["name"] = "应付渠道全额"
        with self.assertRaisesRegex(CheckError, "结构变化"):
            validate(plan)

    def test_matching_stale_snapshots_do_not_make_old_semantics_valid(self):
        plan = fixture()
        for schema in (plan["schema_before"], plan["schema_current"]):
            schema["project"][2]["name"] = "返点渠道"
        with self.assertRaisesRegex(CheckError, "语义"):
            validate(plan)

    def test_changed_formula_or_type_is_detected(self):
        for key, value in (("type", "text"), ("expression", "[已收款项]")):
            plan = fixture()
            plan["schema_current"]["project"][-2][key] = value
            with self.assertRaises(CheckError):
                validate(plan)

    def test_formula_must_deduct_all_obligations_once(self):
        plan = fixture()
        for schema in (plan["schema_before"], plan["schema_current"]):
            next(f for f in schema["project"] if f["name"] == "实收款")["expression"] = "[已收款项]-[已返点渠道]-[已转款莞云/其他]"
        with self.assertRaisesRegex(CheckError, "实收公式"):
            validate(plan)

    def test_missing_flow_options_are_rejected(self):
        plan = fixture()
        for schema in (plan["schema_before"], plan["schema_current"]):
            next(f for f in schema["flow"] if f["name"] == "变动类型")["options"] = []
        with self.assertRaisesRegex(CheckError, "分类选项"):
            validate(plan)


class ReceivableChecks(unittest.TestCase):
    def test_unknown_total_stays_unknown_with_blank_guard(self):
        plan = fixture()
        plan["projects"][0].update(contract_total=None, receivable=None)
        validate(plan)

    def test_unknown_total_cannot_generate_negative_receivable(self):
        plan = fixture()
        plan["projects"][0].update(contract_total=None, receivable="-100.10")
        with self.assertRaisesRegex(CheckError, "留空"):
            validate(plan)


class ReadbackChecks(unittest.TestCase):
    def after(self, plan):
        return {"schema": copy.deepcopy(plan["schema_current"]),
                "projects": copy.deepcopy(plan["projects"]), "flows": copy.deepcopy(plan["flows"])}

    def test_successful_readback_and_resolved_new_project_id(self):
        plan = fixture()
        after = self.after(plan)
        after["projects"][0]["id"] = "server-record"
        for row in after["flows"]:
            row["project_id"] = "server-record"
        plan["id_map"] = {"demo": "server-record"}
        self.assertEqual(verify(plan, after)["verified_flows"], 3)

    def test_wrong_link_or_double_write_is_rejected(self):
        for mode in ("link", "duplicate", "amount"):
            plan = fixture()
            after = self.after(plan)
            if mode == "link":
                after["flows"][0]["project_id"] = "wrong"
            elif mode == "duplicate":
                after["flows"].append(copy.deepcopy(after["flows"][0]))
            else:
                after["projects"][0]["net"] = 999
            with self.subTest(mode=mode), self.assertRaises(CheckError):
                verify(plan, after)

    def test_equivalent_timestamp_and_amount_cannot_evade_dedup(self):
        plan = fixture()
        existing = copy.deepcopy(plan["flows"][1])
        existing.update(source_id="different-id", amount="-10.00", date="2026-01-01T19:00:00+08:00")
        plan["existing_flows"] = [existing]
        with self.assertRaisesRegex(CheckError, "重复"):
            validate(plan)


class BusinessChecks(unittest.TestCase):
    def snapshot(self):
        plan = fixture()
        return {"projects": plan["projects"], "flows": plan["flows"]}

    def test_user_adjusted_project_requires_rechecking_historical_flows(self):
        snapshot = self.snapshot()
        snapshot["projects"][0]["business"] = ["示例业务乙"]
        result = audit_business(snapshot)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["issues"]), 3)

    def test_missing_flow_business_is_not_considered_a_match(self):
        plan = fixture()
        plan["flows"][0]["business"] = []
        with self.assertRaisesRegex(CheckError, "流水业务"):
            validate(plan)

    def test_missing_project_business_is_not_masked_by_manual_flow_value(self):
        snapshot = self.snapshot()
        snapshot["projects"][0]["business"] = []
        self.assertEqual(audit_business(snapshot)["issues"][0]["issue"], "project_business_missing")

    def test_unlinked_manual_business_is_kept_but_multiple_projects_are_reported(self):
        snapshot = self.snapshot()
        snapshot["flows"][0].update(project_id=None, business=["历史手填业务"])
        self.assertTrue(audit_business(snapshot)["ok"])
        snapshot["flows"][0]["project_ids"] = ["demo", "another"]
        self.assertEqual(audit_business(snapshot)["issues"][0]["issue"], "multiple_projects")

    def test_formula_text_matches_project_select_and_readback_rejects_stale_value(self):
        plan = fixture()
        after = {"schema": copy.deepcopy(plan["schema_current"]), "projects": copy.deepcopy(plan["projects"]),
                 "flows": copy.deepcopy(plan["flows"])}
        for f in after["flows"]:
            f["business"] = "示例业务甲"
        verify(plan, after)
        after["flows"][0]["business"] = "示例业务乙"
        with self.assertRaisesRegex(CheckError, "流水业务"):
            verify(plan, after)

    def test_contradictory_link_list_cannot_bypass_business_check(self):
        snapshot = self.snapshot()
        snapshot["flows"][0]["project_ids"] = []
        with self.assertRaisesRegex(CheckError, "关联列表"):
            audit_business(snapshot)

    def test_old_receivable_formula_blocks_unknown_project(self):
        plan = fixture()
        plan["projects"][0].update(contract_total=None, receivable=None)
        for schema in (plan["schema_before"], plan["schema_current"]):
            next(f for f in schema["project"] if f["name"] == "待收款项")["expression"] = "[收款总额/项目金额]-[已收款项]"
        with self.assertRaisesRegex(CheckError, "先只记流水"):
            validate(plan)

    def test_deposit_is_not_contract_total(self):
        plan = fixture()
        plan["projects"][0].update(contract_total="100.10", receivable="0", contract_source="bank:income")
        with self.assertRaisesRegex(CheckError, "合同总额需"):
            validate(plan)

    def test_current_receipt_does_not_clear_unpaid_half(self):
        plan = fixture()
        plan["projects"][0]["receivable"] = 0
        with self.assertRaisesRegex(CheckError, "待收金额"):
            validate(plan)


if __name__ == "__main__":
    unittest.main()
