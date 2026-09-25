---
name: weicoz-dsh-repos-update-check
description: >
  检查这两个 DeepSeek Harness (DSH) 插件仓库是否有更新：`xiaobright/dsh-anchored-standard`
  与 `yjh051108/dsh-routing-suite`。当用户说“检查/看看这两个仓库(插件)有没有更新”“dsh-anchored-standard、
  dsh-routing-suite 更新了吗”“这两个插件是不是有更新了”，或给出这两个 GitHub 链接想对比本地与远端最新提交时，
  务必使用本 skill。只读检查并输出报告，绝不修改任何文件、不安装/卸载、不 pull。
---

# weicoz-dsh-repos-update-check

只读检查两个 DSH 插件仓库相对本地实装的更新情况，产出报告。**只读**：只 `git fetch` 远端引用并比对哈希，
不改工作区、不 checkout、不 pull、不 reset、不动已安装预设、不卸载已取消插件。所有判断和报告基于 git 事实。

## 什么时候用
- 用户问这两个仓库/插件“有没有更新”“是不是更新了”“看下最新到哪了”。
- 用户贴出这两个 GitHub 链接要求对比本地与远端。
- 需要知道每个仓库相对本地实装新增了哪些提交（哈希、时间、说明），以及是否涉及功能代码还是仅文档、
  本机实装是否需要同步。

## 信号灯语义（关键）
- 🟢 **绿灯** = 本地实装(~/.dsh)与上游一致 / 无需任何同步操作。
- 🔴 **红灯** = 实装落后于上游，需要 pull / 重新同步预设（或注意移除联动）。
- ⚪ **无法对比** = clone 缺失、网络失败或实装未能自动检测——如实说明，不要臆断红/绿。

> ⚠️ 判定基准以**实装(~/.dsh)**为准：`/tmp/dsh-compare` 下的 clone 只是对比镜像，其 local HEAD 落后
> **不代表**你 DSH 的实装落后。不要凭缓存 clone 落后就报红灯。

## 前置
- 需要 `git` 与网络（访问 GitHub）。
- 默认本地缓存 clone 位于 `/tmp/dsh-compare/xiaobright` 与 `/tmp/dsh-compare/routing-suite`。
  可用环境变量覆盖：`DSH_REPOS_XIAOBRIGHT`、`DSH_REPOS_ROUTING`。
- anchored 实装目录默认 `~/.dsh/.agent-presets/anchored-standard`，可用 `DSH_INSTALLED_ANCHORED` 覆盖。

## 步骤

1. 运行捆绑脚本：
   ```bash
   bash "$(skill_dir)/scripts/check_updates.sh"
   ```
   - `skill_dir` 是技能基目录（`~/.agents/skills/weicoz-dsh-repos-update-check`）。
   - 脚本输出每个仓库的：local HEAD、remote HEAD、状态、**信号灯**、新增提交列表。
   - 脚本已内置实装核对：anchored-standard 对比实装目录关键文件(custom-bash.mjs / agent.cordis.yml)
     与远端 `preset/`；routing-suite 检查上游是否移除 mode-boost 及本机是否有真实安装引用。
   - 若某仓库 local clone 缺失，脚本只报远端 HEAD 并给 ⚪——如实告知，不要臆造本地基线。

2. 若某仓库 `HAS update` 且脚本给 🔴/⚪，用 git 事实补充定位新提交动了功能代码还是仅文档：
   ```bash
   git -C <local_dir> diff --name-only <local_head>..<remote_head>
   git -C <local_dir> diff --name-only <local_head>..<remote_head> -- preset shared preset/preset
   ```
   - `preset`/`shared`（anchored-standard）或 `preset/preset`、`mode-boost`（routing-suite）等路径是功能相关；
     只有 README/*.md/.gitmodules 等是文档/仓库级改动。
   - 据此告诉用户“已装预设是否需要重新同步”。

3. 重要联动项（只报告，不自动改）：
   - `routing-suite` 若移除/取消了子模块或插件（历史上 `mode-boost` 被取消），检查本地 DSH 是否还装有该插件的 link 引用；
     若有，明确提醒用户“上游已取消，pull 本地 checkout 会断 link”，并提供可选的卸载路径，但需用户确认后再动手。
   - 检测时**忽略备份/残留文件**（如 `package.json.bak-mode-boost-*`、`mode-boost-activity.jsonl`、`cordis.patch.yml`
     里的 disabled 残留条目）：它们不是真实安装引用，不构成断 link 风险。

## 报告模板
对每个仓库 ALWAYS 用这个结构（中文）：

```
### <repo>
- 信号灯: 🟢 绿灯 / 🔴 红灯 / ⚪ 无法对比
- 状态: 有更新 / 无更新 / 无法对比（注：缓存 clone 状态，不直接决定信号灯）
- 实装核对: 已同步 / 落后（说明依据，如关键文件哈希一致、无 mode-boost 引用等）
- local HEAD : <sha>
- remote HEAD: <sha>
- 新增提交: <n>
  - <sha> | <日期> | <说明>  ...
- 本轮改动类型: 功能代码 / 仅文档 / 仓库级（说明路径）
- 对已装插件影响: 无需同步 / 需同步预设 / 需注意 <风险>
```

结束后给一句总结表：每仓库信号灯（🟢/🔴/⚪）与是否需要额外动作（需用户拍板）。

## 只读保证
- 可与用户明确重申：绝不 checkout/reset/pull/clean，不卸载插件、不改 `~/.dsh`、不拉本地 checkout 到远端。
- 若发现会导致破坏的动作（如“顺手 pull”“顺手卸载 mode-boost”），一律先报告、等用户确认。

## 例子
**输入**：“看看 dsh-anchored-standard 和 dsh-routing-suite 是不是有更新了”
**输出**：运行脚本 → 两者状态与新增提交 → 判定功能/文档改动 → 报告“已装预设是否需同步”+ 任何取消插件风险。
