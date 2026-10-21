---
name: weicoz-mail-guard
version: 1.4.2
description: 安全隐私优先的多邮箱管理与事件驱动大模型智能通知系统（mail-guard）。当用户要求“查收邮件”“查验证码”“找登录链接”“看看有没有新邮件”“邮箱摘要”“邮箱待办”“mail-guard”“check email”“fetch 2FA/OTP/magic link”“查QQ/Outlook/Gmail邮箱”或管理后台监听、调整汇总排班、测试邮件推送、重新授权微软邮箱时使用。支持只读无损拉取（PEEK）、零外部资源加载防追踪、本地规则粗筛与大模型提取。遇到验证码与登录链接时必须原样输出纯文本并绝对禁止 Agent 预取点击。
whenToUse: 当用户要求“检查邮箱”“查收邮件”“查验证码”“看看有没有新邮件”“邮箱摘要”“找登录链接”“mail-guard”“check email”“2FA/OTP”或管理邮件守护监听与排班时使用。
---

# 多邮箱管理与智能告警（weicoz-mail-guard）v1.4.2

基于本地统一 CLI 工具 `mail-guard`，为多邮箱管理提供物理级防追踪、只读无损拉取（`BODY.PEEK[]`）与事件驱动的智能通知。

## 核心设计与安全原则

1. **毫秒级极速热快照 (Cache-First)**：新邮件到达时由后台长连接毫秒级自动同步至本地轻量 SQLite WAL 缓存；查询默认读取热快照，**响应耗时 < 50ms（提速 60x+）**，完全杜绝高频访问导致的邮箱封号与连接限流。
2. **协议级批量直连 (--live 兜底)**：支持 `--live` 参数穿透本地缓存直接请求 IMAP 服务器；采用 Sequence Range 范围切片直接批量 Fetch 最新邮件，彻底砍掉耗时的全量搜索与多次往返。
3. **物理级防追踪**：纯 IMAP 协议拉取，纯文本隔离清洗（仅提取 `text/plain`；纯 HTML 邮件由本地纯离线解析器剥离标签，绝对不发起针对邮件正文内任何外部资源的 HTTP/DNS 请求，100% 阻断 Tracking Pixels 间谍像素）。
4. **状态无损（PEEK）**：所有主动查询与事件驱动抓取均强制采用 `BODY.PEEK[]` 只读模式，绝对不将未读邮件标记为已读。
5. **零 Token 闲置监听与低磁盘损耗**：基于 IMAP IDLE 协议长连接常驻后台（`goimapnotify` / `run_daemon.py`），无邮件时内核级休眠（0% CPU）；SQLite WAL 极小顺序追加，正文限制 2000 字符，保留最新 30 封，**整库 < 1MB，SSD 零磨损，闲置 Token 消耗严格为 0**。
6. **按需单次唤醒大模型**：仅当命中验证码、两步验证、安全告警等目标特征时，单次唤醒大模型或本地免 Key Harness 提取结构化 JSON。
7. **统一推送分发**：无缝联动统一通知调度器 `harness-notify`（路由键 `"mailguard"`），多渠道覆盖系统原生弹窗、Bark、飞书机器人/CLI、Telegram。

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
>
> **4. 待办事项必须标注到达时间与来源邮箱**：
> 凡列入「待处理 / 需关注 / 待办」的邮件，**必须逐条标注**：
> - **来源邮箱**：`qq` / `gmail1` / `gmail2` / `outlook`；同一封出现在多个邮箱时写全（如 `gmail1 + outlook`）。**不得**只写账号简称或省略。
> - **到达时间**：绝对时间（本地时区含日期，如 `10-21 14:51 (+08:00)`）+ 相对时间（如「1 小时前」）。
> **不得**只写日期、只写相对时间、或整条省略时间与来源。原因：用户要按邮箱与时间定位邮件、判断紧急度与是否已过期，缺任一项等于信息不全。
> 已过期的一次性链接必须直接标注「已过期（10 分钟有效，已于 HH:MM 失效）」。

---

## 核心配置与关键路径

- **全局 CLI 命令**：`mail-guard`（位于 `~/.local/bin/mail-guard`）
- **备用脚本路径**：`python3 $HOME/File/git/mail-guard/scripts/cli.py`
- **本地配置文件目录**：`~/.config/mail-guard/`
  - 邮箱账户配置：`~/.config/mail-guard/accounts.json`（严格隔离，禁止提交）
  - 模型与通知环境变量：`~/.config/mail-guard/mail-guard.env`（LLM Provider、Harness、排班 SCHEDULE）
  - 本地极速 SQLite 缓存：`~/.config/mail-guard/cache/mails.db`（WAL 模式，亚秒级读取）
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

### 1. 查收邮件 / 待办（默认唯一入口：一次调用）

> [!IMPORTANT]
> **查邮件默认只跑一条命令**：`mail-guard brief -n 5 --hours 24`。
> 一条命令即返回：各账号最新邮件、**来源邮箱**、到达时间（本地 +08:00 绝对时间 + 相对时间）、发件人、主题、验证码/链接、正文预览、缓存水位、守护健康；输出 < 6KB、耗时亚秒级（典型 0.4-0.5s）。
> **禁止**为同一次查询串行叠加 `daemon status`、`--live`、大 JSON、多个账号逐个 `query` 试探——这正是端到端变慢的主因。
> **推理等级**：查邮件属轻量格式化任务，不需要深度推理；宿主提供推理等级选择时用最低可用档，代码类任务再切回 `max`。

```bash
# 【默认】一次调用出简报（缓存优先，零网络，亚秒级）
mail-guard brief

# 指定时间窗口与每账号条数
mail-guard brief --hours 48 --limit 5

# 只看某个账号（qq / gmail1 / gmail2 / outlook）
mail-guard brief --account outlook --limit 5

# 仅当需要"刚到达、尚未进缓存"的邮件时才加 --live（4 个 IMAP 直连，约 2-15s）
mail-guard brief --live --hours 6

# 仅当需要程序化处理时才用 JSON（体积更大，按需取）
mail-guard brief --json --limit 2
```

**升级到 query 的唯一条件**：`brief` 显示缓存滞后/无命中，或需要关键词、发件人、主题、垃圾箱、全文检索。

```bash
# 关键词检索（找验证码、通知、动态口令）
mail-guard query --keyword "验证码" --limit 3

# 按主题 / 发件人检索并输出完整正文
mail-guard query --subject "GitHub" --limit 3
mail-guard query --from "anthropic.com" --limit 2 --full

# 检查垃圾邮件箱（怀疑重要邮件被误判时）
mail-guard query --account qq --folder Junk --limit 3

# 检索过去 N 天内的邮件（默认 30 天）
mail-guard query --days 7 --limit 5

# 强制直连刷新并看完整正文
mail-guard query --account outlook --limit 1 --live
```

**输出纪律**：`brief` 之后不得再叠加同类查询；确需多轮检索时每轮只加一个过滤条件。

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

1. **未收到验证码 / 漏信排查**（按序，前一步无果再走下一步）：
   - 步 1：`mail-guard brief --hours 6 -n 3` —— 一次调用看最新信件、缓存水位与守护健康；
   - 步 2：若缓存滞后或无命中，`mail-guard brief --live --hours 6 -n 3` 直连刷新；
   - 步 3：仍无则查垃圾箱 `mail-guard query --account <acc> --folder Junk --limit 3`；
   - 步 4：`mail-guard daemon logs` 查是否因关键词过滤被跳过；仅在怀疑守护异常时才跑 `mail-guard daemon status`。
2. **微软 Outlook 鉴权失败 / Token 过期**：
   - 执行 `mail-guard account auth-ms`；
   - **立即提取输出中的 `verification_uri` (`https://microsoft.com/devicelogin`) 与 `user_code` 提示用户在浏览器完成授权**；
   - 授权成功后执行 `mail-guard daemon restart`。
3. **海外邮箱代理异常 (Gmail / Outlook 握手超时或 403 Port Forbidden)**：
   - 检查本地代理端口：`nc -zv 127.0.0.1 7897`；
   - 确保代理出站节点放通 IMAP SSL `993` 端口（机房/住宅拦截 993 端口会导致 `WRONG_VERSION_NUMBER` 报错）；
   - 在代理客户端（如 Bettbox / Clash）中切换为全端口支持节点（如中转节点）；
   - 如需更改代理端口，编辑 `~/.config/mail-guard/accounts.json` 中的 `"proxy"` 字段后执行 `mail-guard daemon restart`。
