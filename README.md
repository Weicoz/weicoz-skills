# weicoz skills

面向 AI Agent 与终端用户的自研技能集合（支持 DSH、Codex、Claude Code、Antigravity、Kimi Code）。

每个 Skill 独立成目录，自带 `version`，通过软链接挂到各 harness 的 skills 目录。共 **66 个 Skill**。

---

## 快速开始

**1. 克隆仓库**

```bash
git clone https://codeberg.org/jy_project/weicoz-skills.git
cd weicoz-skills
```

**2. 挂到 harness**

每个 harness 读取各自的 skills 目录。把需要的 Skill 软链进去即可（指向本仓库，不要复制正文）：

```bash
SKILL=weicoz-feishu-task-tracker
ln -s "$PWD/skills/$SKILL" ~/.agents/skills/$SKILL         # 通用入口
ln -s "$PWD/skills/$SKILL" ~/.dsh/skills/$SKILL            # DSH
ln -s "$PWD/skills/$SKILL" ~/.codex/skills/$SKILL          # Codex
ln -s "$PWD/skills/$SKILL" ~/.claude/skills/$SKILL         # Claude Code
ln -s "$PWD/skills/$SKILL" ~/.kimi-code/skills/$SKILL      # Kimi Code
ln -s "$PWD/skills/$SKILL" ~/.gemini/config/skills/$SKILL  # Antigravity
```

只挂需要的，不必全量。同一 Skill 只维护一份源文件，多入口全部指向它。

挂载数量多时用脚本一次建好，并随时检查有没有指错地方：

```bash
./scripts/sync-skills.sh           # 只检查：软链是否都指向本仓库
./scripts/sync-skills.sh --apply   # 修复：重指漂移的软链、补上缺失挂载
./scripts/sync-skills.sh --apply --skill weicoz-feishu-task-tracker   # 只处理一个
```

脚本只管理 `weicoz-*` 条目，不碰其他 Skill。harness 目录可用 `WEICOZ_SKILL_HARNESS_DIRS`（冒号分隔）覆盖。

**3. 配置私有凭据**

需要外部服务的 Skill 带 `config.example.yaml` 模板。复制到 `~/.config/<skill-name>/config.yaml`，填真实值，权限设 `600`。**真实配置永不进 Git。**

```bash
mkdir -p ~/.config/weicoz-feishu-task-tracker
cp skills/weicoz-feishu-task-tracker/config.example.yaml ~/.config/weicoz-feishu-task-tracker/config.yaml
chmod 600 ~/.config/weicoz-feishu-task-tracker/config.yaml
```

环境变量类配置参考 [.env.example](./.env.example)。

---

## Skill 清单

版本号取自各 `SKILL.md` frontmatter 的 `version` 字段。

#### 飞书与办公自动化

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-feishu-task-tracker`](skills/weicoz-feishu-task-tracker/) | 2.1.0 | 读飞书任务清单、盘点逾期临期、写评论并 @ 负责人、改状态与进度、同步关注人；含只读盘点与评论写入两个脚本 |
| [`weicoz-feishu-receipt-base`](skills/weicoz-feishu-receipt-base/) | 1.0.0 | 飞书多维表财务收款入账、渠道返点对账与开发绩效核算 |
| [`weicoz-feishu-salary-base`](skills/weicoz-feishu-salary-base/) | 1.0.0 | 飞书工资多维表读写、按月生成草稿、导入个税表回填社保与个税 |
| [`weicoz-mail-guard`](skills/weicoz-mail-guard/) | 1.4.4 | 多邮箱只读拉取、单次调用 brief 简报、默认直跑可选子代理、验证码与登录链接提取、时间与来源邮箱强制标注 |
| [`weicoz-monthly-reconciliation-xlsx`](skills/weicoz-monthly-reconciliation-xlsx/) | 1.0.0 | 按固定 Excel 模板生成月度对账单，不改列、先预览后生成 |
| [`weicoz-harness-notify`](skills/weicoz-harness-notify/) | 1.0.0 | 为 Codex / Claude Code / DSH / AGY 安装并验证完成通知（Bark、TG、飞书、ntfy） |

#### 客户需求、报价与交付文档

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-pm-requirements-from-docs`](skills/weicoz-pm-requirements-from-docs/) | 1.0.0 | 把客户需求材料整理成 PM 可读的需求文档：业务模型、流程、身份、奖励、报价 |
| [`weicoz-custom-feature-checklist`](skills/weicoz-custom-feature-checklist/) | 1.0.0 | 把沟通记录整理成可交付功能清单初稿，只留定制部分并区分待确认项 |
| [`weicoz-demand-mindmap-organizer`](skills/weicoz-demand-mindmap-organizer/) | 1.0.0 | 把沟通记录整理成客户可读需求导图，直接产出可打开的 .xmind 文件 |
| [`weicoz-requirement-spec-writer`](skills/weicoz-requirement-spec-writer/) | 1.0.0 | 追问澄清需求边界，生成并持续维护 SPEC.md / PRD |
| [`weicoz-project-quote-estimator`](skills/weicoz-project-quote-estimator/) | 1.0.0 | 生成可签约核对的逐项报价与第三方成本文档（含服务器、上架费） |
| [`weicoz-custom-contract-docx`](skills/weicoz-custom-contract-docx/) | 1.0.0 | 按 .docx 模板生成定制开发合同并完成渲染验收 |
| [`weicoz-jy-design-demand-archive`](skills/weicoz-jy-design-demand-archive/) | 1.0.0 | 把客户沟通与附件归档到 jy-design 项目目录，再产出导图、需求或报价 |
| [`weicoz-mode-commerce-research`](skills/weicoz-mode-commerce-research/) | 1.0.0 | 研究模式电商、社群团购、多层级分销的商业模式与系统表达 |

#### 产品机会与市场调研

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-ai-product-opportunity`](skills/weicoz-ai-product-opportunity/) | 1.0.0 | 用购买理由、供需失衡、MVP 闭环、Alpha 窗口评估 AI 产品机会 |
| [`weicoz-startup-pressure-test`](skills/weicoz-startup-pressure-test/) | 1.0.0 | 用早期创业框架压测想法，给 strong / weak / pivot 判定与两周计划 |
| [`weicoz-always-on-track-founder`](skills/weicoz-always-on-track-founder/) | 1.0.0 | 把创业直播笔记转成可执行的决策与行动系统 |
| [`weicoz-brd-market-research`](skills/weicoz-brd-market-research/) | 1.0.0 | 3 小时 BRD 流程评估产品机会，输出 GO / NO-GO 决策 |
| [`weicoz-brd-kdroi-fusion`](skills/weicoz-brd-kdroi-fusion/) | 1.0.0 | KDRoi 关键词 Gate + 6 步 BRD，一体评估出海产品机会 |
| [`weicoz-demand-mining-kdroi`](skills/weicoz-demand-mining-kdroi/) | 1.0.0 | 基于搜索量、CPC、KD 做工具站需求挖掘与四步验证 |
| [`weicoz-first-keyword-free-tools`](skills/weicoz-first-keyword-free-tools/) | 1.0.0 | 用免费工具从一个种子词里选出值得先做的第一个关键词 |
| [`weicoz-liu-xiaopai-perspective`](skills/weicoz-liu-xiaopai-perspective/) | 1.0.0 | 以刘小排的思维框架与表达方式做产品决策与效率诊断 |
| [`weicoz-cn-demand-liu-xiaopai`](skills/weicoz-cn-demand-liu-xiaopai/) | 1.0.0 | 中文平台近 30 天痛点挖掘，再用刘小排视角判断可持续交易 |
| [`weicoz-reddit-pain-evidence`](skills/weicoz-reddit-pain-evidence/) | 1.0.0 | 从 Reddit 帖子与评论挖真实痛点，按抱怨型标准判定真需求 |
| [`weicoz-reddit-pain-liu-xiaopai`](skills/weicoz-reddit-pain-liu-xiaopai/) | 1.0.0 | Reddit 痛点证据 + 刘小排视角 + 可持续交易判断一体化 |
| [`weicoz-reddit-opportunity-semrush`](skills/weicoz-reddit-opportunity-semrush/) | 1.0.0 | Reddit 需求交叉验证后用 Semrush 门槛筛选，输出机会报告 |
| [`weicoz-reddit-research-automation`](skills/weicoz-reddit-research-automation/) | 1.0.0 | 可定时、可重复的 Reddit 研究流水线，产出带证据的 Markdown 报告 |
| [`weicoz-toolify-month-rank-filter`](skills/weicoz-toolify-month-rank-filter/) | 1.0.0 | 查 Toolify 月度 AI 工具榜，按访问量、增长、类型筛选 |
| [`weicoz-semrush-ego-browser`](skills/weicoz-semrush-ego-browser/) | 1.0.0 | 用真实浏览器操作 Semrush，按 KD / Volume / CPC 阈值提取数据 |

#### 内容写作与公众号

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-wechat-article-writer`](skills/weicoz-wechat-article-writer/) | 1.0.0 | 公众号文章写作：选题、标题、大纲、正文、改写、审稿与头条压缩 |
| [`weicoz-wechat-official-account-operator`](skills/weicoz-wechat-official-account-operator/) | 1.0.0 | 公众号运营：定位、选题、发布计划、增长转化与数据复盘 |
| [`weicoz-wechat-save-template-deploy`](skills/weicoz-wechat-save-template-deploy/) | 1.0.0 | wechat-save-template 本地预检、远端部署与会话存档入库验证 |
| [`weicoz-gpt-5-6-prompt-compiler`](skills/weicoz-gpt-5-6-prompt-compiler/) | 1.0.0 | 把零散需求编译成可直接发给 GPT 的轻量提示词 |

#### 视觉设计与图像提示词

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-gptimage2-prompts`](skills/weicoz-gptimage2-prompts/) | 1.0.0 | GPT-Image-2 提示词总入口：判断场景并补齐主体、文字、构图、比例 |
| [`weicoz-gptimage2-commercial-visuals`](skills/weicoz-gptimage2-commercial-visuals/) | 1.0.0 | 电商主图、品牌海报、Banner、产品套图的商业视觉提示词 |
| [`weicoz-gptimage2-info-ui-text`](skills/weicoz-gptimage2-info-ui-text/) | 1.0.0 | 信息图、UI 截图、中文长文字海报等文字密集图提示词 |
| [`weicoz-gptimage2-style-reference-edit`](skills/weicoz-gptimage2-style-reference-edit/) | 1.0.0 | 风格化、参考图编辑、真实摄影、角色一致性与艺术玩法提示词 |
| [`weicoz-goosedesigns`](skills/weicoz-goosedesigns/) | 1.0.0 | 做页面前先检索本地视觉参考库，保证设计多样性 |
| [`weicoz-page-design-harness`](skills/weicoz-page-design-harness/) | 1.0.0 | 按产品、用户、约束与验收标准设计与审查页面 |
| [`weicoz-page-layout-ascii-guide`](skills/weicoz-page-layout-ascii-guide/) | 1.0.0 | 内容已知但不知如何排版时，产出 ASCII 页面骨架 |
| [`weicoz-ui-studio`](skills/weicoz-ui-studio/) | 1.2.1 | 完整继承 Free 设计流程、对比页、素材检索与取证，再加交互、19 套组件、工作区及评审增强 |
| [`weicoz-tree-swimlane-diagram`](skills/weicoz-tree-swimlane-diagram/) | 1.0.0 | 树状泳道流程图：竖向泳道 + 角色标题 + 判断分支，交付前验遮挡 |

#### 编码代理协作与派单

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-session-hub`](skills/weicoz-session-hub/) | 1.0.0 | 总控会话协调多个代理会话，派任务、收汇报、验收 |
| [`weicoz-herdr-hub`](skills/weicoz-herdr-hub/) | 0.1.0 | 管理全部 Herdr 窗口：先问清项目目录再派单，按 pane 增量采集，20 分钟汇报 + 手机推送 |
| [`weicoz-session-recall`](skills/weicoz-session-recall/) | 1.0.0 | 跨 harness 检索历史会话，回答“我以前做过什么” |
| [`weicoz-remote-dispatch`](skills/weicoz-remote-dispatch/) | 1.0.1 | 把代理会话、测试与构建经 SSH 派到另一台机器执行 |
| [`weicoz-agent-implement`](skills/weicoz-agent-implement/) | 1.2.0 | 把单张票据委派给编码代理实现，派单方监控与验收 |
| [`weicoz-agent-implement-spec`](skills/weicoz-agent-implement-spec/) | 1.3.0 | 按依赖图编排整份规格，每票一个实现会话并统一合并验收 |
| [`weicoz-multi-worktree-dev-v3`](skills/weicoz-multi-worktree-dev-v3/) | 1.0.0 | 多 worktree 隔离开发与精确集成，按风险分级验证（当前版本） |
| [`weicoz-multi-worktree-dev-v2`](skills/weicoz-multi-worktree-dev-v2/) | 1.0.0 | 历史版本，仅在用户明确指定 v2 时使用 |
| [`weicoz-multi-worktree-dev`](skills/weicoz-multi-worktree-dev/) | 1.0.0 | 历史版本，仅在用户明确指定时使用 |
| [`weicoz-log-driven-ai-development`](skills/weicoz-log-driven-ai-development/) | 1.0.0 | 用日志把关键流程与结果变得可查，便于 AI 排查与验证 |
| [`weicoz-ai-dev-os`](skills/weicoz-ai-dev-os/) | 1.0.0 | 安装或同步项目级 AI 开发治理、宪法、SDD 与架构护栏 |
| [`weicoz-codex-context-window-override`](skills/weicoz-codex-context-window-override/) | 1.0.0 | 用 model_catalog_json 修改 Codex 上下文窗口，含备份与回滚 |
| [`weicoz-code-review`](skills/weicoz-code-review/) | 1.0.0 | 省 token 的本地代码审查：fork 给 Sonnet 执行、Haiku 批量打分过滤误报，主对话只收报告（Claude Code 需先运行 `scripts/install-agents.sh`） |

#### 浏览器与信息获取

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-ego-browser-reddit`](skills/weicoz-ego-browser-reddit/) | 1.0.0 | 用 ego-browser 查 Reddit、抓评论并落盘归档 |
| [`weicoz-ego-browser-x`](skills/weicoz-ego-browser-x/) | 1.0.0 | 用 ego-browser 查 x.com、抓线程并落盘归档 |
| [`weicoz-jev-ultrafast`](skills/weicoz-jev-ultrafast/) | 1.0.0 | 用本机 jev-ultrafast 驱动真实浏览器完成任务与链路体检 |
| [`weicoz-last30days-cn-bridge`](skills/weicoz-last30days-cn-bridge/) | 1.0.0 | last30days-cn 的本地修复封装，保留官方 skill 可升级 |

#### 本机环境与运维

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-mac-procmon`](skills/weicoz-mac-procmon/) | 1.0.0 | 查本机 CPU / 内存 / 磁盘异常，做进程归因与告警排查 |
| [`weicoz-mac-rescue`](skills/weicoz-mac-rescue/) | 1.0.0 | 卡顿与磁盘满的现场急救：swap 吃盘、僵尸启动项、进程泄漏、系统进程误判 |
| [`weicoz-harness-config-sync`](skills/weicoz-harness-config-sync/) | 1.0.0 | 把 Codex / DSH / Shell 配置同步到指定机器并装齐依赖 |
| [`weicoz-skill-tiers`](skills/weicoz-skill-tiers/) | 1.5.0 | skill 分层：L1 常驻、L2 短描述桩、L3 领域 Hub 收纳且可手动 /name 调用；只改软链与生成文件，不改原 skill，多 harness 通用，含查找、依赖检查与快照回滚 |
| [`weicoz-dsh-repos-update-check`](skills/weicoz-dsh-repos-update-check/) | 1.0.0 | 只读检查 DSH 本体与已装插件仓库的更新和实装差异 |
| [`weicoz-frp-port-dispatch`](skills/weicoz-frp-port-dispatch/) | 1.0.0 | 配置、迁移与排查 FRP 端口转发与开机自启 |
| [`weicoz-3a-game-manifest`](skills/weicoz-3a-game-manifest/) | 1.0.0 | 从 3a.lol 提取 Steam 入库清单并归档，附画质帧率预测 |

#### 视频与视觉

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-video-frame-density`](skills/weicoz-video-frame-density/) | 1.0.0 | 修复深色视频「画面太空」：覆盖率诊断、程序化氛围层、第二层信息重构，附帧号/字幕/音效/文档防漂移规则 |

#### 交付与表达规范

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-ste`](skills/weicoz-ste/) | 1.0.0 | 交付表达规范：结论先行、状态严谨、证据可查、决策选项化 |

#### 其他

| Skill | 版本 | 说明 |
| --- | --- | --- |
| [`weicoz-life-design`](skills/weicoz-life-design/) | 1.0.0 | 用设计思维探索人生方向，生成可试错的人生原型 |

---

## 版本号规范

每个 Skill 的 `SKILL.md` frontmatter 必须带 `version`，格式为语义化版本 `MAJOR.MINOR.PATCH`。

| 位 | 何时递增 | 例子 |
| --- | --- | --- |
| MAJOR | 破坏性变更：删参数、改配置键名、改输出契约 | 配置从环境变量改为 YAML 文件 |
| MINOR | 新增能力且向后兼容：加脚本、加配置项、加流程分支 | 新增「催办」流程 |
| PATCH | 修正与润色：改错别字、修命令示例、补边界说明 | 修正 `@` 语法示例 |

改动 Skill 时必须同步升版本，并在同一次提交里更新本 README 的版本表。校验脚本会检查 `version` 是否存在。

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

```text
skills/<skill-name>/
├── SKILL.md              # 必需：name / version / description + 操作指引
├── README.md             # 可选：维护者备注（口径、坑、实现细节）
├── config.example.yaml   # 可选：私有配置模板（真实配置放 ~/.config/）
├── references/           # 可选：参考资料、格式示例、发现流程
└── scripts/ 或 bin/      # 可选：实现脚本
```

- 每个 Skill 独立存放在 `skills/<skill-name>/`。
- `SKILL.md` frontmatter 的 `name` 必须与目录名完全一致。
- `SKILL.md` 写使用说明（Agent 读它执行）；`README.md` 写维护者备注（人读它改它）。
- 环境变量规范请参考 `.env.example`，本机私有变量推荐保存在本地环境变量配置（如 `~/.zshrc`）。
- 普通输出路径优先使用 `$WEICOZ_OUTPUT_ROOT`，未配置时回退使用当前工作目录。

---

## 校验与质量保证

提交前执行校验脚本：

```bash
./scripts/validate-skills.sh
```

脚本检查五项：

1. `skills/weicoz-*/` 下必须有 `SKILL.md`。
2. frontmatter 的 `name` 必须等于目录名。
3. frontmatter 必须有 `version` 字段，格式为 `X.Y.Z`。
4. 必须被本 README 的清单收录。
5. 不得出现疑似凭据（私钥、`sk-`、`ghp_`、`xox[baprs]-`、`AIza`、`AKIA`）与 `.env`/`.pem`/`.key` 文件。

第 6 项由 `scripts/sync-skills.sh` 承担：各 harness 目录里的 `weicoz-*` 必须指向本仓库，而不是历史备份库。`validate-skills.sh` 会顺带调用它；本机没有 harness 目录时（例如 CI 或新克隆）自动跳过。

**自动护栏**：安装 pre-commit hook，提交时自动跑校验。

```bash
./scripts/install-hooks.sh
```

安装后 `core.hooksPath` 指向 `.githooks/`。hook 提交前跑 `validate-skills.sh --no-links`（仓库内容不通过则阻止提交），再检查软链漂移——漂移属本机状态，只提示不阻止。用 `git commit --no-verify` 可临时跳过。

更多 Agent 协作与开发约束，请参阅 [AGENTS.md](./AGENTS.md)。
