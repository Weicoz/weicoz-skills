# 目标仓文件地图（对齐 Clawith）

候选路径如下。仅在用户明确要求完整 Clawith 同构时采用完整集；否则保留既有结构，只创建本次目标需要的文件。方括号项还要求对应子系统真实存在。

```text
AGENTS.md                          # 总入口；不复制宪法全文
CLAUDE.md                          # 内容只有：AGENTS.md
docs/
  README.md                        # 导航
  constitution.md                  # 唯一法律
  SDD-Guide.md                     # 流程分级、授权和完成条件
  architecture/
    01-architecture-overview.md    # 今日拓扑
    02-backend-runtime-boundary.md # 或按本仓改名：执行/数据边界
    03-multi-tenant-data-model.md  # 或按本仓改名：隔离/数据模型
  features/                        # 产品向 SDD 归档
    .gitkeep
  adr/                             # 已有 ADR 则保留，不搬迁
specs/                             # Spec Kit 功能目录
  .gitkeep
.specify/
  init-options.json
  memory/constitution.md           # Spec Kit 行为宪法（开发原则，从本仓挖）
  scripts/bash/                    # 从 assets/specify 拷贝
  templates/                       # spec/plan/tasks/checklist/...
scripts/
  arch-guard.sh
[backend/AGENTS.md]
[frontend/AGENTS.md]
[src/db/AGENTS.md]
[src/actions/AGENTS.md]
[src/lib/AGENTS.md]
```

## 覆盖规则

| 已有文件 | 做法 |
|---|---|
| `AGENTS.md` | 默认保留结构；明确要求同构时才调整，始终保留有效命令、栈和路径 |
| `CLAUDE.md` | 改成单行指针。旧内容并入 `AGENTS.md` 后删除重复 |
| `CONTEXT.md` | 保留，根 `AGENTS.md` 链接 |
| `openspec/` | 默认沿用；明确迁移时才改入口，不删除 |
| `docs/superpowers/` | 同上 |
| `docs/adr/` | 保留；宪法条款引用 ADR 编号 |

已初始化后再跑：先按 `align-resync.md` 对比证据，再根据已有授权执行无冲突更新；不因文件已存在要求重复批准。

## 根 AGENTS.md 必须有的五节

1. Project Identity（栈、目录、事实分离）
2. P0 Constitution（只放链接）
3. Quick Command Reference（或指向子 AGENTS.md）
4. SDD Workflow
5. Instruction File Mapping

末尾可追加 Active Technologies / Recent Changes（Spec Kit `update-agent-context.sh` 会写这里）。用 `<!-- MANUAL ADDITIONS START -->` 保护人工段。
