#!/usr/bin/env python3
"""微信收款证据只读预检及消息脱敏；不启动服务、不取钥、不触碰客户端。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def locate_wrapper(skill_dir=None, home=None):
    root = Path(home) if home is not None else Path.home()
    candidates = [Path(skill_dir)] if skill_dir else [
        root / ".agents/skills/wx-cli", root / ".agents/skill-tiers/library/wx-cli"]
    for directory in candidates:
        wrapper = directory.resolve() / "scripts/wx.sh"
        if wrapper.is_file():
            return wrapper
    raise FileNotFoundError("未找到 wx-cli/scripts/wx.sh；指定 --wx-skill-dir 为真实 Skill 目录")


def run(wrapper, args):
    try:
        proc = subprocess.run(["bash", str(wrapper), *args], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "reason": "timeout_or_unavailable"}
    if proc.returncode:
        error = proc.stderr + proc.stdout
        reason = "key_validation_failed" if any(s in error for s in ("HMAC", "密钥", "页头校验")) else "query_failed"
        # 仅输出错误分类；原始错误中可能有路径、正文或密钥提示。
        return {"ok": False, "reason": reason}
    try:
        return {"ok": True, "data": json.loads(proc.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "text": proc.stdout}


def preflight(wrapper, chat=None, since=None, until=None, runner=run):
    result = {"wrapper": str(Path(wrapper).resolve()), "service": "unverified",
              "text": "unverified", "images": "unverified", "extract_attempts": 0}
    status = runner(wrapper, ["daemon", "status"])
    description = status.get("text", "")
    if not status["ok"] or "未运行" in description or "运行中" not in description:
        result["service"] = "blocked"
        result["reason"] = "daemon_not_confirmed_running"
        return result
    result["service"] = "ok"
    if not chat:
        return result
    window = []
    for flag, value in (("--since", since), ("--until", until)):
        if value:
            window.extend([flag, value])
    history = runner(wrapper, ["history", chat, *window, "--limit", "1", "--json"])
    result["text"] = "ok" if history["ok"] and isinstance(history.get("data"), dict) else "blocked"
    if result["text"] != "ok":
        result["reason"] = history.get("reason", "history_unavailable")
    attachments = runner(wrapper, ["attachments", chat, *window, "--kind", "image", "--limit", "1", "--json"])
    if not attachments["ok"]:
        result.update(images="blocked", image_reason=attachments.get("reason", "attachments_unavailable"))
        return result
    data = attachments.get("data")
    if not isinstance(data, dict):
        result.update(images="blocked", image_reason="attachments_response_invalid")
        return result
    items = data.get("attachments", [])
    if not items:
        result.update(images="no_sample", image_reason="当前时间窗无图片样本，不能证明图片可读取")
        return result
    if not isinstance(items, list) or not isinstance(items[0], dict) or not items[0].get("attachment_id"):
        result.update(images="blocked", image_reason="attachment_id_missing")
        return result
    # 只验证一个样本；首次失败后结束此批图片预检，不换图片重复取钥错误。
    with tempfile.TemporaryDirectory(prefix="receipt-wx-") as directory:
        output = Path(directory) / "probe.jpg"
        extract = runner(wrapper, ["extract", items[0]["attachment_id"], "--output", str(output), "--json"])
        result["extract_attempts"] = 1
        header = output.read_bytes()[:12] if output.is_file() else b""
        image_file = header.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")) or (
            header.startswith(b"RIFF") and header[8:12] == b"WEBP")
        success = extract["ok"] and image_file
        result["images"] = "ok" if success else "blocked"
        if not success:
            result["image_reason"] = extract.get("reason", "supported_image_file_not_produced")
    return result


def redact(text):
    value = str(text or "")
    if re.search(r"密码|口令|验证码|后台账号|后台账户|password|secret|token|api[_ -]?key|<\?xml|<msg\b|<recordinfo", value, re.I):
        return "[含凭据或原始结构的消息已省略]"
    value = re.sub(r"https?://\S+", "[链接]", value)
    value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", value)
    value = re.sub(r"(?<!\d)(?:\d[ -]?){15,}\d(?!\d)", "[长编号]", value)
    value = re.sub(r"(?:sk-|ghp_|github_pat_)[\w-]{8,}", "[凭据]", value)
    return value


def financial_messages(payload, keywords=()):
    if not isinstance(payload, (list, dict)):
        raise ValueError("消息根结构无效")
    rows = payload if isinstance(payload, list) else payload.get("messages", payload.get("results", []))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("消息列表结构无效")
    result = []
    for message in rows:
        content = str(message.get("content", ""))
        kind = message.get("type_id", "")
        is_image = kind == "image" or message.get("type") == "图片"
        if not is_image and not re.search(r"款|付|转账|返点|收到|合同|项目|元|万|千", content) and not any(k in content for k in keywords):
            continue
        safe = redact(content)
        if safe.startswith("[含凭据"):
            continue
        result.append({key: redact(message.get(key)) for key in ("chat", "sender", "time")})
        result[-1].update(local_id=message.get("local_id"), type=kind,
                          content=safe[:600], image_verified=False if is_image else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--wx-skill-dir", type=Path)
    check.add_argument("--chat")
    check.add_argument("--since")
    check.add_argument("--until")
    clean = sub.add_parser("messages")
    clean.add_argument("input", type=Path)
    clean.add_argument("--keyword", action="append", default=[])
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = preflight(locate_wrapper(args.wx_skill_dir), args.chat, args.since, args.until)
        else:
            result = financial_messages(json.loads(args.input.read_text(encoding="utf-8")), args.keyword)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if isinstance(result, dict) and (result["service"] == "blocked" or result["text"] == "blocked" or result["images"] == "blocked") else 0
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"ok": False, "error": "入口、输入文件或响应结构无效；未输出原始正文"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
