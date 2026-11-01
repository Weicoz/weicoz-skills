# Harness 支持矩阵与验证方法

L3 手动调用桩依赖各 harness 的“仅手动调用”机制。宿主升级可能改变行为，升级后按本页复核。

## 支持矩阵

| Harness | 机制 | 用户调用 | 依据 |
| --- | --- | --- | --- |
| Claude Code | SKILL.md frontmatter `disable-model-invocation: true` | `/name` | 官方字段；带该字段的 skill 不进入模型的 skill 列表 |
| DSH | 同上 | `/name` | `dsh-tool-skill` README：该类 skill 只经 `/name` 手势进入，目录与 `skill` 工具不暴露 |
| Kimi Code | 同上（也认 `disable_model_invocation`） | `/name` | 源码 `listInvocableSkills()` 过滤 `disableModelInvocation === true`；模型调用返回“can only be triggered by the user” |
| Grok | 同上 | `/name` | 内置文档：“only your slash command runs the skill -- the model cannot invoke it automatically” |
| Antigravity (agy) | 同上（yaml 字段 `disable-model-invocation`） | 斜杠命令 | 二进制含该字段；另有独立的 `disable_slash_command` |
| Codex | 不认上述字段；用 `agents/openai.yaml` 的 `policy.allow_implicit_invocation: false` | `$name` | 内置 skill-creator 文档：显式 `$skill-name` 可用，且不自动加入模型上下文 |

手动调用桩同时写入两种标记，一个桩目录服务全部 harness。

## 验证方法

验证目标：L3 名称不出现在模型收到的 skill 清单中；Hub 与 L2 出现。

- **Claude Code**：新会话中检查系统提示里的 skill 列表，或让模型列出可用 skill 名称。
- **Codex**：
  1. `codex exec --skip-git-repo-check "只回复 OK" < /dev/null`。必须重定向 stdin，否则会等待输入。
  2. 在 `~/.codex/sessions/` 最新的 rollout 中检索 `- <L3名称>:`，预期 0 次；检索 `- weicoz-hub-<领域>:`，预期出现。
  3. app-server 的 `skills/list` 会列出 L3 桩（供 `$` 选择器使用），它不能证明桩没有进入模型上下文。
- **DSH / Kimi / Grok / agy**：新会话中让模型列出可用 skill 名称，或检查宿主的会话日志与调试输出。

某个 harness 验证失败时，把它的发现目录加入 manifest 的 `l3_manual_exclude_dirs`，然后运行 `apply`。

## 跨 skill 调用

规则见 SKILL.md 的“跨 skill 调用”一节：桩与 Hub 内回退、全局规则回退、`deps` 提升。
复核方法：在 L1 skill 中找一条对 L3 的引用（用 `deps` 查），在新会话里触发它，确认模型在调用被拒后改为读取 `library/<name>/SKILL.md`。
