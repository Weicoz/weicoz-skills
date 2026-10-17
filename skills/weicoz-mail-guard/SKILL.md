---
name: weicoz-mail-guard
version: 1.2.0
description: 安全隐私优先的多邮箱管理与事件驱动大模型智能通知系统（mail-guard）。当用户要求“查收邮件”“查验证码”“找登录链接”“看看有没有新邮件”“邮箱摘要”“邮箱待办”“mail-guard”“check email”“fetch 2FA/OTP/magic link”“查QQ/Outlook/Gmail邮箱”或管理后台监听、调整汇总排班、测试邮件推送、重新授权微软邮箱时使用。支持只读无损拉取（PEEK）、零外部资源加载防追踪、本地规则粗筛与大模型提取。遇到验证码与登录链接时必须原样输出纯文本并绝对禁止 Agent 预取点击。
whenToUse: 当用户要求“检查邮箱”“查收邮件”“查验证码”“看看有没有新邮件”“邮箱摘要”“找登录链接”“mail-guard”“check email”“2FA/OTP”或管理邮件守护监听与排班时使用。
---

# 多邮箱管理与智能告警（weicoz-mail-guard）v1.2.0

基于本地统一 CLI 工具 `mail-guard`，为多邮箱管理提供物理级防追踪、只读无损拉取（`BODY.PEEK[]`）与事件驱动的智能通知。

## 核心设计与安全原则

1. **物理级防追踪**：纯 IMAP 协议拉取，纯文本隔离清洗（仅提取 `text/plain`；纯 HTML 邮件由本地纯离线解析器剥离标签，绝对不发起针对邮件正文内任何外部资源的 HTTP/DNS 请求，100% 阻断 Tracking Pixels 间谍像素）。
2. **状态无损（PEEK）**：所有主动查询与事件驱动抓取均强制采用 `BODY.PEEK[]` 只读模式，绝对不将未读邮件标记为已读。
3. **零 Token 闲置监听**：基于 IMAP IDLE 协议长连接常驻后台（`goimapnotify` / `run_daemon.py`），秒级响应新邮件；本地轻量规则粗筛，非目标邮件本地拦截，**闲置 Token 消耗严格为 0**。
4. **按需单次唤醒大模型**：仅当命中验证码、两步验证、安全告警等目标特征时，单次唤醒大模型或本地免 Key Harness 提取结构化 JSON。
5. **统一推送分发**：无缝联动统一通知调度器 `harness-notify`（路由键 `"mailguard"`），多渠道覆盖系统原生弹窗、Bark、飞书机器人/CLI、Telegram。

---

## 🚨 核心交付纪律：链接与验证码提取规范（强制约束）

> [!IMPORTANT]
> **1. 必须原样输出链接与验证码**：
> 当邮件中包含**登录确认链接（Magic Link）**、**一次性 Token**、**密码重置链接**、**双重认证 (2FA) 验证码**或**重要业务跳转链接**时，Agent **必须且绝对不得遗漏**在最终回复中将纯文本链接和验证码完整呈现（使用独立代码块展示），以便用户直接复制使用。
>
> **2. 严格禁止 Agent 打开或预取链接**：
> Agent **绝对禁止**通过浏览器、`curl`、`fetch`、`read_url_content` 或任何自动化工具去直接访问、点击或预先探测该链接。
> - **原因 1：防止一次性 Token 作废**：Magic Link 和密码重置链接均为单次有效（Single-Use）。自动化请求一旦触碰，Token 立即被服务端消耗作废，用户后续在浏览器点击时将直接遭遇 `Expired` 或 `Invalid Token`。
> - **原因 2：认证会话隔离**：登录必须由用户在自己的宿主浏览器上完成，以绑定用户的真实登录态与指纹环境。
> - **原因 3：防风控误判**：避免 Agent 所在的 IP 或无头特征触发发信方平台的安全风控与封禁。
>
> **3. 刚性拒绝用户自动点击指令**：
> 若用户明确要求“帮我打开邮件里的登录链接”或“帮我点击确认”，Agent **必须礼貌拒绝**，向用户说明该链接为一次性认证 Token，必须由用户在个人浏览器中手动打开。

---

## 核心配置与关键路径

- **全局 CLI 命令**：`mail-guard`（位于 `~/.local/bin/mail-guard`）
- **备用脚本路径**：`python3 $HOME/File/git/mail-guard/scripts/cli.py`
- **本地配置文件目录**：`~/.config/mail-guard/`
  - 邮箱账户配置：`~/.config/mail-guard/accounts.json`（严格隔离，禁止提交）
  - 模型与通知环境变量：`~/.config/mail-guard/mail-guard.env`（LLM Provider、Harness、排班 SCHEDULE）
  - 微软 OAuth2 令牌缓存：`~/.config/mail-guard/ms_tokens.json`
  - 历史简报归档：`~/.config/mail-guard/summaries/`（最新报告查看：`cat $(ls -t ~/.config/mail-guard/summaries/*.md | head -1)`）
  - 后台守护日志：`~/.config/mail-guard/mailguard.log`
  - 定时汇总日志：`~/.config/mail-guard/summary.log`
- **统一通知路由配置**：`~/.config/harness-notify/config.json`（路由 key: `"mailguard"`）
- **系统自启守护托管**：
  - macOS: `~/Library/LaunchAgents/com.weicoz.mailguard.plist`
  - Linux: `~/.config/systemd/user/mailguard.service`

---

## 常用场景与执行命令

### 1. 主动查收邮件 / 检索验证码与安全登录链接

```bash
# 查询所有配置邮箱的最新 1 封邮件
mail-guard query

# 查询指定邮箱（qq / outlook / gmail1 / gmail2 / all）最新 N 封
mail-guard query --account outlook --limit 3

# 专供 Agent 解析的结构化 JSON 输出
mail-guard query --account all --limit 2 --json

# 按关键词检索（如找验证码、通知、动态口令）
mail-guard query --keyword "验证码"

# 按主题检索（精准匹配主题字串）
mail-guard query --subject "GitHub"

# 按发件人检索并输出完整正文
mail-guard query --from "anthropic.com" --full

# 检查垃圾邮件箱（当怀疑重要邮件被误判为垃圾邮件时）
mail-guard query --account qq --folder Junk --limit 3

# 检索过去 N 天内的邮件（默认 30 天）
mail-guard query --days 7 --limit 5
```

### 2. 每日跨邮箱智能摘要与待办提炼

系统定期全自动扫描所有邮箱，由大模型识别**待办事项 (Action Items)** 与 **重要告警 (Important Alerts)**，过滤营销噪音：

```bash
# 手动触发一次增量汇总（默认过去 8 小时）
mail-guard summary

# 演练模式（仅终端打印，不写本地简报文件、不发推送）
mail-guard summary --dry-run

# 扫描过去指定小时数（如过去 24 小时）
mail-guard summary --hours 24

# 全量无时间限制扫描
mail-guard summary --all-time

# 无重要邮件时也强制发送平安通报
mail-guard summary --always-notify
```

### 3. 后台守护服务与排班管理

```bash
# 查看服务运行状态与监听进程
mail-guard daemon status

# 启动后台守护
mail-guard daemon start

# 重启后台监听并自动应用排班
mail-guard daemon restart

# 停止后台监听
mail-guard daemon stop

# 查看当前每日汇总排班时刻表
mail-guard daemon schedule

# 修改 mail-guard.env 后，同步排班至系统服务（launchd / systemd）
mail-guard daemon schedule --apply

# 实时查看监听日志
mail-guard daemon logs

# 查看定时汇总日志
mail-guard daemon logs --summary
```

> **排班调整 SOP**：编辑 `~/.config/mail-guard/mail-guard.env` 中的 `SUMMARY_SCHEDULE="08:30, 12:00, 15:30, 18:30, 21:30, 00:30"` -> 执行 `mail-guard daemon schedule --apply` -> 执行 `mail-guard daemon schedule` 验证。

### 4. 模型路由、账户与连通性自检

```bash
# 查看大模型调度模式与本地已安装 Harness（Claude / Codex / Kimi / AGY / DSH）
mail-guard model

# 执行端到端轻量结构化提取测试与测速
mail-guard model test

# 查看已配置邮箱账户清单
mail-guard account list

# 邮箱连接连通性全面测试
mail-guard account test

# 微软账户重新授权（Device Code 流程）
mail-guard account auth-ms

# 测试全通道消息推送连通性（桌面弹窗 / harness-notify / 飞书 / Bark）
mail-guard notify

# 运行端到端全链路自检流水线
mail-guard test

# 查看系统各项配置与存储文件路径
mail-guard config
```

---

## 异常诊断与自愈排障 SOP

1. **未收到验证码 / 漏信排查**：
   - 步 1：`mail-guard daemon status` 检查 worker 是否在运行；
   - 步 2：`mail-guard query --account all --limit 3 --full` 查看最新收信；
   - 步 3：若怀疑被拦截，检查垃圾箱 `mail-guard query --account <acc> --folder Junk`；
   - 步 4：`mail-guard daemon logs` 查看是否因关键词过滤被跳过。
2. **微软 Outlook 鉴权失败 / Token 过期**：
   - 执行 `mail-guard account auth-ms`；
   - **立即提取输出中的 `verification_uri` (`https://microsoft.com/devicelogin`) 与 `user_code` 提示用户在浏览器完成授权**；
   - 授权成功后执行 `mail-guard daemon restart`。
3. **海外邮箱代理异常 (Gmail / Outlook 握手超时或 403 Port Forbidden)**：
   - 检查本地代理端口：`nc -zv 127.0.0.1 7897`；
   - 确保代理出站节点放通 IMAP SSL `993` 端口（机房/住宅拦截 993 端口会导致 `WRONG_VERSION_NUMBER` 报错）；
   - 在代理客户端（如 Bettbox / Clash）中切换为全端口支持节点（如中转节点）；
   - 如需更改代理端口，编辑 `~/.config/mail-guard/accounts.json` 中的 `"proxy"` 字段后执行 `mail-guard daemon restart`。
