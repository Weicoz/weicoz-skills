---
name: weicoz-t3-dispatch
version: 1.1.0
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
- CLI 与服务端版本不一致时，stdout 会混入 `WARN ... migration history diverges` 日志。这不影响执行；解析 `--json` 输出时只取以 `{` 开头的行。

## 派单流程

1. **建 worktree**：用 worktrunk，不用 T3 的 `--worktree`。
   ```bash
   wt switch --create <branch> --no-cd      # 生成 <仓库>/.worktrees/<branch 中 / 换成 ->
   ```
2. **登记项目**：每个 worktree 登记成一个 T3 项目，会话就在该目录里运行。
   ```bash
   t3 project add --title "<仓库> <branch>" <worktree 路径>
   ```
3. **冒烟**（该 provider 本机首次使用时）：
   ```bash
   t3 thread start --provider <id> --model '<模型串>' --title "冒烟测试" --wait --json <worktree> "只回复 OK"
   ```
   结果 `"status":"completed","reply":"OK"` 即通。
4. **派单**：提示词写进文件，经 stdin 传入。
   ```bash
   t3 thread start --provider <id> --model '<模型串>' --title "<任务名>" --json <worktree> - < task.md
   ```
   记下返回的 `threadId`。提示词必须写明：已在独立 worktree、可写范围、完成判据、提交但不合并不推送、交付说明格式。
5. **巡检**：把等待放进宿主后台作业，完成时会唤醒发起会话。
   ```bash
   scripts/t3-wait.sh <threadId> [超时秒，默认 5400]   # 0 完成；1 失败或等待输入；2 超时
   ```
   用户问进度时：`t3 thread show --messages 3 <threadId>`。不要前台忙轮询。
6. **验收**：在 worktree 里自己跑完成判据中的命令（测试、类型检查、构建、截图），查看 `git log`、`git diff --stat <基线>..`。代理自述不算通过。
7. **打回**：
   ```bash
   t3 thread send <threadId> - < fix.md     # 会话忙时排到下一轮，不打断
   ```
   然后重挂 `t3-wait.sh`。
8. **合并与清理**：验收通过后由发起方合并。不再续派时：
   ```bash
   wt remove <branch>
   t3 project remove <worktree 路径或项目 id>
   ```
   `t3 project remove` 只能删空项目。项目下还有会话时报 `ProjectLiveServerDeclaredResponseError ... invalid_command`（实测：空项目删除成功，含会话的项目失败，本机与 m4 同样）。有会话时的做法：
   - 在 T3 界面里删除或归档会话后再删项目（未验证）；
   - 或用 MCP `t3_project_delete`，传 `force:true`；该工具要求 full-access 客户端，`auto-accept-edits` 令牌会被拒（`capability_denied`）。未获用户同意前不要为此升级到 full-access。
   - 会话的运行模式比 MCP 令牌宽时，`t3_thread_organize archive` 被拒（`runtime_mode_escalation_denied`）。CLI 派出的会话默认 full-access。
   不确定时保留项目，并告知用户。删除 worktree 前确认不再需要其中未提交的产物（截图、日志）。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 列出项目下会话 | `t3 thread list --project <路径> --json` |
| 看状态与最新回复 | `t3 thread show --messages N <threadId>` |
| 同步等待一轮结束 | `t3 thread send --wait <threadId> <消息>`（退出码 1 失败，2 等待用户回答） |
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
