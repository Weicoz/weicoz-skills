---
name: weicoz-session-hub
description: 用一个总控会话协调多个独立的编码代理会话：总控派任务、补充指令、收汇报并验收，每个子会话用户也能直接对话。默认用 Herdr pane 跑 Claude Code、Codex、Kimi 等代理（DSH 等不能用 agent start 启动的代理先按普通命令启动），总控读 pane 输出验收，任何宿主都可当总控；Herdr 不可用、用户点名要会话消息，或子会话是云端／Remote Control 会话时，改用 Claude Code 的 ListAgents／SendMessage。用户说“多会话工作台”“开几个会话并行干、由一个会话汇总”“总控／主控会话”“给另一个会话发消息”“让那个会话做完告诉我”“用 Herdr pane 跑几个代理”“汇总几个会话的进度”时使用。单次委派一个子任务用宿主子代理或派单技能；多 worktree 开发与集成用 weicoz-multi-worktree-dev-v3；派到别的机器后台无人值守跑、经分支取回结果的用 weicoz-remote-dispatch；这三种情况不用本技能。
---

# 会话总控台

一个**总控会话**负责拆分任务、派发、收汇报和验收；多个**子会话**各自独立运行，用户可以随时直接进入任一子会话下指令。总控不替子会话干活，只管分工、边界和验收。

适合：多条相互独立的工作线并行推进，用户想随时插手其中某一条，且要一处汇总。不适合：一次性小委派（用宿主子代理即可），或多条线争写同一批文件（先串行化）。

## 选路线

| 路线 | 总控宿主 | 子会话 | 汇报方式 |
|---|---|---|---|
| 一（默认）. Herdr pane | 任何能执行 `herdr` 命令的宿主 | `herdr agent` 类型清单里的代理走代理命令；其他代理（如 DSH）先按普通命令启动 | 总控读 pane 输出，并回读产物；Claude 子会话可加 SendMessage 回报（见“混用”） |
| 二. 会话消息 | 仅 Claude Code（需有 `ListAgents`、`SendMessage` 工具） | 本机 Claude Code 会话、后台任务、云端会话、Remote Control 会话 | 本机会话用 `SendMessage` 回复总控；云端会话不能回发（`ListAgents` 工具说明原文），结果另取 |

默认走路线一。只有以下情况改走路线二：Herdr 不可用（未安装，或总控不在 Herdr pane 内且用户不改在 Herdr 里开总控）；用户点名要用会话消息；子会话是云端、Remote Control 或用户已在别处开好的 Claude Code 会话。路线二只在 Claude Code 里可用，没有 `ListAgents` 工具时不能走。
两条路线可以混用。工具是否存在以当前运行环境为准。总控不在 Herdr 内（`HERDR_ENV` 不等于 `1`）时，不得从外部操控用户的 Herdr 会话：请用户在 Herdr pane 里开总控会话，或经用户同意改走路线二，并说明原因。

## 开工前

1. **列出工作线**：每条线写清目标、输入、产出、范围、完成判据。判据必须能验证（文件、提交、测试命令、页面），不能只写“做完”。
   一条工作线也可以是一个 `weicoz-remote-dispatch` 远端任务：按该技能派出，总控用 `rd status` 监看、`rd fetch` 后审查验收；远端任务的派发仍须用户要求或授权。
2. **定唯一写入者**：同一文件、同一分支、同一外部状态（数据库、部署、对外消息）只能由一个会话写。并行改代码时，每条线用独立分支或 worktree。
3. **准入检查**：每次新开会话或派重活前，运行本技能目录下的 `scripts/hub-gate`。它检查四项，任一不达标即不放行：每核负载（1 分钟负载 ÷ 核数）超过 1.5、空闲内存低于 10%、可用磁盘低于 10 GB、已用交换超过 15 GB。阈值与 `weicoz-remote-dispatch` 的 `rd` 默认值一致，可用 `SESSION_HUB_*` 环境变量覆盖。
   - 退出码 0 放行；3 不放行，默认不新开会话，把脚本输出的算法和结论原样告诉用户，用户明确要求强制时才开；2 表示有指标无法采集，由用户决定。
   - 偏高时附上占用最高的进程。没有会话数上限，只看这四项。
   - Windows 没有负载均值，脚本改用 CPU 采样利用率（上限 85%，与 `rd` 的 `max_cpu_pct` 一致，`SESSION_HUB_MAX_CPU_PCT` 可覆盖），交换取页面文件已用量。Windows 上用 `python scripts\hub-gate` 运行（无法直接执行无扩展名脚本）。
   - 脚本无法运行时，按同样四项人工检查并写出算法。
4. **授权不扩大**：子会话只继承本次已授权的范围。提交、推送、部署、付费、对外发送照旧要用户授权，派单时写明。

## 路线一（默认）：Herdr pane

先确认 `test "${HERDR_ENV:-}" = 1`（Windows PowerShell：`$env:HERDR_ENV -eq "1"`），再读 `herdr --skill` 和 `herdr agent`、`herdr pane` 的帮助。命令语法以已安装版本为准。不得为探查语法而省略参数运行会修改布局的命令，也不得运行裸 `herdr`。

### 开 pane

1. **复用优先**：用 `herdr agent list`、`herdr pane list --workspace "$HERDR_WORKSPACE_ID"` 查现有 pane，同一任务优先复用。
2. **看布局**：`herdr pane layout --pane "$HERDR_PANE_ID"`。宽 pane 向右分，窄或高的 pane 向下分；多条工作线时交替方向，避免连续同方向切出过窄的列或过矮的行。
3. **切分**：`herdr pane split --current --direction right --cwd "$PWD" --no-focus`，从返回的 `.result.pane.pane_id` 取 ID，不要猜。

### 登记：状态存在 Herdr 的 pane 标签里

工作线状态不能只存在总控的上下文里，上下文压缩或换会话后会丢。Herdr 服务端持久保存 pane，所以把登记写成 pane 标签，不另建账本：pane 关了，登记也随之消失，不会出现账本和实际不一致。

- **格式**：`hub|<总控 pane ID>|<工作线>|<状态>|<ListAgents 名，可省>`。状态只用：已派单、待验收、已验收、已打回、受阻。标签支持中文和长文本（2026-10-15 实测），但不要在字段内用 `|`。
- **何时写**：`agent start` 或 `pane run` 成功后立即 `herdr pane rename <pane_id> "<标签>"`；派单、收到汇报、验收、打回时更新状态字段。
- **恢复**：总控换会话或上下文被压缩后，先 `herdr pane list`（不带 `--workspace`，可列出全部工作区），筛出以 `hub|<总控 pane ID>|` 开头的标签，即为全部在途工作线。用本技能的 `scripts/hub-ls [前缀]` 列出（Windows：`python scripts\hub-ls`），每行给出 pane ID、代理状态、工作线、登记状态和会话名。
  总控换了 pane 时，筛 `hub|` 前缀，把列表给用户确认后再接管，并把标签里的总控 ID 改成新的。
- **范围**：完成判据和派单原文不放进标签，写在派单说明文件里，恢复时按工作线名找回。远端 `rd` 任务由 `rd status` 登记，云端会话写进分支或 PR，都不用 pane 标签。
- **Herdr 重启后**（2026-10-15 在 Mac mini 上停止并重启一个独立会话实测）：标签、布局和 pane ID 都恢复，但 pane 里的进程全部结束，只剩新 shell。所以恢复时，标签为“已派单”或“待验收”的线，必须用 `hub-ls` 的代理状态或 `herdr pane process-info --pane <pane_id>` 核对代理是否还在运行；不在的改为“受阻”，在原 pane 里用代理自己的续跑命令接回原会话（例如 Codex 的 resume、Claude Code 的 `--resume`），已写入文件和提交的成果不受影响。

### 已识别代理（`herdr agent` 类型清单里有的，如 claude、codex、kimi）

1. **起代理**：`herdr agent start <名字> --kind <类型> --pane <pane_id>`。名字必须匹配 `[a-z][a-z0-9_-]{0,31}`，取有意义的短名（如 `billing-api`），后续都用它。
   - 返回 `agent_not_ready`：代理启动时卡在提示上（如信任目录、登录）。用 `herdr agent read <名字>` 读出界面交给用户处理，再 `herdr agent wait <名字> --until idle` 后派单。
2. **派单**：`herdr agent prompt <名字> "<派单说明>" --wait --timeout <毫秒>`。
   - 返回 `agent_blocked` 错误：代理本来就停在审批或提问界面，**消息没有发出**。读出界面交给用户；用户处理完后再派单。
   - `--wait` 正常返回、状态为 `blocked`：消息已发出，代理执行中途停下等审批。读出界面交给用户决定，不得重发，总控也不得替用户点同意。
   - 返回 `timeout` 或 `agent_prompt_stalled`：不能证明消息没送到，不得重发。先 `herdr agent get <名字>` 和 `herdr agent read <名字>` 确认状态，再 `herdr agent wait <名字> --timeout <毫秒>` 继续等。编码类长任务基本都会超时，这是常态。
3. **读结果**：`herdr agent read <名字> --source recent-unwrapped --lines 200`。状态 `idle` 或 `done` 表示可以接收输入，`unknown` 不能证明完成。

### 不能用 agent start 启动的代理与普通命令（如 DSH、测试、服务）

`--kind` 清单之外的代理，启动后 Herdr 可能仍能识别：DSH 运行后在 `herdr agent list` 中显示为 `dsh-tui`。出现在 `agent list` 里的，先用 `herdr agent rename <pane_id> <名字>` 命名，再按上一节的代理命令派单、等待和读取（DSH 的派单链路未实测，首次使用先发一条短指令验证）。不被识别的，按下面的普通命令方式处理。


1. **启动**：`herdr pane run <pane_id> "<启动命令>"`。
2. **派单**：`herdr pane run <pane_id> "<派单说明>"`（发送文本并回车）。派单说明较长或含换行时，先写入文件，再让代理读该文件。
3. **等待与读取**：`herdr pane wait-output <pane_id> --match "[汇报]" --timeout <毫秒>`，`herdr pane read <pane_id> --source recent-unwrapped`。这条路径拿不到 idle、done 等状态，验收只能靠汇报标记和回读产物。

### 混用：Herdr 启动和监看，SendMessage 回报（总控和子会话都是 Claude Code 时推荐）

2026-10-15 实测可行：在 Herdr pane 里用 `agent start --kind claude` 起的会话，会出现在总控的 `ListAgents` 里；总控 `SendMessage` 给它后，空闲的子会话被唤醒执行，再用 `SendMessage` 把结果发回总控。好处是既能用 Herdr 看状态、发现审批卡住，又能拿到完整的结构化汇报，不用读屏幕。

1. 按上文开 pane、`herdr agent start <名字> --kind claude --pane <pane_id>`。
2. 调 `ListAgents` 找新会话。**两边名字不同**：Herdr 名是你起的（如 `hub-probe`），`ListAgents` 名由会话自己生成（如 `ai-content-ops-9b`）。按“刚启动”认出后，让子会话第一条回报带上 `$HERDR_PANE_ID`，核对映射。
3. 派单走 `SendMessage`，可加 `notify_when_idle: true`；汇报要求见模板中的路线二本机会话。
4. 监看走 Herdr：`herdr agent get` 看状态，`blocked` 时读出界面交给用户。
5. 子会话和总控的权限模式不同时，消息会先被扣给对方用户审批；这时改用 `herdr agent prompt` 派单。

### 通用

- **Windows**：命令本身相同，变量写法不同。PowerShell 中 `$HERDR_PANE_ID`、`$HERDR_WORKSPACE_ID` 写成 `$env:HERDR_PANE_ID`、`$env:HERDR_WORKSPACE_ID`；`--cwd "$PWD"` 可直接使用。本技能的脚本都用 `python scripts\<脚本名>` 调用。

- **用户接管**：用户可以随时进 pane 直接输入。总控再派单前，先读一遍最新输出，避免与用户的指令冲突。
- **显式指定目标**：部分命令省略目标时会落到 UI 焦点所在的 pane，那可能是用户的 pane。必须显式传 pane ID、代理名或 `--current`。
- **跨机器**：只在用户要求或授权用别的机器时使用，与 `weicoz-remote-dispatch` 的规则一致；先查那台机器的负载。用 `herdr --machine <标签>` 时，发现与后续每条命令都必须带同一个前缀；远端 pane ID 在远端重新查，不能沿用本机 ID。不得与 `--session`、`--remote` 同时使用。

## 路线二：Claude Code 会话消息

1. **开子会话**：请用户在别的终端、桌面端或云端开 Claude Code 会话，或开后台任务。
2. **列出**：调用 `ListAgents`。地址用表里打印的名字原样填写；只有重名或报错要求区分时，才附上 `[ref]`。
3. **派单**：`SendMessage({to: "<名字>", message: "<派单说明>"})`，内容用下文模板。
   - 对方用户只先看到第一行预览，第一行必须写清这条消息是什么。
   - 正文里的 `@文件路径` 在对方那边不会附带文件。要发原文，或让对方自己读路径。
4. **等完成**：本机会话可以加 `notify_when_idle: true`，它下次空闲或退出时总控收到一次通知。
   - 只有主会话能订阅；订阅可能过期，过期时通知会说明。
   - “空闲”也可能是子会话在等它的用户回答，不等于完成。收到通知后必须回读结果。
   - 不得循环调用 `ListAgents`，也不得反复发“好了吗”。
5. **收汇报**：子会话回复时，把收到的派单消息的 `from` 属性原样填进 `to`，不要由总控猜自己的名字。
6. **云端会话**：能收消息，但还不能回发。不得叫它回复。派单时让它把结果写进仓库分支或 PR，总控拉取后验收；或请用户在网页端或桌面端打开该会话，把结果贴回来。
7. **送达不等于执行**：权限模式和总控不同的会话，会先把跨会话消息交给它的用户审批，也可能过期或拒收。本机会话会返回 `[Cross-session delivery notice]`；Remote Control、云端和桌面端会话不回报这些情况，沉默不等于同意。
8. **不转嫁权限**：总控里被拒绝或会被拦下的操作，不得派给子会话代做，要交回用户决定。
9. **补充指令**：同样用 `SendMessage`。用户直接在子会话里改了方向的，以用户为准，总控更新自己的分工表。

## 派单说明模板

```text
【工作线】<名称> 派单：<一句话目标>
总控：<路线一写总控 pane；路线二写“回复本消息的 from”>
输入：<文件、票据、链接、前置结论>
范围：只改 <路径/分支>；不得改 <路径>；不得提交、推送、部署（除非这里写明已授权）
完成判据：<可验证的检查，如命令与预期输出、文件路径、页面>
产出：<交付物位置>
汇报：完成、失败或受阻时，报告「状态、改动文件、验证命令与结果、未完成项」。
  路线一：输出在本 pane 末尾，以 "[汇报]" 开头。
  路线二本机会话：用 SendMessage 回复，to 填本消息的 from 属性。
  路线二云端会话：把汇报写进 <分支或 PR>，不要尝试回发。
```

第一行即预览，必须能单独看懂。汇报状态只用四种：已完成且已验证、已完成未验证、失败（附关键报错）、受阻（附需要谁做什么）。

## 验收与汇总

- 子会话说“完成”，或 Herdr 显示 `done`，只说明它停下了，不说明结果对。总控必须回读产物：看 diff、跑完成判据里的命令、打开页面或文件。
- 不通过的打回原会话，附上具体证据。不得在总控里悄悄改掉，否则会出现两个写入者。
- 给用户的汇总按工作线列：状态、证据（`路径:行号`、提交号、完整命令）、待用户决策项。没跑的检查标“未验证”。
- 收尾：只关标签以 `hub|<总控 pane ID>|` 开头、状态为“已验收”且已无用的 pane（`herdr pane close <pane_id>`）。没有本总控标签的 pane 一律不关，那是用户或别的总控的。

## 常见坑

- 让云端会话“做完回复我”：它回发不了，总控只会白等。
- 两个会话同时改一个文件或同一分支：后写的覆盖先写的。先分好写入者再派单。
- Herdr 派单超时后重发：同一张单可能被执行两次。
- 用 `--kind dsh` 之类不在清单里的类型起代理：直接报错，改为普通命令启动。
- 混用时拿 Herdr 名去 `SendMessage`：两边名字不同，必须用 `ListAgents` 打印的名字。
- 把总控被拒的命令派给权限更宽的子会话去跑：这是绕过用户的权限决定。
- 开了 pane 忘了打标签：上下文一压缩，这条线就成了无人认领的孤儿 pane。
