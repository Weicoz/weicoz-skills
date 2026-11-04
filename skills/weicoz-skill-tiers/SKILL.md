---
name: weicoz-skill-tiers
version: 1.7.0
description: skill 分层管理：L1 常驻、L2 短描述桩、L3 由领域 Hub 收纳并可手动 /name 调用，大幅减少常驻上下文的 skill 描述量。只改各 harness 发现目录的软链与生成文件，不改原 skill，Claude Code/Codex/DSH/Kimi/Grok/Antigravity 通用。用于“skill 太多占上下文”“调整或撤销分层”“新装 skill 后分层”“忘了某个 skill 叫什么／找不到某个 skill”“skill 调用被拒绝”“统计 skill 使用次数与常用度”。
---

# weicoz-skill-tiers

## 机制

| 层 | 发现目录中的条目 | 模型可见 | 用户调用 | 适合放入 |
| --- | --- | --- | --- | --- |
| L1 常驻 | 原软链，不变 | 完整描述 | `/name` | 高频；依赖 `context: fork`、`allowed-tools` 等 frontmatter；全局规则点名的 skill |
| L2 短描述桩 | 指向生成的桩：短描述 + 先读原 SKILL.md | 短描述，可自动触发 | `/name` | 中频但需要模型主动想到；被 L1 或未分层 skill 自动调用 |
| L3 手动调用桩 | 指向生成的桩：带“仅手动”标记 | 不可见，经 Hub 索引按需读取 | `/name`（Codex 为 `$name`） | 领域专用、低频；同类 skill 多 |
| Hub | 每个领域一个 `weicoz-hub-*` | 短描述 | `/weicoz-hub-…` | 领域入口，索引表列出该领域的 L3 及用途、路径 |

- 原 skill 不改动。工具只增删软链，并在数据根目录生成桩与 Hub；不删除任何 skill 源。
- “仅手动”标记：frontmatter `disable-model-invocation: true`（Claude Code、DSH、Kimi Code、Grok、Antigravity）加 `agents/openai.yaml` 的 `policy.allow_implicit_invocation: false`（Codex）。依据与验证方法见 [references/harness-support.md](references/harness-support.md)。
- manifest 未列出的 skill 保持原样。原本就带 `disable-model-invocation` 的 skill 不必分层。
- 桩与 Hub 中原 skill 的 frontmatter（`context`、`allowed-tools` 等）不生效，所以依赖这些字段的 skill 必须放 L1。

## 跨 skill 调用

L3 禁止模型自动调用。其他 skill 让模型调用某个 L3 skill 时，宿主会拒绝，或者报告找不到。为此设三道回退：

1. **桩与 Hub 内**：生成的 L2 桩、L3 桩和 Hub 正文都写有回退规则：调用被拒绝或找不到时，读 `library/<name>/SKILL.md` 并执行。
2. **全局规则**：在各 harness 共用的全局规则文件中写入同一条回退规则，覆盖 L1 与未分层 skill。把该文件列进 manifest 的 `global_rules`，`status` 会检查它是否已写入。参考写法：
   > Skill 调用被拒或找不到时读 `~/.agents/skill-tiers/library/<name>/SKILL.md` 执行，不得判定未安装。
3. **提升到 L2**：`deps` 列出 L1 与未分层 skill 对 L3 的引用。核对确属模型自动调用后，把被引用的 skill 移到 L2。如果是让用户手动输入 `/name`，无需处理。

## 操作

```bash
T="$(readlink -f ~/.agents/skills/weicoz-skill-tiers)/scripts/skill_tiers.py"
python3 "$T" ensure                # 会话启动钩子用：无漂移、无引用缺口时静默退出（约 0.5 秒）；有漂移自动 apply，有缺口报一行
python3 "$T" status                # 健康检查：各目录体量、漂移、依赖缺口、全局回退规则、未分层清单
python3 "$T" plan                  # 预演 apply，不改动
python3 "$T" apply                 # 写快照 → 建 library → 生成桩与 Hub → 改链
python3 "$T" deps                  # L1 与未分层 skill 对 L3 的引用
python3 "$T" find <关键词...>      # 按名称与描述查找 skill（含 L3）：层级、所属 Hub、路径
python3 "$T" restore <快照> [--dry-run]   # 恢复到快照时的软链；backups/baseline.json 即完全撤销
python3 "$T" sources               # 只读：skills-manager 中可挂到上游 git 源的 import/local skill，附 set-source 命令
python3 "$T" stats [--top N]       # 统计使用 skill 次数、计算常用度 (1-5) 与调层建议（支持 --tier 与 --json）
```

## 常见任务

- **找 skill**：运行 `find <关键词>`。L3 结果用 `/name`（Codex 为 `$name`）调用，或读取输出中的 SKILL.md 路径。
- **新装 skill 后**：`status` 会把它列进未分层清单。按上面“机制”表的判据写进 manifest（L2 附 ≤80 字短描述；L3 附 ≤40 字用途，突出与同组 skill 的区别），然后依次运行 `plan`、`apply`、`deps`。
- **调整层级**：在 manifest 中移动名称，然后依次运行 `plan`、`apply`、`deps`。在 L2 与 L3 之间调整时，桩会自动重写；只在原本装有该 skill 的发现目录恢复。
- **撤销**：`restore backups/baseline.json`。
- **宿主升级后**：按 harness-support.md 复核 L3 仍不进入模型上下文。哪个宿主不再支持“仅手动”标记，就把它的目录写进 `l3_manual_exclude_dirs`，再运行 `apply`，该目录的 L3 改为移除软链。

## 数据与配置

数据根目录默认 `~/.agents/skill-tiers/`，可用环境变量 `SKILL_TIERS_HOME` 覆盖。

| 路径 | 用途 |
| --- | --- |
| `manifest.json` | 分层定义，格式见 [references/manifest.example.json](references/manifest.example.json) |
| `library/<name>` | 指向原 skill 的稳定软链，供桩与 Hub 引用；不在任何 harness 的扫描范围内 |
| `generated/<name>` | 生成的桩与 Hub |
| `backups/baseline.json` | 首次 apply 前的原始状态，不再覆盖 |
| `backups/snapshot-*.json` | 每次 apply 前的快照 |
| `installed.json` | 各发现目录原本装有的 skill，调层时按原范围恢复 |

manifest 字段：`discovery_dirs`（省略时用内置默认列表）、`global_rules`、`l1`、`l2`、`hubs`、`l3_manual`（默认 `true`）、`l3_manual_exclude_dirs`。

## 约束

- 一个名称只能出现在 L1、L2、Hub 中的一处，脚本会校验。
- 发现目录中的真实目录（非软链）一律不处理，只报告。
- `apply` 只替换现存链接，不补回缺失项。缺失可能是用户或其他管理器主动取消了部署。唯一例外：`l3_manual_exclude_dirs` 中由本工具移除的 L3，调层时按 `installed.json` 恢复。
- 其他同步工具若会重建软链，必须跳过指向 `generated/` 的链接；否则 `status` 会报告漂移，重新运行 `apply` 即可恢复。

## 自动检查（会话启动钩子）

不用常驻后台进程。在支持 SessionStart 钩子的 harness 中挂 `ensure`，每次开会话时检查并修复漂移。各 harness 共用同一批发现目录，任一 harness 开会话即可修复全部目录。

- Claude Code（`~/.claude/settings.json` 的 `hooks.SessionStart`）：
  `{"matcher": "^(startup|resume|clear)$", "hooks": [{"type": "command", "command": "python3 \"$HOME/.agents/skills/weicoz-skill-tiers/scripts/skill_tiers.py\" ensure", "timeout": 15}]}`
- Codex（`~/.codex/hooks.json` 的 `hooks.SessionStart`）：同上命令，`matcher` 为 `startup|resume`。追加到数组末尾，不打乱已有条目的信任编号；新钩子需在 Codex 中确认信任。
- 钩子不得阻断会话：`ensure` 出错只写 stderr，退出码恒为 0。
- 修复发生在会话启动时；同一会话中途同步造成的漂移，在下次开会话或手动 `apply` 时恢复。

## 与 skill 管理器共存

以 skills-manager-plus 为例（其他“库 + 部署软链”式管理器同理）：管理器负责库、安装、更新和部署范围，本工具只负责分层。

| 管理器操作 | 影响 | 处理 |
| --- | --- | --- |
| `skills sync`、界面的同步 | 把桩链接改回原 skill，分层失效 | 会话启动钩子运行 `ensure` 自动恢复；也可手动 `apply` |
| `skills deploy`、`presets deploy`/`apply` | 目标路径已存在时跳过，不影响 | 无 |
| `skills undeploy` | 删除该目录的桩链接，本工具不会补回 | 无 |
| 安装并部署新 skill | 新 skill 以原链接出现，进入未分层清单 | 写入 manifest 后 `apply` |
| `skills check`/`update` | 更新库中原文，桩运行时读取最新原文 | 无；只有短描述需在 manifest 中按需更新 |

- 新 skill 必须经管理器安装，让它记录 git 来源以便更新；不要直接复制进库目录。已验证的完整链路：
  1. `skills-manager-cli skills install https://github.com/<owner>/<repo>/tree/<branch>/<subpath> --git`。`owner/repo/skill` 简写会被拼成 `<repo>/<skill>.git` 而 404。
  2. 参照同类 skill 的 `skills status <name>`：对其 `presets` 逐个 `presets add-skill <预设> <name>`，对其 `deployed_to` 逐个 `skills deploy --agent <agent> <name>`。
  3. 写入 manifest，再 `plan`、`apply`、`deps`。
- import/local 类 skill 不受管理器更新检查，界面的 `up_to_date` 是默认值。用 `sources` 找出能挂源的，再 `skills set-source <name> --git-url <url> --subpath <路径> --dry-run` 核对，确认后加 `--force` 原地改源（保留预设与部署）。
- 管理器显示的“已部署”只表示目标路径存在，不区分原链接与桩。
