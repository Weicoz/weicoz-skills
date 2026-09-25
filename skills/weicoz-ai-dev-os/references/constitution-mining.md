# 从目标仓挖宪法

不要从 Clawith 或其它仓搬运条款。只保留本仓证据支持、会改变工程决策的不变量，不凑条数。

## 证据优先级

1. ADR / design 里的 **Rejected** 和 **不得**
2. 测试里断言的禁止行为（静默降级、双扣积分、跨租户读）
3. 代码里的唯一入口（单一账本、单一 provider 包装、单一 schema 文件）
4. 事故记录、`bugs.md`、注释里的 invariant
5. 现有 `AGENTS.md` 的硬规则（需再用代码核对，过期的丢掉）

## 六类槽位（对应 Clawith C1–C6 的**形状**，不是内容）

| 槽 | 要找的不变量 | 典型证据 | 能否进 arch-guard |
|---|---|---|---|
| C1 权威边界 | 哪张表/哪个服务拥有执行生命周期；禁止第二套 | 任务账本、worker、checkpoint | 难；API 不得 import 执行内核时可以 grep |
| C2 隔离 | 租户、用户、公私域 | `userId`/`tenant` where、域分离 ADR | 部分 |
| C3 幂等与失败可见 | 副作用只发生一次；禁止静默降级 | webhook、cron、credit settle、409 busy | 部分 |
| C4 包装层 | 外呼、支付、LLM、HTTP 必须走统一模块 | `src/payment/provider`、request wrapper | 易 |
| C5 数据变更 | 迁移入口、禁物理 cascade、软删 | schema 文件、drizzle/alembic 规则 | 易 |
| C6 模块边界 | 目录职责、文件尺寸、先搜再写 | 现有分层 | 行数 warning |

没有证据的槽位 **留空**，不要用行业最佳实践填。

## 条款写法

```markdown
## C1. <短名>

<一句话法律。>

### Invariants
- ...
- Product / UI / 投影 **不得** 成为第二套执行状态机（按本仓名词改写）。

证据：`docs/adr/00xx-...md`，`src/...`
```

Spec Kit 的 `.specify/memory/constitution.md` 写 **开发行为**（先证据、最小 diff、测试证明、不碰脏工作区），不要重复 `docs/constitution.md` 的系统法律。
