---
name: weicoz-session-recall
description: 检索本机所有 harness（DSH / Codex / Claude Code / Antigravity / Kimi Code）的历史会话，回答"我以前做过什么"，定位会话窗口、摘要与产出物，并给出打开原会话的方式。当用户问"上次那个 X 怎么做的""我之前搞过 Y""找找处理过 Z 的会话""那时候的交接记录/产出物在哪"，或需要回顾某项目的来龙去脉、接续旧决策时使用。调用时会顺手把新会话补进索引，不需要用户手动维护。
whenToUse: 用户想找历史会话、回顾之前的工作成果或决策、确认某个需求当时是怎么落地的，或问"索引里还有多少没摘要"。
---

# 会话回顾（weicoz-session-recall）

把本机所有 harness 里"说过话"的历史会话做成一份可检索的索引：每个会话一段中文摘要 + 关键词 + 状态 + 产出物。数据在 `~/.local/state/weicoz-session-recall/`，**与当前所在目录、当前用哪个 harness 无关**——在 DSH、Codex、Claude Code、Antigravity 还是 Kimi Code 里调用，看到的都是同一份索引，五个 harness 的会话一起检索。

## 会话从哪来

| harness | 会话源 | 打开某次会话 |
| --- | --- | --- |
| DSH | `~/.dsh/sessions/<项目目录>/<会话目录>/` | `dsh-tui --resume <session-id>`（GUI 兜底：侧栏「工作区」切到该项目 → 对话列表按标题找） |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | `cd <项目路径> && codex resume <session-id>` |
| Claude Code | `~/.claude/projects/<项目目录>/<uuid>.jsonl` | `cd <项目路径> && claude --resume <session-id>` |
| Antigravity | `~/.gemini/antigravity-cli/brain/<uuid>/.system_generated/logs/transcript.jsonl` | `agy --conversation <session-id>` |
| Kimi Code | `~/.kimi-code/sessions/wd_<cwd_hash>/session_<uuid>/agents/main/wire.jsonl` | `cd <项目路径> && kimi --session <session-id>` |

五个源的会话都按 `cwd` 归到同一个项目名下（如 `--Users-weicoz-File-git-LLM-wiki--`），所以在索引里同一个项目的会话是合流的，不管当时用的是哪个 harness。同一条会话若同时存在于多个 harness，会各自独立成条（它们是不同的记录）。

## 怎么调用

```bash
BIN=~/.agents/skills/weicoz-session-recall/bin

node $BIN/recall.mjs 竞拍 页面          # 检索：默认先看当前项目，没命中再跨全部项目
node $BIN/recall.mjs 飞书 --all         # 明确跨全部项目检索
node $BIN/recall.mjs 毛绒玩具 --project=ai_geo   # 限定某个项目（项目目录名子串）
node $BIN/recall.mjs 飞书 --source=codex # 只看某个 harness（dsh / codex / claude）
node $BIN/recall.mjs 毛绒玩具 --detail  # 只命中一个时直接输出详情原文
node $BIN/recall.mjs --status           # 索引规模 + 待采集数量（按 harness 分）
node $BIN/recall.mjs --status --list    # 外加待采集会话明细
```

每个关键词独立计分：标题 6 > 关键词 5 > 产出物 4 > 摘要 3 > 提问原文 2 > 状态 1。

## 流程与执行流水线

> [!IMPORTANT]
> **执行纪律（唯一意图约束）**：
> 收到 `/weicoz-session-recall <任何描述>` 时，**唯一的意图是在全机会话历史中检索记录**。
> - **严禁**将用户的输入当成现场开发指令或排查任务（绝对不要去查系统进程、端口、源码或执行全盘 find）；
> - **必须严格按照以下三步流水线执行**：分析拆词 → 程序召回 → Jev 贴合度重排呈现。

### 阶段 1：模型语义分析与关键词拆解（Query Understanding）
当用户输入是一句完整的自然语言长句时（如提问、报错或需求片段）：
- 模型必须先分析该句的核心意图，提炼出 **2~4 个最具区分度的核心检索词**（优先：项目名/目录名 > 具体功能/模块 > 核心技术/文件 > 关键动作）；
- **严禁**把整句自然语言直接原样透传给脚本（整句输入会导致 0 命中）；
- *示例*：
  - `DSH插件不生效，重启之后` → 拆解为 `DSH 插件 重启`
  - `上次在 ai_geo 做毛绒玩具竞拍的倒计时组件` → 拆解为 `竞拍 倒计时 毛绒玩具`
  - `之前腾讯云 134 节点配置 EasyTier 中继的记录在哪` → 拆解为 `腾讯云 EasyTier 中继 134`

### 阶段 2：程序执行多路召回（Programmatic Candidate Retrieval）
由程序执行命中检索，初筛候选池（默认获取前 5~10 条）：
```bash
node $BIN/recall.mjs <拆解后的关键词...> --limit=10 [--all] [--json]
```
- **默认当前项目优先**：当前仓库有命中则优先展示；若无命中脚本已自动跨全部项目召回并在输出标明；
- 程序毫秒级返回一组候选会话窗口（含 ID、时间、项目、来源 Harness、标题、中文摘要、产出物）；
- 若一个词都没命中，由模型主动换近义词或减少非核心词重试一次，不要轻易放弃。

### 阶段 3：贴合度判断与评分倒序呈现（JV / 大模型决策重排）
召回候选后，对比各候选事实与用户原始诉求，执行重排与贴合度打分：

- **决策引擎策略（无缝降级，零配置门槛）**：
  - **若环境配有 JV（Jev / TypeSafe 决策头）**：可调用 JV 决策服务从候选中执行结构化选择与打分；
  - **若未配置 JV（默认情况）**：**默认由当前 Harness 大模型原生推理直接处理**（零外部配置依赖，不强求独立 Key）。大模型自身基于召回事实进行语义比对与打分。

- **执行规则（两套引擎保持一致的输出契约）**：
  1. **真实事实对比**：以用户**原始句子中的诉求**为唯一锚点，比对各候选会话的「标题 + 中文摘要 + 产出物 + 时间」；
  2. **打分与排序**：对每个候选会话评估其贴合度（0~100 分），**严格按贴合度评分从高到低倒序排列**；
  3. **输出呈现**：
     - **首项置顶**：标注 `(最贴合 / 推荐)`，用 1~2 句直接陈述选择理由（说明为什么它最契合用户原始长句的诉求）；
     - **次优候选递减排列**：列出得分较低的候选项（摘要作为主体）；
     - **保留恢复入口**：每项末尾给出打开原会话的命令（`回到会话：...`）或详情路径。

### 展开与回到会话
- 详情文件在 `~/.local/state/weicoz-session-recall/detail/<项目目录名>/<日期>-<会话id>.md`，含完整摘要、关键词、产出物、用户消息节选与打开原会话的方式；
- 用户想回到原会话时，按记录里的 `来源` 给对应方式：
  - **DSH**：`dsh-tui --resume <session-id>`
  - **Codex**：`cd <项目路径> && codex resume <session-id>`
  - **Claude Code**：`cd <项目路径> && claude --resume <session-id>`
  - **Antigravity**：`agy --conversation <session-id>`
  - **Kimi Code**：`cd <项目路径> && kimi --session <session-id>`

   `recall.mjs` 每条结果的「回到会话」一行已经给出了正确命令，直接转述即可。DSH 那条走的是本机的 `dsh-tui`（`~/.local/bin/dsh-tui`）：`--resume <id>` 恢复指定会话，不带 id 是恢复最近一次，`-c` / `--continue` 同义；界面里显示的短 id（`#` + 前 8 位）也能用来定位。注意别写成 `dsh sessions`（不是命令）或 `dsh web --resume`（没这个参数）——这两个都会报错。只有在目标机器没装 dsh-tui 时才退回 GUI：侧栏「工作区」切到该会话所属项目，再在对话列表里按标题找（列表按最近活动排序，较老的要先展开「其余 N 个会话」）。

   如果用户只是想回顾内容，直接从详情文件复述即可，不必打开原会话。

## 自动采集（完全无感，不需要用户操心）

`recall.mjs` **检索过程纯内存只读，零前台开销（< 30ms）**：

- **极速返回**：前台一律不阻塞等待大模型，立刻基于现有已落盘索引秒级返回检索结果；
- **后台异步静默触发**：检索完成后在后台静默补录新产生的安静会话（日志 `~/.local/state/weicoz-session-recall/digest.log`），完全不影响前台命令的退出与响应；
- **防并发排他锁**：内置基于文件系统的原子独占排他锁（`open('wx')` + PID 存活检测）。已有任务运行时直接跳过，绝不重复拉起多个采集进程，杜绝并发冲突。

**正在写入的会话不采**（距上次写入不到 10 分钟，可用 `SESSION_RECALL_ACTIVE_MS` 调）：这类会话的摘要生成完就过时，而且它通常正是用户此刻正在用的那个——以前每次检索都会停下来重新摘要它一次，白等十几秒。它会一直保持"未采集"，等安静下来后下一次调用自动补上，输出末尾会提示一句。需要连它一起采时给 `digest.mjs` 加 `--include-active`。

所以用户不需要记任何定时任务。

## 定时兜底

定时兜底用的是 **DSH 自带的自动化任务**（侧栏「自动化任务」页面）：宿主级持久，DSH 重启后仍在，到点由宿主唤醒原会话执行。**不是**系统级的 cron / launchd，也不需要安装任何东西。

当前已建好一条：

- 标题「会话摘要采集」，`cron: {expression: "0 */2 * * *", time_zone: "Asia/Singapore"}`，跑的就是同一个 `bin/digest.mjs`（一次采集覆盖五个 harness）。
- 要停、改频率、看下次触发时间：去「自动化任务」页面。
- 要重建（换机器、或误删）：让 agent 用 `schedule_create` 建一条，`title` + 上面的 `cron` 两个参数就够，`prompt` 用下面这段：

```
运行本机会话摘要采集，只做采集，不要改任何代码或文档：

    node ~/.agents/skills/weicoz-session-recall/bin/digest.mjs

完成后用一句话报告本次处理的会话数、失败数、耗时；失败数大于 0 时列出失败会话 ID 与错误原因。
```

在另一台机器上装这套东西只有三步：把 `weicoz-session-recall/` 放到 `~/.agents/skills/`（同时给 `~/.codex/skills/`、`~/.claude/skills/`、`~/.gemini/config/skills/`、`~/.kimi-code/skills/` 建同名软链，各 harness 就都能调用）、跑一次 `bin/digest.mjs` 建立索引、再照上面建一条自动化任务。

## DSH Web 界面插件集成（图形化悬浮摘要、智能重命名与 ID 直达）

在 DSH Web 图形化界面中，可搭配安装一体化配套插件 `dsh-session-recall`（已完整合并原 `dsh-session-jump` 的全部能力），与本 skill 形成完整的会话回顾、智能重命名与直达闭环：

### `dsh-session-recall`（全功能会话回顾与直达插件）
- **仓库地址**：[Weicoz/dsh-session-recall](https://github.com/Weicoz/dsh-session-recall)（本地源码：`/Users/weicoz/File/git/dsh-session-recall`）
- **核心功能**：
  - **悬停即读**：在 DSH 侧栏会话列表中悬停任意会话，悬浮卡片直接展示由本 skill 采集的中文摘要与更新时间；
  - **点击看全文**：点击摘要块弹出完整摘要详情窗口（包含会话标题、关联项目、完整摘要与时间）；
  - **模型一键重命名**：弹窗底部提供「用摘要更新会话标题」按钮，调用宿主 LLM 服务根据摘要自动提炼 12~24 字精准标题并就地更新侧栏会话标题（模型不可用时退回摘要首句）；
  - **会话直达面板（设置页）**：解决 DSH 内置搜索中 `session_id` 属于 `UNINDEXED` 字段导致无法按 ID 检索的痛点，支持按完整 UUID、前 8 位短 ID、项目路径或标题实时过滤全机 1500+ 会话并一键切换主视图；
  - **摘要联动展示**：直达搜索结果列表中实时联动呈现已采集的 `💡 <中文摘要>` 与 `[全文]` 弹窗，直观确认会话背景；
  - **会话标题栏复制 ID**：在当前打开的会话标题栏右侧提供「复制会话 id」按钮，方便在命令行或其它 harness 中联动检索。
- **安装与生效**：
  ```bash
  # 方式 A：通过本地目录链接装载（开发推荐）
  # 在 ~/.dsh/profiles/web/package.json 中添加 dependencies 与 dsh.profile.bundles，执行 pnpm install

  # 方式 B：通过插件管理器装载本地 bundle
  plugin_manager install_bundle /Users/weicoz/File/git/dsh-session-recall

  # 方式 C：从 GitHub 仓库安装
  dsh plugin --profile web add https://github.com/Weicoz/dsh-session-recall
  ```
  > [!NOTE]
  > 宿主端代码（`lib/host.js`）或新增 bundle 生效必须**重启 `dsh web`**（受 Node ESM 模块缓存影响）；前端页面调整（`lib/client.js`）仅需刷新浏览器生效。

## 交接口径

用户往往不是要"看文档"，而是要**接着那段工作往下做**。复述时优先讲：当时的目标、关键决策与理由、产出了什么、留下什么没做完。索引里的"状态"列（已完成 / 进行中 / 中断 / 仅咨询）就是这个用途的入口。

## 边界

- 索引由脚本生成（`bin/digest.mjs`），**不要手工编辑** `~/.local/state/weicoz-session-recall/index.md`；要改格式改 `bin/lib/store.mjs` 里的 `renderIndex/renderDetail`。
- 覆盖 **DSH / Codex / Claude Code / Antigravity / Kimi Code** 五个 harness；其他 harness 的会话暂不采集。要加新 harness：照着 `bin/lib/sources/` 里的适配器写一个，在 `bin/lib/harness.mjs` 的 `SOURCES` 里注册即可，水位线键用 `<harness>:<id>` 前缀。
- 索引只收录**有人打过字**的会话。两类噪音会被排除：① 空壳会话（DSH 阈值 `EMPTY_SESSION_BYTES = 4000`；Kimi Code 阈值 `EMPTY_KIMI_BYTES = 1000`；Codex / Claude Code / Antigravity 按是否有用户消息判断）；② **无头、自动化任务、定时任务、探针与子代理会话**——程序驱动、定时调度、探针探测或跨代理委派的会话均不采集。判据分别是：Codex 看 `originator: codex_exec` / `subagent` 以及用户消息首条含 `Automation:` / `定时任务：` / `probe.txt`；DSH 自动读取 `~/.dsh/storages/schedule.json` 排除所有定时自动化任务绑定的会话，且看会话头 `origin === 'subagent'` / `delegationDepth > 0` 与首部自动化特征；Claude Code 仅扫描项目根级 `.jsonl`（物理跳过 `subagents/*.jsonl` 目录），跳过 `isSidechain: true` 轮次，首条看 `promptSource: sdk` / `promptSource: system` / `entrypoint: sdk-cli` 及自动化模式词；Antigravity 看 `conversation_summaries.db` 元数据中 `nesting_depth > 0` 或 `parent_conversation_id` 存在（即子代理），或首条含 `SYSTEM_MESSAGE` / 自动化与探针特征；Kimi Code 仅扫描 `agents/main/wire.jsonl`（物理忽略 `agents/agent-*/` 子代理目录），读取 `state.json` 判定 `parentSessionId` / `parentAgentId` / `type === 'sub'`，并匹配自动化、探针与委派模式词；代码在五个适配器的 `isHeadlessFile()` 与 `scanSessions()` 里。这些会话在 state 里留一条 `headless: true` 记录但不重复解析、不调模型，索引与检索都会跳过；详情文件保留不删。
- 摘要由模型生成，可能不完整；要精确的原文、命令、代码时读详情文件，两者冲突时信原话。
- 找"文档/资料"用各项目自己的检索（LLM-wiki 是 `npm run query`），找"哪次会话做过什么"才用这个 skill。
