# AI Agent 开发与维护规范（weicoz-skills）

适用于在本项目中开发、重构、审查或维护 Skill 的所有 AI Agent（Codex、DSH、Claude Code、Antigravity、Kimi Code 等）。

---

## 核心原则：开源合规与配置零硬编码

**本项目面向开源社区。所有代码、脚本、配置与文档必须满足随时公开发布的安全与隐私标准。**

### 1. 严禁硬编码敏感信息与私有网络地址
- **禁止硬编码私有 IP 与端口**：严禁在任何脚本、配置文件、文档或默认回退逻辑中写入私有服务器 IP（如 `43.x.x.x`、`10.x.x.x`、`192.168.x.x` 等）或非公开端口。
- **禁止硬编码个人凭据**：API Key、Access Token、数据库密码、鉴权 Secret 必须动态读取，严禁在源码或 Git 追踪文件中出现任何明文值。
- **禁止写死绝对用户路径**：严禁在通用代码中硬编码宿主机特定用户名（如 `/Users/weicoz/...` 或 `/Users/jy/...`）。路径必须通过 `process.env.HOME`、`os.homedir()`、`path.join()` 或对应环境变量动态解析；测试用例使用虚拟 mock 路径（如 `/home/user/...` 或 `/Users/developer/...`）。

---

## 配置解耦标准

所有涉及外部接口、模型调用、服务连接或自定义存储的 Skill，必须遵循以下标准：

### 1. 统一环境变量规范
- **环境变量优先**：所有服务端点（API URL）、访问密钥（API Key / Token）、外部模型名称（Model Name）、自定义存储根目录必须优先从环境变量读取。
- **前缀与命名**：Skill 专用变量必须使用清晰的大写前缀（如 `SESSION_RECALL_API_URL`、`WEICOZ_FEISHU_BASE_TOKEN` 等）。
- **同步更新 `.env.example`**：任何 Skill 若新增了环境变量依赖，**必须**同步在仓库根目录的 `.env.example` 中增加变量名及用途注释（保留空值，不得填写真实值）。

### 2. 默认值与通用回退
- **默认端点规范**：若必须提供默认地址，只能使用官方公开标准域名（如 `https://api.deepseek.com/v1`、`https://api.openai.com/v1`）或本地回环地址（`http://127.0.0.1:端口`），不得指向任何未公开的私有云服务器。
- **优雅拦截与友好报错**：当必需的环境变量未配置时，脚本或工具必须输出清晰易懂的人性化指引，告知用户如何配置：
  ```text
  错误：未检测到 API 凭据。
  请先配置环境变量：
    export SESSION_RECALL_API_KEY="sk-..."
    export SESSION_RECALL_API_URL="https://..."  # 可选，默认为官方端点
  ```
  严禁静默失败、死循环重试或抛出未捕获的不可读堆栈。

### 3. 多协议支持标准（chat 与 respond）
所有涉及 LLM 模型调用的通用实现，**必须同时兼容支持**主流的两种接口协议规范：
- **`chat` 协议（OpenAI Chat Completions 规范）**：端点特征通常为 `/chat/completions`，请求体采用 `{ model, messages: [...], temperature, max_tokens }`，响应正文从 `choices[0].message.content` 解析。
- **`respond`（或 `responses`）协议（OpenAI Responses API 规范）**：端点特征通常为 `/responses`，请求体采用 `{ model, instructions, input: [...], temperature, max_output_tokens }`，响应正文从 `output[].content[].text` 或 `output_text` 解析。
- **自适应识别与显式覆盖**：必须支持通过环境变量（如 `<SKILL>_PROTOCOL`）显式指定 `chat` 或 `respond`；若未显式指定，必须根据 URL 特征路径（如是否包含 `/responses`）或宿主适配器配置（如 `openai-responses` / `openai-chat`）自适应识别，并具备通用的多字段响应解析兜底能力。

---

## Skill 目录与元数据要求

1. **单 Skill 独立性**：每个 Skill 独立维护在 `skills/<skill-name>/` 下，目录名必须与 `SKILL.md` frontmatter 中的 `name` 完全一致。
2. **规范文件结构**：
   - `SKILL.md`：核心定义，包含 `name`、`description` 及详细操作指引。
   - `scripts/` 或 `bin/`：实现脚本。
   - `references/`：参考资料或格式示例。
3. **跨 Harness 兼容**：Skill 遵循标准规范，确保 DSH、Codex、Claude Code、Antigravity、Kimi Code 五端均可识别与调用。
