---
name: weicoz-t3-dispatch
version: 1.3.2
description: 经本机 T3 Code（`t3` CLI）把编码任务派给其他 harness（DSH、Kimi Code、Antigravity 等），在独立 worktree 里执行，并巡检、续派、验收。用户说“用 T3 派”“通过 t3 code 分发任务”“让 DSH/Kimi 在 T3 里做”时使用。跨机器派单见本文“跨机器派单”一节（也可用 weicoz-remote-dispatch）；当前会话自己的子代理不需要本技能。
---

# T3 Code 任务分发

T3 Code 是本机的多 harness 图形客户端。它的 `t3` CLI 可以新开会话、给会话发消息、读会话状态。用它派单的好处：每个任务在 T3 界面里是一个可见会话，用户能旁观和插话。

## 授权

- 每个新任务首次派出前，展示确认卡并等用户明确同意。沉默、含糊或只回“嗯”不算同意。
- 同一任务的续派、打回修复，在 provider、模型和范围都不变时免确认。
- 换 provider 或模型、扩大范围、触及真机/生产/共享环境、同一任务连续两轮验收不通过：重新确认。
- 冒烟会话也会消耗额度，写进确认卡。

确认卡：

```
准备经 T3 派单（等你确认）：
- harness：<provider id>（<显示名>），模型：<模型串>
- 项目与基线：<仓库> @ <短哈希>，分支 <branch>，worktree <路径>
- 本地未提交改动：无／有（说明处理）
- 提示词要点：<一两句>；可写范围：<目录>
- 首次使用该 provider：会先跑一次冒烟会话
回复「确认」后派出。
```

## 前置检查

```bash
t3 --version                     # CLI 存在
scripts/t3-models.sh             # provider 实例 id 与可用模型串
```

- `--provider` 与 `--model` 必须同时传。模型串取 `t3-models.sh` 输出的原文，例如 `'["magpie","auto/deepseek-v4.1-flash"]'`，整串加单引号。
- 报错 `Model X is not advertised by provider Y` 表示模型串不对。
- 某 provider 还没有历史模型串时，请用户先在 T3 界面用它开一个会话，再重跑脚本。不要猜模型串。
- T3 服务端必须在运行（桌面 App 开着，或 `t3 serve`）。
- CLI 与服务端版本不一致时，会混入 `WARN ... Database migration history diverges` 警告块。实测两点：t3 的日志写 **stdout**，不写 stderr；该警告由内部 `logWarning` 打印，**不改变命令退出码**——`thread list` 退出 1 时伴随的是真实错误（如 `SecretStoreSecureError`），不是警告本身。
- 手工敲命令统一加全局参数 `--log-level none`。本目录脚本经 `scripts/t3-lib.sh` 的 `t3_call` 调用 t3：成功时过滤该警告块，失败时把原始输出原样打到 stderr（不用 `2>/dev/null` 吞掉真错误），退出码原样返回。`scripts/t3-json.py` 再按 JSON 行兜底。

## 分支守卫

派单脚本自动把守卫写进提示词，不依赖派单者记得写。

1. **派单时自动加开头**：`t3-start.sh` 用 `git -C <worktree> branch --show-current` 取分支，把固定开头拼在任务文件前面，合并写入临时文件再派，**不改原任务文件**。开头三条：
   - 开工先 `git branch --show-current`，必须等于该 worktree 当前分支，不等就停下报告；
   - 所有提交只落在该分支；
   - `git add` 只加具体文件，不用 `-A`。
   worktree 处于 detached HEAD 时取不到分支名，脚本拒派（退出 3）。`--dry-run` 只打印拼接后的完整提示词，不登记项目、不起会话；核对提示词用它。
2. **收尾审计**：`scripts/t3-audit.sh <worktree> [--branch <目标分支>]` 列出近 24 小时内、所有本地分支上署名含 “via DSH” 的提交，凡不在目标分支上的都报警，给出提交号、摘要与所在分支。
   - 目标分支默认取 worktree 当前分支；`--hours` 改窗口，`--author` 改署名匹配串。
   - 署名匹配查提交正文（含 `Co-Authored-By: … via DSH` 尾注）、作者与提交者。DSH 的落款在正文尾注里，`%an` 通常是普通姓名，只查作者会漏。
   - 默认只在“没落在目标分支”时报警；`--strict` 连“落在目标分支但同时出现在别的分支”一起报。
   - 退出码 0 无异常、1 有异常、3 参数错误；只读，不改仓库。验收通过、合并前后各跑一次。

## 派单流程

1. **建 worktree**：用 worktrunk，不用 T3 的 `--worktree`。
   ```bash
   wt switch --create <branch> --no-cd      # 生成 <仓库>/.worktrees/<branch 中 / 换成 ->
   ```
2. **冒烟**（该 provider 本机首次使用时）：
   ```bash
   t3 --log-level none thread start --provider <id> --model '<模型串>' --title "冒烟测试" --wait --json <worktree> "只回复 OK"
   ```
   结果 `"status":"completed","reply":"OK"` 即通。
3. **派单**：一条命令登记项目、起会话、设推理等级。
   ```bash
   export T3_PROVIDER=<provider 实例 id>
   export T3_MODEL='<模型串>'
   scripts/t3-start.sh <worktree> "<任务名>" task.md      # stdout 倒数第二行是 threadId，末行是下一步命令
   ```
   - 脚本顺序：取当前分支拼分支守卫（见「分支守卫」）→ 项目未登记时 `t3 project add`（名称默认取 worktree 目录名，`--project-title` 可改），已登记则跳过 → `thread start --json` → 解析 threadId → `t3-effort.sh` 设 `reasoning_effort`。
   - DSH 默认值（2026-11 实测；provider 实例名以 `scripts/t3-models.sh` 为准）：`T3_PROVIDER=acpRegistry_dsh`，`T3_MODEL='["magpie","auto/deepseek-v4.1-flash"]'`。
   - 用户偏好：DSH 派单一律 `max`（`T3_EFFORT` 或 `--effort` 可改）。各模型可选值见 MCP `orchestrator_capabilities`（选项名 `reasoning_effort`）；不设时多数模型默认 `high`，`magpie` 路由组默认为空。脚本内部签 5 分钟 full-access 令牌、校验后即吊销，属于本 skill 的既定步骤。
   - 手工起会话：`t3 --log-level none thread start --provider <id> --model '<模型串>' --title "<任务名>" --json <worktree> - < task.md`，再 `scripts/t3-effort.sh <threadId> <provider id> '<模型串>' max`（输出 `reasoning_effort=max` 才算设好）。
   - 提示词必须写明：已在独立 worktree、可写范围、完成判据、提交但不合并不推送、交付说明格式。
   - 脚本成功后 stdout 末行给出可直接照抄的 `t3-wait.sh` 命令，接着按第 4 步挂监测，不要就此收工。
4. **巡检（固定流程，不得跳过）**：起会话后**立刻**把等待挂到宿主后台作业（例如 Bash 工具的 `run_in_background`），完成后再读正文并验收。只发任务不监测等于没派单。
   ```bash
   scripts/t3-wait.sh <threadId> [超时秒，默认 5400] [--project <路径>]   # 0 完成；1 失败或等待输入；2 超时；3 参数错误
   scripts/t3-last.sh <threadId> [--project <路径>]                      # 只打印最后一条 assistant 正文
   ```
   - 顺序固定：`t3-start.sh` → 立刻后台挂 `t3-wait.sh` → 唤醒后 `t3-last.sh` 读正文 → 验收（第 5 步）。`t3-start.sh` 末行就是这条命令，路径含空格时已加好引号，可整行照抄。
   - 三条禁令：不得只发任务不监测；不得把 `t3-wait.sh` 放前台阻塞；不得起完会话就向用户报“已派，等我消息”。
   - 退出 1（等待输入或失败）、退出 2（超时）都要回报用户，不静默重试。
   - 完成判据是 `t3 thread list --project` 里该线程状态不再是 `running`；不传 `--project` 时按线程所属项目查询。
   - `t3-last.sh` 去掉 t3 告警日志与 JSON 残行，只输出正文；传 `--project` 时还能把 `mcp:84354ccf` 这类前缀还原成完整 id。
   - 用户问进度时：`t3 --log-level none thread show --messages 3 <threadId>`。不要前台忙轮询。
5. **验收**：在 worktree 里自己跑完成判据中的命令（测试、类型检查、构建、截图），查看 `git log`、`git diff --stat <基线>..`。代理自述不算通过。
6. **打回**：
   ```bash
   scripts/t3-ask.sh <threadId> fix.md       # send → wait → last 一步完成
   # 或只发不等下一轮：t3 --log-level none thread send <threadId> - < fix.md
   ```
   - `t3 thread send` 返回 `Sent.`（线程空闲，立刻开跑）或 `Queued.`（线程忙，排到下一轮），两者都算发出成功，不重发。
   - 只发消息时，发出后再挂 `scripts/t3-wait.sh` 等下一轮。
7. **合并与清理**：验收通过后由发起方合并。删 worktree 前先确认没有绑定它的存活线程：
   ```bash
   t3 --log-level none thread list --project <worktree 路径> --json    # 仍有 running 或未归档线程时保留该目录
   ```
   - 线程还在跑、或要留着续派时，worktree 不删；先归档或结束会话再删目录。删前确认其中未提交的产物（截图、日志）已导出。
   - 长期线程（上线、运营、巡检）用固定 worktree，不随某次合并删除，后续只给它发消息。
   - 不再续派时：
     ```bash
     wt remove <branch>
     t3 project remove <worktree 路径或项目 id>
     ```
     `t3 project remove` 只能删空项目。项目下还有会话时报 `ProjectLiveServerDeclaredResponseError ... invalid_command`（实测：空项目删除成功，含会话的项目失败，本机与 m4 同样）。有会话时的做法：
     - 在 T3 界面里删除或归档会话后再删项目（未验证）；
     - 或用 MCP `t3_project_delete`，传 `force:true`；该工具要求 full-access 客户端，`auto-accept-edits` 令牌会被拒（`capability_denied`）。未获用户同意前不要为此升级到 full-access。
     - 会话的运行模式比 MCP 令牌宽时，`t3_thread_organize archive` 被拒（`runtime_mode_escalation_denied`）。CLI 派出的会话默认 full-access。
     不确定时保留项目，并告知用户。

## 补充指令只能排队

`t3` CLI 没有引导（steer）参数。线程忙时 `t3 thread send` 只返回 `Queued.`，消息排到下一轮才执行，改不了当前轮。

- 发之前先看状态：线程空闲就直接 `t3 thread send`，来得及生效；线程忙时排队等于没纠正。
- 用户要求优先用引导、且线程忙又要即时纠偏时，只有两条路：
  1. 告知用户 `t3` CLI 只能排队，由用户在 T3 界面用引导插进当前轮；
  2. 等线程空闲（`scripts/t3-wait.sh`）后再发，把纠偏放到下一轮。
- 必须原文转达这条限制，不得暗示“已引导”或“马上生效”。排队后按 `t3-wait.sh` 等这一轮，不重复重发。

## 派单模板默认值

派单前问不清的归档位置与体积处理，按下面默认值写进提示词，不为此单独打断用户。

| 项 | 默认 |
| --- | --- |
| 产物位置 | 项目内，如 `docs/…`；项目已有归档约定时用它的 |
| 构建产物、缓存 | 已被 `.gitignore` 覆盖的不提交；未覆盖的写明“不提交” |
| 大文件与二进制（截图、视频、模型、安装包） | 写明“不提交”；需要留证的放仓库外，或换成小体积替代 |
| 敏感内容（凭据、密钥、私有地址、真机截图里的账号） | 放仓库外，仓库内只留占位与环境变量名 |

- 提示词必须逐项写明哪些路径“不提交”，否则代理会把大文件一起 `git add`。
- “仓库外”只写位置约定（如 `~/.config/weicoz-secrets/<game>/`），不写真实路径、密钥或 AppID。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 起会话（含登记项目、effort、下一步提示） | `scripts/t3-start.sh <worktree> <标题> <任务文件>` |
| 等一轮结束 | `scripts/t3-wait.sh <threadId> [超时秒]` |
| 取最后一条回复正文 | `scripts/t3-last.sh <threadId>` |
| 发消息并等回复 | `scripts/t3-ask.sh <threadId> <消息文件>` |
| 只看将派出的完整提示词（不派） | `scripts/t3-start.sh <worktree> <标题> <任务文件> --dry-run` |
| 审计提交是否落错分支 | `scripts/t3-audit.sh <worktree> [--branch <目标分支>]` |
| 列出项目下会话 | `t3 --log-level none thread list --project <路径> --json` |
| 看状态与最新回复 | `t3 --log-level none thread show --messages N <threadId>` |
| 同步等待一轮结束（无超时） | `t3 --log-level none thread send --wait <threadId> <消息>`（退出码 1 失败，2 等待用户回答） |
| 网页查看 | `t3 thread show --json` 返回的 `thread.link` |

## 失败处理

- 状态为等待输入（`t3-wait.sh` 退出 1，回复里有提问）：把问题转给用户，不替用户回答业务决策。
- 同一任务连续两轮验收不通过：停下，向用户报告并建议换模型或换 harness，等确认。
- `t3` 命令报连接错误：先确认 T3 服务端在运行，再重试一次；仍失败就报告，不改派到其他工具。

## 跨机器派单（本机 T3 派到另一台机器）

用本机 T3 把会话派到远端机器（例：m4）。`thread start` 不能指定远端；要经 MCP 的 `t3_thread_launch` 带 `environmentId`。2026-11 实测通过（T3 `0.1.10-nightly.20261112.4580`，远端 macOS，codex provider）。

### 一次性准备

1. **远端装同版本 T3**：`curl -fsSL https://t3.codes/install.sh | T3CODE_VERSION=<本机 t3 --version 的版本> sh`。脚本只写 `~/.t3` 与 `~/.local/bin`。远端到 GitHub 很慢时，把本机 `~/.t3/runtime/versions/<版本>/` 打包拷过去，再 `ln -s .../t3 ~/.local/bin/t3`（同为 macOS arm64 才可）。
2. **远端只开 LAN**：`t3 up --lan --no-connect --yes`。不要裸用 `--yes`（新机器默认开 T3 Connect）。同时装一个后台服务。
3. **远端开关联环境**：在远端 `~/.t3/userdata/settings.json` 加 `"linkedEnvironmentsEnabled": true`（等同界面 Settings → Labs），本机同样要开。否则报 `Linked environments is off`。
4. **远端登记项目**：`ssh <远端> 't3 project add --title <名> <目录>'`（目录须是 git 仓库）。
5. **远端冒烟**：`ssh <远端> "t3 thread start --provider codex --model <模型> --wait --json <目录> '只回复 OK'"`。provider 与模型取远端已装 harness 的实际值（codex 的模型见远端 `~/.codex/models_cache.json`）。
6. **配对并 link**：`t3 environment link` 拒绝明文 http 的非本机地址（`is plain http`）。无 https 或 Tailscale 时，开 SSH 隧道，再 link 回环地址：
   ```bash
   ssh -f -N -o ExitOnForwardFailure=yes -L 127.0.0.1:13773:127.0.0.1:3773 <远端>
   CODE=$(ssh <远端> "t3 pair --label dispatch-link --ttl 10m" | sed -n 's/^Token: //p')
   t3 environment link http://127.0.0.1:13773 --pairing-code "$CODE" --access auto-accept-edits
   t3 environment list        # 应显示 reachable
   ```
   `--access` 取够用的最低档。link 有效期 30 天；隧道断开后状态变为不可达，需重开隧道。

### 派单

```bash
export T3_MCP_TOKEN=$(scripts/t3-mcp.py login)      # 默认 auto-accept-edits；T3_MCP_ACCESS 可改
scripts/t3-mcp.py call t3_environment_links         # 取远端 environmentId
scripts/t3-mcp.py call t3_project_list '{"environmentId":"<id>"}'
scripts/t3-mcp.py call t3_thread_launch '{"environmentId":"<id>","projectId":"<远端项目id>","title":"<任务>","modelSelection":{"instanceId":"codex","model":"<模型>"},"runtimeMode":"auto-accept-edits","message":"<提示词>"}'
scripts/t3-mcp.py call t3_thread_wait '{"environmentId":"<id>","threadId":"<threadId>"}'   # 阻塞到本轮结束
scripts/t3-mcp.py call t3_thread_read '{"environmentId":"<id>","threadId":"<threadId>"}'
```

- `login` 做的事：签 5 分钟管理会话 → 换绑定权限的一次性配对码 → OAuth（PKCE）换 MCP 令牌，管理会话随即吊销。`t3 auth session issue` 签的普通 bearer 令牌不能调 `/mcp`（401 `invalid_mcp_credential`），必须走这条路。
- 令牌有效期 30 天，只放进程环境变量，不写文件、不进输出。收工后吊销：`t3 auth session list` 找 `client: t3-dispatch`，`t3 auth session revoke <id>`。
- 会话的运行模式不能高于令牌的权限。远端项目要事先在远端登记；本机路径与远端路径不同，worktree 由远端自己管理（未验证 `workspaceStrategy:worktree` 在远端的行为）。
- 备选：`ssh <远端> 't3 thread start ...'` 直接在远端开会话，实测可行；本机 T3 界面看不到该会话的派发关系。

### 安全与清理

- 开 LAN 后，同网段任何人拿到配对码就能接入；配对码只是唯一门槛，TTL 用 10 分钟内，用后即失效，不回显、不写文件。
- 令牌与 link 的 `--access` 用最小够用档，不用 full-access。
- 收工清理：`t3 environment unlink <id>`；本机 `t3 auth session revoke` 吊销 MCP 令牌；关隧道；远端不再需要时 `t3 up --no-lan`。远端项目的清理见“派单流程”第 8 步。
