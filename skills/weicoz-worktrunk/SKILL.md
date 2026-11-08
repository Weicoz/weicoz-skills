---
name: weicoz-worktrunk
description: 本机新建、切换、列出、删除 git worktree 时优先用 worktrunk（wt）替代 git worktree，并按 .worktreeinclude 用写时复制复用构建缓存，减少重复构建、依赖重复和磁盘占用；发现项目仍用原生 git worktree 时主动建议迁移并给出完整切换流程。适用于 Claude Code、Codex、DSH、Kimi Code、Grok、Antigravity 等所有 harness。用户提到 worktree、并行分支、子代理隔离、wt、worktrunk 时用。
version: 1.1.0
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

## 发现旧用法时主动建议迁移

在仓库里做 worktree 相关工作时，先只读检查下列信号。命中任一项，就向用户建议迁移到 wt，并附上影响；用户同意前不得移动任何 worktree。

| 信号 | 检查命令 |
|---|---|
| 已有 worktree 不在 wt 约定路径 | `wt list --format json` 中 `items[].worktree.branch_mismatch` 为 `true`；`wt step relocate --dry-run` 列出待移项 |
| 旧位置 | `.claude/worktrees/`、仓库旁的 `<仓库>-wt/` 等目录 |
| 脚本或文档直接建 worktree | `rg -n "git worktree (add\|remove\|move)" --glob '!.worktrees/**'` |
| 仓库未忽略 `.worktrees/` | `git check-ignore -q .worktrees/x` 失败 |
| 本机未装 wt 或未配置 | `command -v wt`；配置缺 `worktree-path` 或 `[pre-start]` |

建议内容写清：待移 worktree 数量与新旧路径、哪些有未提交改动或被锁定、预计收益（复用缓存、统一路径）、风险（见下方流程第 3 步）。

## 切换全流程

按顺序执行；每步失败就停下汇报，不跳步。

1. **只读盘点**
   - `git worktree list --porcelain`、`wt list --format json`、`wt step relocate --dry-run`。
   - 逐个 `git -C <路径> status -s`，记下有未提交改动的 worktree。
   - `git worktree list --porcelain` 中带 `locked` 的 worktree 单独列出。
   - 查当前目录在旧路径里的进程：`lsof -d cwd 2>/dev/null | rg <旧路径前缀>`，包括编辑器、开发服务器、其他代理会话。relocate 不检查占用，会照样移动，这些进程的当前目录随即失效。
2. **取得同意**：一次展示待移清单、新旧路径、有改动项、锁定项、占用进程和回滚方式。
3. **说明风险**
   - 移动后，正在旧路径里运行的进程、编辑器窗口、代理会话的当前目录会失效，需重开。
   - 带绝对路径的缓存（venv、CMake、Xcode DerivedData）移动后可能失效，需重建。
   - 锁定的 worktree 通常属于其他工具或会话，默认不动。
4. **安装与配置**：完成「先检查」三项；`.worktrees/` 写进 `.git/info/exclude`，或经用户同意写进 `.gitignore`。
5. **留回滚清单**：把 `git worktree list --porcelain` 输出存到会话临时目录。
6. **停用占用**：请用户关闭占用旧路径的进程和会话；不得替用户结束他人会话。
7. **迁移**
   - 先 `mkdir -p <仓库根>/.worktrees`：父目录不存在时 relocate 会报 `No such file or directory` 失败。
   - 执行 `wt step relocate [分支...]`，默认移动全部不匹配项；锁定项与用户要保留的不列入。
   - 未提交改动随目录原样移动，不需要提交。`--commit` 会先提交改动，只在用户明确要求时使用。
   - 目标位置已有非 worktree 目录时 relocate 会停下；`--clobber` 会把它改名为 `.bak.<时间戳>`，使用前须征得同意。
   - `relocate` 标注 experimental；失败时改用 `git worktree move <旧> <新>` 逐个迁移。
8. **校验**
   - `wt list --format json` 不再有 `branch_mismatch: true`（未迁移的保留项除外）。
   - `git worktree list` 路径正确；`git worktree prune --dry-run` 无意外条目。
   - 每个已迁移 worktree `git status -s` 与第 1 步记录一致。
9. **更新入口**
   - 仓库脚本和文档里的 `git worktree add/remove` 改为 wt 命令，保留无 wt 时的 git 回退；改动按项目流程提交，需用户同意。
   - 需要复用缓存的仓库加 `.worktreeinclude`，按「复用构建缓存」一节只列可再生缓存。
   - CI 与远端派单脚本不改。
10. **清理**：旧父目录（如 `<仓库>-wt/`）为空时才 `rmdir`；非空时列出剩余内容交用户决定。
11. **汇报**：迁移数、保留项及原因、未验证项、回滚方式。

回滚：按第 5 步清单逐个 `git worktree move <新路径> <旧路径>`，再 `git worktree prune`。

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
