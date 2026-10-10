# 代理适配

每个代理是一组命令模板。内置的定义在 `scripts/rd` 的 `AGENTS` 里，可以在机器清单里用同名小节覆盖，也可以新增。

## 内置代理

| 名称 | 启动方式 | 换模型 | 推理强度 | 验证情况 |
| --- | --- | --- | --- | --- |
| `codex` | `codex exec`，完全访问、不询问、JSON 输出 | `--model` | `--effort` | 启动、续跑、提交回传都实际跑通过 |
| `dsh` | `dsh headless --json` | 不支持，由远端的 headless profile 决定 | 不支持 | 命令取自帮助文档，未实跑 |
| `kimi` | `kimi --auto`，stream-json 输出 | `--model`（别名见远端 `~/.kimi-code/config.toml`） | 不支持 | 命令取自帮助文档，未实跑 |
| `claude` | `claude -p`，跳过权限询问，stream-json 输出 | `--model` | 不支持 | 命令取自帮助文档，未实跑 |

未实跑的代理第一次使用时要确认两件事：启动后 `rd logs <job>` 有输出、文件确实写进了 worktree；续跑时 `rd resume` 打印出了会话编号。会话编号取不到，就在日志里找到它的字段名，按下面的方法改 `session_regex`。

## 模板里能用的变量

命令在任务的 worktree 目录里执行，由 `sh` 解释。

| 变量 | 含义 |
| --- | --- |
| `$RD_WT` | worktree 路径（也是当前目录） |
| `$RD_JOB_DIR` | 这个任务的日志目录 |
| `$RD_PROMPT` | 本轮提示词文件 |
| `$RD_ROUND` | 第几轮（首次为 1，每次续跑加 1） |
| `{model_args}` | 由 `--model`、`--effort` 生成的参数，没有就是空 |
| `{session}` | 续跑时的会话编号 |

命令的标准输出存为 `stdout.r<轮次>.log`，会话编号就是用 `session_regex` 从这里匹配出来的。

## 覆盖或新增

```ini
[agent:codex]
; 收紧权限：只允许写工作区
start = codex exec -C "$RD_WT" -s workspace-write -c approval_policy=never --json {model_args} - < "$RD_PROMPT"

[agent:myagent]
start = myagent run --json {model_args} < "$RD_PROMPT"
resume = myagent run --json --continue {session} {model_args} < "$RD_PROMPT"
model = --model {model}
session_regex = "conversation":\s*"([^"]+)"
```

各字段：

- `start`：必填，首次启动。
- `resume`：续跑。不写就不能 `rd resume`。
- `model`、`effort`：对应 `--model`、`--effort` 的参数写法。不写表示不支持，用户传了会报错。
- `session_regex`：从输出里取会话编号的正则，第一个括号是编号。默认匹配 `session_id`、`sessionId`、`thread_id` 三种字段名。
- `bin`：`rd doctor` 用来检查是否安装的命令名，默认取 `start` 的第一个词。

只覆盖一个字段时，其余字段沿用内置定义。
