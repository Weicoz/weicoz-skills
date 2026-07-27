#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
EXAMPLES = ROOT / "references" / "examples.md"
EVALS = ROOT / "evals" / "evals.json"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"{label} missing: {needle}")


def main() -> None:
    for path in (SKILL, EXAMPLES, EVALS):
        if not path.exists():
            fail(f"missing file: {path}")

    skill = SKILL.read_text(encoding="utf-8")
    examples = EXAMPLES.read_text(encoding="utf-8")
    evals = json.loads(EVALS.read_text(encoding="utf-8"))

    frontmatter = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
    if not frontmatter:
        fail("SKILL.md frontmatter missing")

    header = frontmatter.group(1)
    require(header, "name: weicoz-wechat-official-account-operator", "frontmatter")
    require(header, "description:", "frontmatter")

    required_skill_terms = [
        "账号定位",
        "目标读者",
        "业务目标",
        "选题",
        "标题",
        "大纲",
        "正文改写",
        "发布计划",
        "增长",
        "复盘",
        "缺信息",
        "不要编造",
        "需要联网核验",
        "事实边界",
        "个人 IP",
        "电商",
        "本地生活",
        "高合规",
    ]
    for term in required_skill_terms:
        require(skill, term, "SKILL.md")

    for heading in ("样例 1：缺信息输入", "样例 2：选题输入", "样例 3：正文改写输入"):
        require(examples, heading, "examples.md")

    if evals.get("skill_name") != "weicoz-wechat-official-account-operator":
        fail("evals.json skill_name mismatch")

    expected_ids = {
        "positioning",
        "topics",
        "titles",
        "outline",
        "rewrite",
        "publish-plan",
        "review",
        "missing-info",
        "personal-ip",
        "ecommerce-local",
        "enterprise-service",
        "high-compliance",
    }
    seen_ids = {item.get("id") for item in evals.get("evals", [])}
    missing = expected_ids - seen_ids
    if missing:
        fail(f"eval coverage missing: {', '.join(sorted(missing))}")

    for item in evals.get("evals", []):
        if not item.get("prompt") or not item.get("expected_output"):
            fail(f"eval item incomplete: {item.get('id')}")

    print("PASS: frontmatter")
    print("PASS: workflow coverage")
    print("PASS: no-fabrication guard")
    print("PASS: examples coverage")
    print("PASS: eval sample coverage")


if __name__ == "__main__":
    main()
