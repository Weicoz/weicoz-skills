---
name: weicoz-herdr-hub
version: 0.1.0
description: 用一个总控会话管理本机全部 Herdr 窗口：先问清目标项目目录再派单，按 pane 增量采集进度，每 20 分钟汇总一次汇报（会话内 + 手机推送），验收留证据。用户说「管所有 herdr 窗口」「看看各窗口在干什么」「给某个窗口派任务」「每 20 分钟汇报一次」「窗口进度汇总」时使用。只管派单、进度与验收；不做 worktree 集成、不代跑远端任务、不改用户窗口标题和目录。
---

# weicoz-herdr-hub

总控会话的窗口管理台。三件事：**派单**（任务给哪个窗口）、**看进度**（各窗口在干什么）、**汇报**（每 20 分钟给用户一份汇总）。

## 什么时候用

- 用户要把任务派给某个 Herdr 窗口，或让某个项目目录里的窗口干活。
- 用户要一份「现在所有窗口都在干什么」的汇总，或要求周期性汇报。
- 用户要把多个窗口的工作线放在一张台账里看进度、验收、打回。

不用本技能的场合：

| 场景 | 用什么 |
|---|---|
| 只派一条线、且只要标签进度 | `weicoz-session-hub`（它管自己派的线，状态写 pane 标签） |
| 一次性子任务，不需要跨会话 | 宿主子代理 |
| 多个 worktree 并行开发与集成 | `weicoz-multi-worktree-dev-v3` |
| 派到别的机器无人值守跑 | `weicoz-remote-dispatch` |

## 前置检查

1. `echo $HERDR_ENV` 必须是 `1`，且 `herdr --version` 能跑。不在 Herdr 里就说明原因并停手，不要假装能读窗口。
2. `herdr api snapshot` 能返回 JSON；失败先修 herdr，不要继续派单。
3. 入口只有一个：`bin/hub.mjs`。不要绕过它直接拼 `herdr` 命令发指令，否则台账会失联。

## 派单纪律（最重要）

1. **先确定目标项目目录**。缺目录或缺可验证完成判据，就停下来问用户，并给选项（目标目录候选、「其它（我填路径）」），不要猜。
2. **判据必须可验证**：文件名、命令、页面、字段。写「做完」等于没写，直接拒收。
3. **目录不符就拒绝**。用户点名的 pane 当前目录和目标项目不一致时，`dispatch` 以退出码 3 拒绝并给三个选项：在该目录新开 pane / 换一个 pane / 用户明确要求才改目录。不要偷偷 `cd` 别人的窗口。
4. **忙就排队**。目标 `agent_status` 是 `working` 或 `blocked` 时登记为「待发」，空闲后用 `flush` 补发；不打断。
5. **长任务落文件**。任务超过 200 字或多段时，先写 `tasks/<id>.md`（含任务、判据、权限边界、汇报要求），只往 pane 发「读取该路径并执行」。避免粘贴长文本被终端打断。

```bash
# 复用该目录下的空闲 pane；没有就新开
bin/hub.mjs dispatch \
  --project <项目目录> --new \
  --title "billing-api 加取消接口" \
  --criteria "src/billing/cancel.ts 存在且 npm test 通过" \
  --prompt-file <任务文件路径>
```

## 状态词

8 个，顺序即生命周期主干：`待发 → 已发 → 进行中 → 待验收 → 已验收`，旁支 `已打回 / 受阻 / 已取消`。

与 `weicoz-session-hub` 的映射（两边共存时对账用）：已派单→已发/进行中，待验收→待验收，已验收→已验收，已打回→已打回，受阻→受阻。

## 进度采集

- `snapshot` 对比上次采样，只对变化的 pane 读尾部（默认最多 6 个，每次 40 行），省 token。
- 变化信号取 `revision + agent_status + state_change_seq`；三者都不变即「无新输出」。
- 卡住判定：`agent_status=blocked` 立即报；`working` 且连续 40 分钟无变化标「疑似卡住」；空闲但有在途派单 → 转「待验收」。
- 「空闲」包含 `idle`/`done`/`ready`/`finished`/`waiting`。herdr 在代理刚结束一轮时会短暂报 `done`，只认 `idle` 会漏判，派单和 `flush` 因此统一用空闲集合。
- 采集由脚本做，总控只负责判断和措辞。不要人肉扫 19 个 pane。

## 20 分钟汇报

`bin/hub.mjs watch --interval 20 --push` 常驻循环；或每次由主循环调 `report` 一次。

版式固定三段：

1. **一句话总览**：几条有进展 / 待验收 / 受阻 / 排队。
2. **工作线明细表**：项目 · pane · 代理 · 状态 · 近 20 分钟进展 · 下一步；子级派单缩进在父线之下。
3. **需要你处理**：受阻、待验收、排队各列一条，没有就写「无」。

补充规则：

- 未受管的用户窗口单独列，只报「有变化」的，不去碰。
- 推送只在「有变化 / 受阻 / 待验收」时发，只发摘要 + 报告路径；会话内每轮完整汇报照常。
- 报告落 `reports/YYYY-MM-DD/HHMM.md`，留 7 天；台账永久保留，pane 消失时该线转「已取消」。

## 验收

- 轻证据：回读 pane 尾部，确认汇报里的文件、命令确实出现过。
- 重验证（跑完整测试、开页面、查线上）：标「未验证」并写清怎么验，不要冒充已验证。
- `ack --verdict accept` 必须带 `--evidence`，否则脚本拒绝（退出码 2）。
- 打回要写清缺什么，别只写「不合格」。

## 子级派单

两条路，优先第一条：

1. **共享台账**：派单说明里写一句「再往下派单时调用本技能 `register` 登记，带上 `--parent-id`」。子会话用同一 CLI 时自带自己的 `HERDR_PANE_ID`，天然成树。
2. **结构推断兜底**：新 pane + cwd 在父项目内 + 时间相邻。推断结果必须在汇报里标「推测，待你确认」。

## 多总控共用

台账是文件，一份多总控共用。每条记录带 `owner_session`，各自只汇总自己派的线；要全量用 `--all-owners`。不要重写别人的记录。

## 指令

```bash
bin/hub.mjs init                                     # 建状态目录
bin/hub.mjs snapshot [--json]                        # 采样全部 pane + 变化对比
bin/hub.mjs dispatch --title T --criteria C --prompt P | --prompt-file F
                     [--pane ID | --project DIR [--new]] [--force-send]
bin/hub.mjs flush                                    # 补发排队派单
bin/hub.mjs report [--push] [--dry-run] [--since N] [--all-owners] [--quiet]
bin/hub.mjs ls [--all-owners]                        # 台账（树）
bin/hub.mjs ack <id> --verdict accept|reject --evidence ... [--notes ...]
bin/hub.mjs register --title T --target-pane ID [--project DIR] [--status S] [--parent-id ID]
bin/hub.mjs watch [--interval 20] [--push] [--dry-run]
bin/hub.mjs stop                                     # 停 watch
```

退出码：`0` 成功；`1` 错误；`2` 需要用户补信息；`3` 目录冲突已拒绝。

## 状态目录

```
$WEICOZ_HERDR_HUB_STATE_DIR 或 ~/.local/state/weicoz-herdr-hub/
├── registry.json     台账（version 1，lines[]，events 每条最多 20 条）
├── snapshot.json     上次采样（覆盖写）
├── tasks/<id>.md     长任务派单文件
├── reports/<日期>/   汇报（留 7 天）
└── watch.pid         守护进程 pid
```

## 不许做

- 不得关闭、改名、改 cwd 用户自己开的窗口；只关自己开且已验收的 pane。
- 不得替用户点审批、确认危险操作；`blocked` 只上报。
- 不得把定时任务写进 DSH 的 `schedule.json`：该服务启动时只加载一次，运行中写入会被内存快照覆盖，且当前 dsh-tui 宿主没有调度器。要周期汇报用 `watch` 或主循环，不用系统级 launchd（用户已明确否掉）。
- 不得把私有 IP、凭据、绝对用户主目录写进脚本或文档；路径走 `os.homedir()` 与环境变量。

## 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `WEICOZ_HERDR_HUB_STATE_DIR` | 状态目录 | `$HOME/.local/state/weicoz-herdr-hub` |
| `WEICOZ_HERDR_HUB_OWNER` | 总控标识，区分多总控 | `HERDR_PANE_ID` |
| `WEICOZ_HERDR_HUB_NOTIFY_HARNESS` | 推送渠道（传给 `harness-notify --harness`） | `dsh` |
| `WEICOZ_HERDR_HUB_STALL_MINUTES` | 疑似卡住阈值 | `40` |

推送依赖 `harness-notify`；不可用时脚本报「推送失败」并继续写报告，不影响台账。

## 排障

| 现象 | 原因 / 处理 |
|---|---|
| `herdr: command not found` | `herdr` 不在 PATH；先确认已安装并在 Herdr 内运行 |
| `snapshot` 报缺少 `result.snapshot` | herdr 版本不兼容，核对 `herdr --version` 与 `herdr api snapshot` 输出 |
| `--new` 报需要 `HERDR_PANE_ID` | 只能在 Herdr pane 内开新 pane；脱离 Herdr 时改指定已有 pane |
| 派单后没反应 | `snapshot` 看目标 `agent_status`；`blocked` 表示代理停在审批界面，需要用户处理 |
| 报告里全是「无变化」 | 目标 pane 本身没输出；先看是不是命令没敲进去（`pane read` 尾部） |
| 「已有守护进程在跑」 | 上一次 `watch` 还活着；先 `stop` 再启动，避免双开 |
| 「不是本工具的守护进程」 | `watch.pid` 陈旧或 pid 被复用；脚本只删 pid 文件、不发信号，可直接重新 `watch` |
