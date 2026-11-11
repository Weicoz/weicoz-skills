# 每日免费额度清单

状态基准：2026-11-11。入口或额度变化时，以平台页面和 `magpie quota` 为准。

## Magpie 自动签到

| 项目 | 每日额度 | 当前条件 | 自动化 |
| --- | ---: | --- | --- |
| WorkBuddy | 100 积分 | 已登录 `LI+VLM`；2026-11-11 已领取，连续 8 天 | `magpie accounts checkin` |
| ZCode | 每日事件制 | 已登录；当前返回 `no ZCode gift plan to claim` | `magpie accounts checkin`，有事件才领取 |
| TRAE 国内版 | 100 积分 | Magpie 的 `traeCheckin` 已开，但目前没有已登录账号传入 | 有账号后随 `accounts checkin` |
| MiniMax Code | 400 积分 | Magpie 的 `minimaxCheckin` 已开，但目前没有已登录账号传入 | 有账号后随 `accounts checkin` |
| Qoder CN | 100 Credits，10:00 后领 | Magpie 的 `qoderCheckin` 已开，但目前没有已登录账号传入 | 有账号后随 `accounts checkin` |

个人 `magpie-provider-plugins` 的 11 个 provider 也都暴露了
`auth.checkin`。其中 ModelScope、AMD、Cloudflare 的每日额度由平台自动发放；
其余为按月、按窗口、代金券或一次性额度。它们统一返回 `inactive` 并附中文
原因，不伪造 `claimed`，因此不能当成“今天领到了新额度”。
New API 与 OpenCode Go 使用 Magpie 原生 provider，不再由个人插件重复提供。

## 每日自动发放，不需要点击

| 项目 | 每日额度 | 核验方式 |
| --- | ---: | --- |
| ModelScope | 200 魔粒 | `magpie quota modelscope-plugin --json` |
| Cloudflare Workers AI | 10,000 Neurons | `magpie quota cloudflare-workers-ai-plugin --json` |

## 网页或产品内签到

| 项目 | 每日额度 | 入口 | 自动化 |
| --- | ---: | --- | --- |
| 秒悟 Meoo | 2,000 积分 | 产品内每日登录 | `browser`，需已有登录态 |
| WPS 灵犀 | 100 智点；第 7 天起 200 | 灵犀产品内签到 | `browser`，需已有登录态 |
| 商汤小浣熊 | 300 积分 | 免费版产品内签到 | `browser`，需已有登录态 |
| 腾讯 ima | 50 算力 | ima 客户端签到 | 仅客户端 |

## 仅客户端或产品内

| 项目 | 每日额度 | 限制 |
| --- | ---: | --- |
| 豆包电脑版 | 200 额度 | 登录电脑版签到，不是开放平台 API |
| 华为 OfficeAce | 100 积分 | 客户端或微信小程序 |
| 讯飞 AStudio | 100 积分 | 下载并登录体验版 |
| Qoder 国际版 Qoduck | 每日有限免费次数 | 只在 Qoder 国际版主应用，不是签到积分 |

## 不属于每日签到

| 项目 | 原因 |
| --- | --- |
| fal FLUX 3 Max 视频 | 免登录 Sandbox，每日 1 个视频；属于生成额度，不是签到 |
| 一次性新人券、月券、学生认证 | 按对应周期或资格领取，不纳入每日任务 |
