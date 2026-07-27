#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))


def require(name, ok):
    if not ok:
        raise SystemExit(f"FAIL: {name}")
    print(f"PASS: {name}")


require("frontmatter", skill.startswith("---\nname: weicoz-wechat-article-writer"))
require("article-only boundary", "不要把任务泛化成账号运营" in skill)
require("task branches", all(x in skill for x in [
    "TopicJudge", "Titles", "Openings", "Outline", "Rewrite",
    "FullDraft", "CTA", "Review", "AudienceVersions", "Compression",
]))
require("no fabrication guard", "不要为了成稿自行补具体金额、案例、数据" in skill)
require("title angle rule", "打开角度" in skill)
require("compression rule", "压缩版与原版对比" in skill and "主要压缩手法" in skill)

ids = {item["id"] for item in evals["evals"]}
require("eval coverage", {
    "topic-judge", "titles", "openings", "outline", "rewrite",
    "full-draft", "cta", "review", "audience-versions", "compression",
}.issubset(ids))

print("OK")
