---
name: weicoz-t3-dispatch
version: 1.0.0
description: 经本机 T3 Code（`t3` CLI）把编码任务派给其他 harness（DSH、Kimi Code、Antigravity 等），在独立 worktree 里执行，并巡检、续派、验收。用户说“用 T3 派”“通过 t3 code 分发任务”“让 DSH/Kimi 在 T3 里做”时使用。跨机器派单用 weicoz-remote-dispatch；当前会话自己的子代理不需要本技能。
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
   t3 project remove <worktree 路径>
   wt remove <branch>
   ```
   删除 worktree 前确认不再需要其中未提交的产物（截图、日志）。

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
