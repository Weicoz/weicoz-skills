---
name: weicoz-last30days-cn-bridge
description: Wrapper skill for Chinese last-30-days research that must not modify the official last30days-cn skill. Use when the user wants last30days-cn results plus local fixes for missing python command, playwright-cli/browser login fallback, source-level diagnostics, or external fallback search for Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat, Baidu, and Toutiao while preserving official skill update compatibility.
---

# weicoz-last30days-cn-bridge

Use this skill as an outer layer. Never edit `$WEICOZ_OFFICIAL_LAST30DAYS_SKILL`.

## Default Paths

- Official skill: `$WEICOZ_OFFICIAL_LAST30DAYS_SKILL`
- Bridge script: `scripts/last30days_cn_bridge.py`
- Browser states: `~/.codex/browser-states/last30days-cn-<platform>.json`

## Workflow

1. Diagnose wrapper and official source status:

```bash
python3 {{SKILL_DIR}}/scripts/last30days_cn_bridge.py diagnose
```

2. Run official `last30days-cn` through Python 3, then add wrapper fallback when sources are sparse:

```bash
python3 {{SKILL_DIR}}/scripts/last30days_cn_bridge.py run "客服 售后 太麻烦" --search xiaohongshu,zhihu,bilibili,wechat --deep --emit md
```

3. If source needs login or browser verification, use `playwright-cli` outside official skill:

```bash
playwright-cli open --headed "https://www.xiaohongshu.com/search_result?keyword=客服%20售后"
playwright-cli state-save ~/.codex/browser-states/last30days-cn-xiaohongshu.json
```

Then rerun bridge. Report browser-confirmed evidence separately from API/search fallback evidence.

## Source Policy

- `weibo`: prefer official token or browser login; public mobile API is best-effort only.
- `xiaohongshu`: prefer configured `XIAOHONGSHU_API_BASE` or browser login; do not use ScrapeCreators for XHS.
- `bilibili`: public API first; if HTTP 412/empty, use browser page.
- `zhihu`: prefer `ZHIHU_COOKIE` or browser login; public `search_v3` often fails.
- `douyin`: prefer `TIKHUB_API_KEY`/`DOUYIN_API_KEY` or browser page; unsigned public API is weak.
- `wechat`: prefer browser or site search for `mp.weixin.qq.com`; old third-party API is optional only.
- `baidu`: public HTML and claimed API are best-effort; Bing fallback is acceptable.
- `toutiao`: unsigned API often needs signature; use browser or site search fallback.

## Evidence Rules

Always label path:

- `official:<source>` means official skill returned item.
- `bridge:site-search:<source>` means public search fallback, weak date/engagement confidence.
- `browser:<source>` means user/agent inspected page through `playwright-cli`.

Do not promote fallback links into strong user-pain evidence. Strong evidence needs readable post/comment text, URL, date or date confidence, and platform/source path.

## Extra Reference

Read `references/source-fixes.md` when deciding how to repair a specific source.
