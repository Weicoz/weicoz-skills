# SDD Guide — Spec-Driven Development

> 本仓功能开发与文档归档的权威流程。
> 根 `AGENTS.md §4` 是速查；本文是全文。
> 架构法律 → [`constitution.md`](constitution.md)。

---

## 1. 流程分级

| 轨道 | 何时 | 必做 |
|---|---|---|
| **Hotfix / Trivial** | 局部修复、文案、低风险且无契约变更 | 修复 → 相关检查 → Review。不强制写 spec/design；分支沿用项目约定。 |
| **Small Feature** | 单模块、无跨功能契约、低不确定 | 轻量 `spec.md`（验收标准）→ 实现 → 测试 → review。 |
| **Full SDD Track** | 重大新能力、跨模块契约变化或需要持久设计记录 | 按 §2 记录规格、设计与验证；暂停按 §3，不按文件数决定。 |

---

## 2. Full SDD Pipeline

```text
1. Spec Discovery（读代码、确定范围）
2. spec.md    （What 与验收）
3. design.md  （How、已知坑、宪法检查）
4. tasks.md   （任务拆分与执行日志）
5. 分支 feat/{NNN}-{name}
6. 按 wave 实现并跑测试
7. scripts/arch-guard.sh 与测试套件
8. Code Review；合并仅在已授权工作流内执行
```

AI 执行产物放 `specs/{NNN}-{name}/`（模板在 `.specify/templates/`）。
产品归档在 `docs/features/v{X.Y.Z}/{NNN}-{name}/` 链接执行产物，不维护两份正文。

---

## 3. 澄清、授权与完成

- 目标和范围明确时连续执行，不因 Discovery、spec 或 design 完成而请求继续。用户明确要求阶段审批时遵循其要求。
- 技术选择先查现有实现，低风险可逆调整自行决定并更新记录。业务含义、契约、授权或不可逆后果发生实质变化时，合并关键问题，只暂停受影响工作。
- 实现、相关测试和必要检查通过后交付，不无限增加文档、审查轮次或测试。提交、推送、合并、部署均按实际授权，不由流水线名称自动授权。
- 必要检查无法完成则交付部分结果和阻塞证据，列出未验证项，不把实现完成写成发布完成。

---

## 4. 文档职责

| 文档 | 用途 | 更新规则 |
|---|---|---|
| `spec.md` | What 与验收 | 维护一个正文，归档处互链 |
| `design.md` | 为什么是这个 How + 今日快照 + 已知坑 | 覆盖写现状；保留否决原因和坑 |
| `tasks.md` | 做了什么、什么顺序 | 执行中追加 |

原则：

1. 法律只活在 `constitution.md`，子系统架构只活在 `docs/architecture/`，功能交付只活在 `docs/features/` 与 `specs/`。
2. `docs/architecture/` 覆盖写，永远是今天。
3. `design.md` 只记录影响决策的取舍和已知陷阱，不为填模板虚构替代方案。
