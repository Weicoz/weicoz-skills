import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wx_preflight import financial_messages, locate_wrapper, preflight, redact, run


class WechatChecks(unittest.TestCase):
    def test_resolve_library_when_generated_stub_has_no_script(self):
        with tempfile.TemporaryDirectory() as home:
            target = Path(home) / ".agents/skill-tiers/library/wx-cli/scripts/wx.sh"
            target.parent.mkdir(parents=True)
            target.write_text("#!/bin/sh\n")
            self.assertEqual(locate_wrapper(home=home), target.resolve())

    def test_stopped_daemon_does_not_start_or_query(self):
        calls = []
        def runner(wrapper, args):
            calls.append(args)
            return {"ok": True, "text": "wx-daemon 未运行"}
        self.assertEqual(preflight("unused", "示例会话", runner=runner)["service"], "blocked")
        self.assertEqual(calls, [["daemon", "status"]])

    def test_text_success_is_not_image_success_and_failure_stops_batch(self):
        calls = []
        def runner(wrapper, args):
            calls.append(args)
            if args[0] == "daemon":
                return {"ok": True, "text": "wx-daemon 运行中"}
            if args[0] == "history":
                return {"ok": True, "data": {"messages": []}}
            if args[0] == "attachments":
                return {"ok": True, "data": {"attachments": [{"attachment_id": "one"}, {"attachment_id": "two"}]}}
            return {"ok": False, "reason": "key_validation_failed"}
        result = preflight("unused", "示例会话", runner=runner)
        self.assertEqual(result["text"], "ok")
        self.assertEqual(result["images"], "blocked")
        self.assertEqual(result["extract_attempts"], 1)
        self.assertEqual(sum(c[0] == "extract" for c in calls), 1)

    def test_empty_image_window_remains_unverified(self):
        def runner(wrapper, args):
            return {"ok": True, "text": "wx-daemon 运行中", "data": {"attachments": []}}
        result = preflight("unused", "示例会话", runner=runner)
        self.assertEqual(result["images"], "no_sample")
        self.assertEqual(result["extract_attempts"], 0)

    def test_cli_success_without_file_is_not_success(self):
        def runner(wrapper, args):
            return {"ok": True, "text": "wx-daemon 运行中", "data": {"attachments": [{"attachment_id": "one"}]}}
        self.assertEqual(preflight("unused", "示例会话", runner=runner)["images"], "blocked")

    def test_real_image_probe_file_is_cleaned_up(self):
        outputs = []
        def runner(wrapper, args):
            if args[0] == "extract":
                path = Path(args[args.index("--output") + 1])
                path.write_bytes(b"\xff\xd8\xffsample")
                outputs.append(path)
            return {"ok": True, "text": "wx-daemon 运行中", "data": {"attachments": [{"attachment_id": "one"}]}}
        self.assertEqual(preflight("unused", "示例会话", runner=runner)["images"], "ok")
        self.assertFalse(outputs[0].exists())

    def test_non_image_output_and_malformed_messages_are_rejected(self):
        def runner(wrapper, args):
            if args[0] == "extract":
                Path(args[args.index("--output") + 1]).write_bytes(b"not-an-image")
            return {"ok": True, "text": "wx-daemon 运行中", "data": {"attachments": [{"attachment_id": "one"}]}}
        self.assertEqual(preflight("unused", "示例会话", runner=runner)["images"], "blocked")
        with self.assertRaises(ValueError):
            financial_messages({"messages": ["raw-sensitive-text"]})

    def test_raw_xml_credentials_and_irrelevant_chats_are_omitted(self):
        payload = {"messages": [
            {"content": "<?xml version='1.0'?><msg>项目后台密码\nopaque-value</msg>"},
            {"content": "验证码 123456，已收到"},
            {"content": "今天去吃饭"},
            {"content": "项目尾款100元，电话13800000000，账户1234567890123456789"},
            {"type_id": "image", "content": "[图片]", "local_id": 8}]}
        result = financial_messages(payload)
        self.assertEqual(len(result), 2)
        self.assertIn("[手机号]", result[0]["content"])
        self.assertNotIn("1234567890123456789", json.dumps(result))
        self.assertFalse(result[1]["image_verified"])

    def test_error_details_do_not_leak(self):
        proc = subprocess.CompletedProcess([], 1, "", "HMAC /private/account raw-sensitive-text")
        with patch("wx_preflight.subprocess.run", return_value=proc):
            result = run("unused", ["extract", "opaque"])
        self.assertEqual(result, {"ok": False, "reason": "key_validation_failed"})


if __name__ == "__main__":
    unittest.main()
