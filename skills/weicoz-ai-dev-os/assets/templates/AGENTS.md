# AGENTS.md — {{PROJECT_NAME}} Agent 治理入口

---

## 1. Project Identity

**{{PROJECT_NAME}}** — {{ONE_LINE_PURPOSE}}。

领域词表（若存在）：[`CONTEXT.md`](CONTEXT.md)

### 栈与目录
| 路径 | 组件 | 栈 | 职责 |
|---|---|---|---|
| {{PATH}} | {{COMPONENT}} | {{STACK}} | {{RESPONSIBILITY}} |

### 事实与所有权（仅填写本仓真实存在的边界）

{{EVIDENCE_BASED_OWNERSHIP_BOUNDARIES}}

---

## 2. P0 架构宪法

唯一法律正文：[`docs/constitution.md`](docs/constitution.md)（由 `scripts/arch-guard.sh` 执法）。此处只放链接，禁止复制条款。

{{EVIDENCE_BASED_CONSTITUTION_LINKS}}

---

## 3. Quick Command Reference

命令写在子系统 `AGENTS.md`，或本仓只有一个包时写在这里。

{{COMMANDS_TABLE}}

---

## 4. SDD Workflow

非 trivial 功能或架构重构：

```text
1. Spec Discovery（查上下文和代码）
2. spec.md   → specs/{NNN}-{name}/
3. design.md → 宪法检查
4. tasks.md
5. 分支 feat/{NNN}-{name}
6. 按 wave 实现并跑定向测试
7. scripts/arch-guard.sh 与测试套件
8. code review
```

完整说明：[`docs/SDD-Guide.md`](docs/SDD-Guide.md)。流程不设固定审批点；关键业务、契约或授权变化才请求决策。已有授权不重复确认；用户明确要求逐阶段审批时除外。

---

## 5. Instruction File Mapping

- 根 `AGENTS.md`（本文件）：全局宪法指针、拓扑、SDD、P0
- 子目录 `AGENTS.md`：只扩展，不重复根规则

> **RULE**：跨组件规则上收到本文件。

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
