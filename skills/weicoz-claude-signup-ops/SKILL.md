---
name: weicoz-claude-signup-ops
version: 1.0.0
description: >
  在国内搭建指纹浏览器环境并注册 Claude 网页账号的流程。用户要新建
  BitBrowser 窗口、注册或换绑邮箱、处理 Cloudflare「Just a moment」、
  复用 cf_clearance、Proton 注册被 422 拒绝、hCaptcha 人工接管，或要求
  证据化验收时使用。分流规则本身委派 weicoz-claude-citadel-routing，
  Claude Code 账号切换委派 weicoz-claude-account-ops。
whenToUse: 用户提到注册 Claude 账号、Claude 网页注册、BitBrowser 指纹窗口、Cloudflare 卡验证、cf_clearance、Proton 422、hCaptcha，或要在国内环境完成 Claude 注册并留证据。
---

# Claude 网页注册（weicoz-claude-signup-ops）v1.0.0

目标：产出一个能正常登录和对话的 Claude 网页账号（Free 起步），全过程有证据。
只负责网页注册；分流修复找 `weicoz-claude-citadel-routing`，Claude Code
账号切换找 `weicoz-claude-account-ops`。

## 先决条件

- BitBrowser 正在运行，本地 API 默认 `http://127.0.0.1:54345`。
- Bettbox/Clash 正在运行，external-controller 默认 `127.0.0.1:9090`；
  secret 从本机 `~/.config/com.appshub.bettbox/config.json` 读取，不回显。
- 本机有可用的海外出口，mixed-port 默认 `127.0.0.1:7897`。
- Node 能 `require("playwright-core")`；不要求下载浏览器，只 `connectOverCDP`。
- 用户提供恢复邮箱；邮箱密码写本地 `inputs.env`（`chmod 600`），不提交。

## 0. 只读体检

先证明“出口”和“路由”两件事，再动窗口。

```bash
curl -s -x socks5h://127.0.0.1:7897 https://ipinfo.io/json
```

读 Clash 连接链，确认目标域名实际走哪个出口：

```bash
curl -s -H "Authorization: Bearer $CLASH_SECRET" \
  http://127.0.0.1:9090/connections \
  | jq -r '.connections[] | select(.metadata.host|test("claude|anthropic|proton")) | "\(.metadata.host) \(.chains)"'
```

本会话实测：`claude.ai` / `anthropic.com` 走 `🇺🇸 海外出口`（波特兰），
但 `account.proton.me` 被 `claude-citadel-gfw` 规则集带到
`🌐 海外服务`（日本节点）。只看 IP 国别会误判，必须看 chains。

## 1. 建指纹窗口

`POST /browser/update`，不带 `id` 即新建；`browserFingerPrint` 必传。代理指向
本机 mixed-port，不要直接填海外 IP：

```json
{
  "name": "Claude-1",
  "platform": "https://claude.ai",
  "proxyMethod": 2, "proxyType": "socks5",
  "host": "127.0.0.1", "port": "7897",
  "workbench": "localserver", "randomFingerprint": false,
  "browserFingerPrint": {
    "coreVersion": "148", "ostype": "PC", "os": "MacIntel",
    "architecture": "arm", "version": "148",
    "webRTC": "2",
    "canvas": "0", "webGL": "0", "webGLMeta": "0",
    "audioContext": "0", "speechVoices": "0", "mediaDevice": "1",
    "clientRectNoiseEnabled": true, "portScanProtect": "0",
    "doNotTrack": "0",
    "isIpCreateTimeZone": false, "timeZone": "America/Los_Angeles",
    "isIpCreateLanguage": false, "languages": "en-US",
    "isIpCreateDisplayLanguage": false, "displayLanguages": "en-US",
    "isIpCreatePosition": false,
    "lat": "45.5234502", "lng": "-122.6762115",
    "hardwareConcurrency": "10", "deviceMemory": "8",
    "deviceInfoEnabled": true,
    "computerName": "<真机设备名>", "macAddr": "<真机 MAC>"
  }
}
```

取值说明：

- `webRTC: "2"` 是禁止；`canvas/webGL/audioContext/speechVoices` 的 `"0"`
  是随机噪音（能过盾的工作窗口都用 0），`"1"` 是关闭噪音。
- `portScanProtect: "0"` 是开启；`"1"` 是关闭。
- `architecture` 在 Apple Silicon 上必须显式 `arm`，否则新建出来是 `x86`。
- **`isIpCreateTimeZone` / `isIpCreateLanguage` / `isIpCreatePosition` 在本地
  socks 代理下取的是本机公网 IP，不是代理出口**。本会话因此把时区判成
  `Asia/Shanghai`。必须关掉自动，显式写出口城市的时区、语言和经纬度。

时区、经纬度、language 一律跟真实出口城市对齐，不跟“教程里写的城市”对齐。

## 2. 打开并验证

`POST /browser/open {"id": "..."}` 返回 `data.http` 调试地址，用
`chromium.connectOverCDP("http://" + http)` 连接。在页面里验证：

```js
({
  ip: (await (await fetch("https://ipinfo.io/json")).json()).ip,
  tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  lang: navigator.language,
  hc: navigator.hardwareConcurrency,
  dm: navigator.deviceMemory,
  webdriver: navigator.webdriver
})
```

期望：IP 等于代理出口、`tz` 等于出口城市、`lang` 为 `en-US`、`webdriver` 为
`false`。BitBrowser 列表里的 `lastIp` 显示本机 IP 不代表代理失效，以页面内
`fetch` 为准。截图存任务目录。

## 3. 过 Cloudflare

新窗口、新 profile 在同一 IP 上会卡在 `Just a moment...`。已验证可行的做法：
从同出口、已过盾的旧窗口导出 `cf_clearance`，只复制这一个 cookie：

```js
const cf = (await clearedContext.cookies("https://claude.ai"))
  .find(c => c.name === "cf_clearance");
await newContext.addCookies([cf]);
```

复制后 `claude.ai` 应直接进 `/login`。不要连账号 session 一起复制。

仍被挑战时，让用户在指纹窗口手动完成；不要循环重载，不要把 BrowserScan 的
“100% 真实度”当唯一证据（扫描未完成时页面也会显示占位值）。

## 4. 邮箱

教程首选现成 Gmail / Outlook；没有再注册 Proton 免费版。

- Proton 在机房或代理出口注册会被 `422` + `Code 2028`（network abusive）
  拒绝；换浏览器（EGO）结果相同，说明是 IP/ASN 级，不是浏览器。
- 不要反复重试同一出口。换住宅网络，或让用户手动创建。
- 注册后绑定恢复邮箱；验证信里的链接右键复制地址，粘回同一指纹窗口打开。
- 收信窗口固定。Claude 的 magic link 就在这个收件箱里。

## 5. 提交 Claude 注册

1. `claude.ai/login` → `Continue with email`，手填邮箱；不要点
   `Continue with Google / Apple`。
2. 邮箱收到黑色 `Sign in` 按钮，10 分钟内打开。
3. `POST /api/auth/send_magic_link` 返回 `400`，页面提示
   `Couldn't verify your browser`，说明 hCaptcha 没过：页面里有
   `newassets.hcaptcha.com` 的 300×150 挑战框，交给用户在窗口里完成。
4. 通过后进入 onboarding：关闭 `Help improve our AI models` → Continue →
   填名字 → Free plan。
5. 先免费聊几轮，不急着 Upgrade。

## 6. 验收

- 账号页显示 Free plan，能发一条消息。
- 证据：窗口详情 JSON、页面内 IP/时区/语言、Cloudflare 通过截图、
  收信截图、账号页截图。
- 失败分类：`422` 网络拒绝；`403` 出口错误；Cloudflare 循环缺 clearance；
  hCaptcha 未过；页面 IP 与出口不一致说明漏代理。

## 常见坑

- 把 BitBrowser 的 `lastIp` 当出口：它是本机探测值。
- 把 `isIpCreate*` 当可靠：本地代理下取本机 IP。
- 把 Proton 的 422 当浏览器问题：EGO 同样 422。
- 只看到 fake-IP 就断言已走代理：必须看 `/connections` 的 chains。
- 家宽节点切换后 `ERR_CONNECTION_CLOSED`：节点可能不可用，先测再切。
- 在 CDP 自动化里硬解 hCaptcha：不做，交给人。

## 凭据与隐私

- 密码、恢复邮箱写本地 `inputs.env`（`chmod 600`），不提交、不回显。
- Clash secret 从本机配置读取，不写入日志或报告。
- 截图里出现邮箱时，报告只写脱敏后的地址。

## 交付格式

结论 → 窗口配置 → 出口与路由证据 → 邮箱结果 → Claude 注册结果 →
未完成项。未验证的步骤明确写「未验证」，不写成「已完成」。
