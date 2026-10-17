---
name: weicoz-mail-guard
version: 1.0.0
description: 安全隐私优先的多邮箱管理与事件驱动大模型智能通知（mail-guard）。支持拉取邮件、查收验证码与登录安全链接、每日跨邮箱智能摘要（待办事项与重要告警提炼）、后台长连接守护管理与排班、连通性自检。纯文本严格隔离、零远程资源加载、只读 PEEK 无损未读状态。
whenToUse: 当用户要求“检查邮箱”“查收邮件”“查验证码”“看看有没有新邮件”“邮箱摘要”“mail-guard”或管理邮件守护监听与排班时使用。
---

# 多邮箱管理与智能告警（weicoz-mail-guard）v1.0.0

基于本地统一 CLI 工具 `mail-guard`，为多邮箱管理提供安全隔离、只读无损拉取与事件驱动的智能通知。

## 核心设计与安全原则

1. **物理级防追踪**：纯 IMAP 协议拉取，纯文本隔离清洗（仅提取 `text/plain`），绝对不发起针对邮件正文内任何外部资源的 HTTP/DNS 请求，100% 阻断追踪像素（Tracking Pixels）。
2. **状态无损（PEEK）**：主动查询默认采用 `BODY.PEEK[]` 只读模式，绝对不将未读邮件标记为已读。
3. **零 Token 闲置监听**：基于 IMAP IDLE 协议长连接常驻后台（`goimapnotify` / `run_daemon.py`），秒级响应新邮件；本地轻量规则粗筛，非目标邮件本地拦截，**闲置 Token 消耗严格为 0**。
4. **按需单次唤醒大模型**：仅当命中验证码、两步验证、安全告警等目标特征时，单次唤醒大模型或本地 Harness 提取结构化 JSON。
5. **统一推送分发**：无缝联动统一通知调度器 `harness-notify`，多渠道覆盖系统原生弹窗、Bark、飞书机器人/CLI、Telegram。

---

## 核心路径与环境

- **全局 CLI 命令**：`mail-guard`（位于 `~/.local/bin/mail-guard`）
- **备用脚本路径**：`python3 $HOME/File/git/mail-guard/scripts/cli.py`
- **本地配置文件目录**：`~/.config/mail-guard/`
  - 邮箱账户配置：`~/.config/mail-guard/accounts.json`（严格隔离，禁止提交）
  - 模型与通知环境变量：`~/.config/mail-guard/mail-guard.env`
  - 微软 OAuth2 令牌缓存：`~/.config/mail-guard/ms_tokens.json`
  - 历史简报归档：`~/.config/mail-guard/summaries/`
  - 后台守护日志：`~/.config/mail-guard/mailguard.log`
  - 定时汇总日志：`~/.config/mail-guard/summary.log`
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

# 按发件人检索并输出完整正文
mail-guard query --from "anthropic.com" --full

# 检索过去 N 天内的邮件（默认 30 天）
mail-guard query --days 7 --limit 5
```

> [!WARNING]
> **安全警示**：当邮件包含一次性登录安全链接（Magic Link）或密码重置链接时，**严禁自动调用浏览器或发起网络请求预取**。必须仅将纯文本链接原样提供给用户，避免链接失效或破坏安全认证流程。

### 2. 每日跨邮箱智能摘要与待办提炼

系统定期全自动扫描所有邮箱，由大模型识别**待办事项 (Action Items)** 与 **重要告警 (Important Alerts)**，过滤营销噪音：

```bash
# 手动触发一次增量汇总（默认过去 8 小时）
mail-guard summary

# 演练模式（仅终端打印，不写本地简报文件、不发推送）
mail-guard summary --dry-run

# 扫描过去指定小时数（如过去 24 小时）
mail-guard summary --hours 24

# 无重要邮件时也强制发送平安通报
mail-guard summary --always-notify
```

### 3. 后台守护服务与排班管理

```bash
# 查看服务运行状态与监听进程
mail-guard daemon status

# 查看当前每日汇总排班时刻表
mail-guard daemon schedule

# 修改 mail-guard.env 后，同步排班至系统服务（launchd / systemd）
mail-guard daemon schedule --apply

# 重启后台监听并自动应用排班
mail-guard daemon restart

# 停止后台监听
mail-guard daemon stop

# 实时查看监听日志
mail-guard daemon logs

# 查看定时汇总日志
mail-guard daemon logs --summary
```

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

## Agent 执行纪律

1. **状态无损默认**：主动拉取邮件必须保持未读状态，不得隐式附加 `--mark-read` 参数。
2. **凭据保护**：不得在回复或文档中打印邮箱密码、应用授权码、API Key 或 OAuth 令牌。
3. **网络与代理注意**：海外邮箱（Gmail、Outlook）依赖本地代理端口（如 `127.0.0.1:7897`）；若出现 SSL 握手超时，优先提示检查本地代理与端口连通性。
4. **路径动态解析**：配置与脚本中禁止硬编码绝对用户名路径，统一使用 `$HOME` 或 `~`。
