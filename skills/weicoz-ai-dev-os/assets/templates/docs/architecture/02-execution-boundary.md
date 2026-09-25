# 02 - 执行边界

> Status: 今日实现基线。覆盖写。

## 入口

{{ENTRYPOINTS}}

**Rules**：
- 入口只创建/领取账本上的任务，不直接推进执行内核状态。
- 禁止在 UI 或产品投影里实现私有执行控制循环。

## Worker / Runtime

{{WORKER}}
