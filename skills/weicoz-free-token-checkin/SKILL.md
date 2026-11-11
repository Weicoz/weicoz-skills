---
name: weicoz-free-token-checkin
version: 1.0.1
description: >
  每日执行并核验 AI 产品免费额度签到。自动运行 Magpie 已登录账号的签到，
  回读每日额度和余额，并明确区分自动发放、网页签到、客户端签到与仅手动项目。
  用户说“每日签到”“领今天的免费 token”“额度领了吗”时使用。不负责注册、
  登录、实名、安装客户端或绕过验证码。
---

# 免费额度每日签到

## 执行

运行本 skill 的 `scripts/daily-checkin.sh`。脚本会：

1. 执行 `magpie accounts checkin`。
2. 从 `~/.config/magpie/plugin-checkin.json` 读取当天实际签到结果。
3. 用 `magpie quota --json` 回读每日额度和余额。

重复执行安全。`already` 表示今天已经领过，仍算成功；`inactive` 或
`no check-in event now` 只表示当前没有可领事件，不按失败处理。个人 provider
插件的 `inactive` 还会带“自动发放/无签到接口”的原因，不能改写成已领取。

默认不打开网页、不启动客户端。用户明确要求“网页也签”或“全部领取”时，
再读 [references/daily-checkins.md](references/daily-checkins.md)，只处理其中标为
`browser` 的项目，并使用用户已登录的 ego-browser 会话。

## 成功判定

- WorkBuddy：当天 `outcome=claimed` 或签到输出含 `already`，并有积分或连续天数证据。
- ZCode：有签到事件时看当天 outcome；无 gift plan 时如实报“无可领额度”。
- 额度：只引用 `magpie quota --json` 返回的数值；接口错误、控制台专用和未登录不得写成 0。
- 网页或产品：以页面显示“已领取/已签到”或积分余额增加为准，不以页面打开或按钮点击为准。

## 边界

- 不自动注册、登录、扫码、验证码、实名、绑卡或安装客户端。
- 遇到登录墙、人机验证、短信或 OTP，立即交给用户。
- 客户端限定项目只列待办，不宣称已领取。
