---
name: weicoz-worktrunk
description: 本机新建、切换、列出、删除 git worktree 时优先用 worktrunk（wt）替代 git worktree，并按 .worktreeinclude 用写时复制复用构建缓存，减少重复构建、依赖重复和磁盘占用；适用于 Claude Code、Codex、DSH、Kimi Code、Grok、Antigravity 等所有 harness。用户提到 worktree、并行分支、子代理隔离、wt、worktrunk 时用。
version: 1.0.0
compatibility: 需要 wt CLI（https://worktrunk.dev）；缺失时回退 git worktree
---

# weicoz-worktrunk

本机 worktree 一律优先用 [worktrunk](https://github.com/max-sixty/worktrunk)（命令 `wt`）。本技能只定本机约定；命令细节以 `wt <命令> --help` 和官方技能 `worktrunk` 为准。

## 适用范围

- 适用：本机仓库的 worktree 新建、切换、列出、删除、清理。
- 不适用：远端派单（weicoz-remote-dispatch）目标机上的任务目录。那里由派单工具自管 bare 仓库与热槽位，不改用 wt。

## 先检查

1. `command -v wt`。没有时提示安装（macOS：`brew install worktrunk`；其他平台见官方 README），本次回退 `git worktree add`，路径仍按下面的位置约定。
2. 用户级配置 `${XDG_CONFIG_HOME:-$HOME/.config}/worktrunk/config.toml` 应包含：

   ```toml
   worktree-path = "{{ repo_path }}/.worktrees/{{ branch | sanitize }}"

   # 新建 worktree 时复用主 worktree 的构建缓存；仓库无 .worktreeinclude 时不复制。
   [pre-start]
   copy-ignored = "wt step copy-ignored --require-include"
   ```

   缺少时补上，改前留备份。用户级钩子不需要审批；项目级钩子（`.config/wt.toml`）需要审批。
3. 仓库须忽略 `.worktrees/`。`.gitignore` 没有这条时，写入 `.git/info/exclude`（只在本机生效），不擅自改仓库的 `.gitignore`。

## 各 harness 接入

| harness | 接入方式 | 新建 worktree 时 |
|---|---|---|
| Claude Code | `wt config plugins claude install` | `EnterWorktree`、子代理 `isolation: "worktree"`、`--worktree` 都经官方 WorktreeCreate/WorktreeRemove 钩子走 wt；不要再手动 `git worktree add` |
| Codex | `wt config plugins codex install`（技能）；活动标记另装 `codex plugin add worktrunk-markers@worktrunk` | 无生命周期钩子，直接调用下方命令 |
| OpenCode 2 | `wt config plugins opencode install` | 插件注册 worktree 策略，自动走 wt |
| DSH、Kimi Code、Grok、Antigravity 等 | 无插件，靠本技能与全局规则 | 直接调用下方命令 |

## 命令

代理会话没有 shell 集成，统一加 `--no-cd`，再用返回的路径工作。

| 动作 | 命令 |
|---|---|
| 新建 | `wt switch -c <分支> --no-cd [-b <基线>] --format json`，路径取 JSON 的 `path` |
| 进入已有分支 | `wt switch <分支> --no-cd --format json`（没有 worktree 时会建） |
| 另一仓库 | 加全局参数 `-C <仓库路径>` |
| 列出 | `wt list --format json`，路径在 `items[].worktree.path` |
| 删除 | `wt remove <分支> --foreground`；默认在后台删除，脚本里必须加 `--foreground` |
| 清理 | `wt step prune`：只删已合并且超过 `--min-age`（默认 1 天）的 worktree |

- 删除会连同已合并的分支一起删；未合并分支保留。worktree 有未提交改动时需要 `-f`，先确认改动已提交或确实可以丢弃。
- 合并按项目自身流程用 git 完成。`wt merge` 会压缩提交、变基、快进目标分支并删除 worktree，只在用户要求时使用。
- 无 TTY 环境下 `wt switch -c … --no-cd --format json` 可正常返回，不会等待输入。

## 复用构建缓存

- 在仓库根放 `.worktreeinclude`（gitignore 语法），只列可再生的缓存，例如 `target/`、`node_modules/`、`.next/`。
- 不得列入 `.env*`、配置文件、数据库、日志等含凭据或用户数据的文件。
- 含绝对路径的缓存（Python venv、CMake 构建目录、Xcode DerivedData）复制后可能失效，默认不列；需要时实测增量构建再加入。
- APFS、btrfs、XFS、ReFS 用 reflink 写时复制，额外磁盘接近 0。ext4、NTFS 没有 reflink，会完整复制，大目录前先评估磁盘。
- 复制后跑一次增量构建确认缓存命中；不命中时从 `.worktreeinclude` 删掉该项。
- 已有 worktree 补复制：`wt step copy-ignored --to <分支> --require-include`（`--to`、`--from` 接分支名）。

## 安全

- 不得对不可信仓库使用 `-y`：它会自动批准项目钩子并执行其中命令。未审阅 `.config/wt.toml` 的仓库，加 `--no-hooks`。
- 主仓库清理不得用 `git clean -x`。
- 删除他人或其他会话的 worktree 前，先用 `wt list` 和 `git -C <路径> status -s` 确认无未提交改动。

## 回退

wt 不可用或命令失败时，用 git 完成同一动作，位置不变：

```bash
git worktree add -b <分支> <仓库根>/.worktrees/<分支名中的/换成-> <基线>
git worktree remove <路径>
```

汇报中说明回退原因。
