# weicoz skills

面向 AI Agent 与终端用户的自研技能集合（支持 DSH、Codex、Claude Code、Antigravity、Kimi Code）。

---

## 开源设计原则与配置规范

**本项目为开源代码仓库。所有 Skill 必须遵循“零硬编码、全面解耦”的安全与可移植性原则：**

1. **严禁硬编码敏感信息**：
   - 严禁在脚本、Prompt、测试用例或文档中硬编码任何私有服务器公网 IP、内网 IP（如 `43.x.x.x`、`10.x.x.x`、`192.168.x.x`）、特定端口或个人域名。
   - 严禁硬编码任何真实 API Key、Token 或认证密钥。
   - 严禁硬编码个人绝对路径（如 `/Users/<username>/...`），一律使用 `HOME` 环境变量或 `path.join(homedir(), ...)` 动态解析。
2. **全量支持环境变量与外部配置**：
   - 所有外部服务请求、端点地址（API Base URL）、模型选择、数据输出根目录必须优先读取对应的环境变量。
   - 变量命名保持规范大写前缀，新增变量必须在根目录的 `.env.example` 中补充空模版与用途说明。
3. **默认端点合规与优雅降级**：
   - 若 Skill 提供默认端点，只能指向公共官方 API（如 `https://api.deepseek.com/v1`）或本地回环地址（`http://127.0.0.1:端口`），不得默认连向私有中转服务器。
   - 当必需配置缺失时，工具必须输出清晰易懂的人性化配置指引，不得静默失败或异常崩溃。
4. **双协议兼容支持（chat 与 respond）**：
   - 调用 LLM 模型时，必须同时支持 `chat`（Chat Completions，`/chat/completions`）与 `respond`（Responses API，`/responses`）两种标准协议。
   - 支持通过环境变量显式指定，或根据端点特征路径/宿主网关配置自适应推断，并具备通用的多字段响应解析能力。

---

## 目录约定

- 每个 Skill 独立存放在 `skills/<skill-name>/`。
- 每个 Skill 必须包含 `SKILL.md`，frontmatter 的 `name` 必须与目录名完全一致。
- 环境变量规范请参考 `.env.example`，本机私有变量推荐保存在本地环境变量配置（如 `~/.zshrc`）。
- 普通输出路径优先使用 `$WEICOZ_OUTPUT_ROOT`，未配置时回退使用当前工作目录。

---

## 校验与质量保证

提交前执行校验脚本：

```bash
./scripts/validate-skills.sh
```

更多 Agent 协作与开发约束，请参阅 [AGENTS.md](./AGENTS.md)。
