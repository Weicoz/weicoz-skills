# Source Fixes

Keep fixes outside official `last30days-cn`.

## Stable repair order

1. Run official skill via `python3`.
2. Add credentials/cookies in official config files only when user approves.
3. Use `playwright-cli` login/browser state outside official skill.
4. Use bridge site-search fallback for link discovery.
5. Mark weak evidence as weak.

## Config file

Official skill reads:

```text
~/.config/last30days-cn/.env
```

Optional keys:

```ini
WEIBO_ACCESS_TOKEN=
ZHIHU_COOKIE=
TIKHUB_API_KEY=
DOUYIN_API_KEY=
WECHAT_API_KEY=
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
XIAOHONGSHU_API_BASE=
```

## Browser state names

Use these paths:

```text
~/.codex/browser-states/last30days-cn-weibo.json
~/.codex/browser-states/last30days-cn-xiaohongshu.json
~/.codex/browser-states/last30days-cn-bilibili.json
~/.codex/browser-states/last30days-cn-zhihu.json
~/.codex/browser-states/last30days-cn-douyin.json
~/.codex/browser-states/last30days-cn-wechat.json
~/.codex/browser-states/last30days-cn-toutiao.json
```

## Platform notes

- Weibo: public mobile endpoint may return 403/empty. Browser login best.
- Xiaohongshu: official public endpoint often 404; local MCP must be healthy and logged in. Browser login best.
- Bilibili: add cookie/header or use browser if 412.
- Zhihu: use `ZHIHU_COOKIE` or browser; API often blocks anonymous search.
- Douyin: unsigned web API is not a reliable repair target. Use TikHub/API or browser.
- WeChat: prefer `site:mp.weixin.qq.com` search plus browser article read.
- Baidu: public HTML may hit security verify. Use Bing/WebSearch fallback.
- Toutiao: native API often needs signature. Use browser/site search.
