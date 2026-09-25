---
name: weicoz-ai-dev-os
description: 安装或同步项目级 AI 开发治理、宪法、SDD 与架构护栏；用于明确要求安装开发规范、对齐项目治理或执行 /weicoz-ai-dev-os。不用于用户级 AGENTS/Skills 审计、普通规则文字修订或单功能实现；这些任务不自动引入完整治理框架。
---

# weicoz-ai-dev-os

把目标仓库装成 Clawith 同款 **AI 开发操作系统**。skill 是安装器，不是法律正文。日常 coding agent 读的是目标仓里的 `AGENTS.md` / `docs/constitution.md`，不是本文件。

**法律禁止抄 Clawith 的 C1–C6。** 文件结构和流程抄 Clawith；宪法条款必须从目标仓源码、测试、ADR、事故里挖出来。

## 何时用 / 何时不用

用：新仓要装；老仓规范散；**已经初始化过的仓要对齐/同步**（代码、ADR、目录变了，OS 文件可能过期）。

不用：正在按本 OS 开发某个功能（那时读目标仓 `AGENTS.md`）；只写一个功能的 spec。对齐规范时必须用本 skill。

## 安装前硬规则

1. 先读目标仓，再写文件。已有 `AGENTS.md` / ADR / OpenSpec 当证据，不当垃圾。
2. 宪法每条必须能指到文件、ADR 或事故。写不出证据的条款不上宪法。
3. 首次安装与二次对齐使用相同授权标准：用户明确要求安装、同步或优化时，先盘点，再直接执行范围内有证据、无冲突的改动；只要求审查或方案时只报告。
4. 仅当改动涉及未授权的治理迁移、有效规则的实质冲突或不可逆影响时，列明差异请求决策；不按文件、ID 或阶段重复确认。详情 → `references/align-resync.md`。
5. 不改业务代码。仅产本次目标需要的规范、导航、护栏和模板；不为凑文件地图生成空目录或无用文档。
6. 不碰用户脏工作区里的未提交业务改动。
7. 文档默认中文。
8. 保留仍在使用的规格系统。只有明确授权迁移时才将旧入口归档并指向新入口；不得借同步 AGENTS 更换开发框架。

详细文件清单 → `references/file-map.md`  
挖宪法方法 → `references/constitution-mining.md`  
新仓 / 老仓 / 二次对齐 → `references/install-tracks.md`  
已初始化对齐协议 → `references/align-resync.md`

## 0. 先判断轨道

读目标仓根 `AGENTS.md`、`docs/constitution.md`、`docs/SDD-Guide.md`。

- **未初始化** → 下面「首次安装」
- **已初始化**（根 `AGENTS.md` + `docs/constitution.md`，或用户明确说对齐/同步）→ **跳到「二次对齐」**，不要走落盘

## 首次安装

### 1. 盘点

读：`README*`、现有 `AGENTS.md`/`CLAUDE.md`/`CONTEXT.md`、`package.json`/`pyproject.toml`、`docs/`、`openspec/`、ADR、CI、目录结构、测试脚本。

输出内部盘点：栈、模块边界、已有规范、能 grep 的铁律、不能 grep 的判断题、历史规格系统（OpenSpec 等）。

### 2. 挖宪法（按证据，不凑条数）

按 `references/constitution-mining.md` 产出 C1–Cn。优先找：

- 唯一权威账本 / 禁止第二套状态机
- 租户或权限隔离
- 副作用幂等、禁止静默降级
- 外部调用必须走包装层
- 数据库迁移与删除策略
- 模块边界与文件尺寸

每条写成否定句：「X 不得变成 Y」。

### 3. 落盘（Clawith 同构）

从 `assets/templates/` 和 `assets/specify/` 生成，填入 **本仓** 身份和宪法，不填 Clawith 领域词。

候选文件地图（明确要求 Clawith 同构时采用完整集，否则只选必要文件）：

| 文件 | 角色 |
|---|---|
| `AGENTS.md` | 总入口：身份、事实分离、宪法指针、命令指针、SDD、分层映射 |
| `CLAUDE.md` | 只有一行 `AGENTS.md` |
| `docs/constitution.md` | 唯一法律正文；别处只链接 |
| `docs/SDD-Guide.md` | hotfix / 小功能 / 全量 SDD + ★ 人确认 |
| `docs/README.md` | 文档导航 |
| `docs/architecture/01-03` | 今日架构快照，覆盖写 |
| `docs/features/` | 产品向 SDD 归档（可先放 `.gitkeep`） |
| `specs/` + `.specify/` | Spec Kit 产物与模板 |
| `scripts/arch-guard.sh` | 只执法能 grep 的条款 |
| 目录级 `AGENTS.md` | 真实子系统才写，禁止空文件凑数 |

根 `AGENTS.md` **禁止复制** 宪法全文。子 `AGENTS.md` **禁止复制** 根规则。

### 4. 接线

- CI 已有则加 `scripts/arch-guard.sh`；没有则只在 `AGENTS.md` 写本地命令。
- 若明确授权替换 OpenSpec / superpowers，才在 `docs/README.md` 标明新旧入口关系；否则沿用已有流程。
- 若已有 `CONTEXT.md` 领域词表：根 `AGENTS.md` 链接它，不把术语抄进宪法。

### 5. 验收

- 根 `AGENTS.md` 能让新 session 的模型找到宪法、命令、SDD。
- `CLAUDE.md` 不维护第二套规则。
- `docs/constitution.md` 每条有证据来源。
- `scripts/arch-guard.sh` 在当前仓可运行；P0 违规才 `exit 1`。
- 没有把 Clawith 的 Runtime / LangGraph / axios 条款写进无关项目。

## 二次对齐（已初始化仓）

代码、ADR、目录变了之后再跑本 skill，走这条。完整规则 → `references/align-resync.md`。

1. 按 file-map + 现行代码/ADR 对比，不要对照 Clawith 法律正文。
2. 分类：建议不动 / 新增 / 更新（无冲突） / 冲突。
3. 整理现状、拟改动、冲突及证据；简单改动不强制四块报告。
4. 已要求同步或优化：执行无冲突的范围内更新；只要求报告：交付分析后结束。实质冲突只暂停受影响部分。
5. 用户限定 ID 时只执行点名项；否则按已授权目标执行。不改业务代码，不为每个新文件夹自动建 `AGENTS.md`。
6. 写完列出实际改动的路径；有 `arch-guard` 就跑。

根 `AGENTS.md` 的 `<!-- MANUAL ADDITIONS` 段、仍有证据的宪法条款、`CONTEXT.md`、ADR、存量 OpenSpec 目录：默认建议不动。

## SDD（本 skill 自带，结构同 Clawith）

全量流程：

```text
1. Spec Discovery（从上下文和代码明确范围）
2. spec.md   （What + 验收）
3. design.md （How + 已知坑 + 宪法检查）
4. tasks.md  （任务拆分，精确到文件）
5. 分支 feat/{NNN}-{name} 或 specs/{NNN}-{name}
6. 按 wave 实现；测试先行（story 要求时）
7. scripts/arch-guard.sh + 定向测试
8. code review
```

产物位置：

- 产品归档：`docs/features/v{X.Y.Z}/{NNN}-{name}/spec.md|design.md|tasks.md`
- AI 执行：`specs/{NNN}-{name}/` 用 `.specify/templates/`（spec/plan/research/data-model/contracts/tasks/checklists/quickstart）

模板：`.specify/templates/`。生成文档用中文填，章节结构不要改。

不设固定暂停点。低风险可逆的技术调整自行处理并更新依据；业务结果、契约或授权发生实质变化时才请求决策。用户明确指定阶段审批时遵循其要求。必做项和必要验证完成即交付；提交、合并、部署不从本流程自动获得授权。

## arch-guard

只把能 `grep` 的宪法条款写成检查。判断题留在 `design.md` 的 Constitution Check。

P0 → `exit 1`。其余 warning。允许行内 `# arch-guard: allow` 豁免并写理由。

通用骨架见 `assets/templates/scripts/arch-guard.sh`。安装时改成 **本仓路径和本仓模式**。

## 反模式

- 把 Clawith C1「四类事实 / LangGraph」贴到 Next.js / PHP 仓
- 同时开 OpenSpec 新 change 和 SDD 新 feature
- 宪法 15 条，一条都扫不了
- `CLAUDE.md` 再写一遍命令
- 为不存在的 DAO/axios 包装发明护栏
- 借安装规范重构业务代码
- 未核对证据就覆盖有效规则，或已有明确更新授权仍要求再次确认全部文件
- 把二次对齐当成首次安装整仓重写
