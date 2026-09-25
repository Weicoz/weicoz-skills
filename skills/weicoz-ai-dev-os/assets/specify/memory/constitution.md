# Spec Kit 开发宪法

> 管 AI 怎么干活，不管系统拓扑。系统法律在仓库 `docs/constitution.md`。
> 本文件服从用户显式指令和根 `AGENTS.md`。

## Core Principles

### I. Evidence Before Claims
先从源码、迁移、测试或运行证据确认现状，再设计改动。Provider 事实、运行时事实、模型输出、猜测必须分开。分支、版本、端口、commit 这类时点事实，报告前再核对。

### II. Minimal Scoped Changes
实现必须落在用户批准范围内，用最小可逆 diff。先复用现有工具和契约。未经批准禁止顺手重构、加依赖、投机加固。

### III. Contract and State Ownership
每类事实一个权威所有者。消费者必须用结构化契约，禁止从摘要或散文反推状态。

### IV. Tests Prove Behavior
修 bug 必须覆盖失败路径和禁止的副作用。完成声明前，定向测试和相关静态检查必须通过；线上验证与本地自动化证据分开报告。

### V. Preserve Existing Work
无关的脏工作区属于用户，禁止 revert、覆盖或折进本功能。被 gitignore 的文件要用文件系统直接检查。禁止破坏性命令；所有权冲突先报告。

## Development Workflow

1. 定义观察到的失败、权威事实、消费者、批准边界。
2. 写可测规格，标明禁止改动。
3. 能先写回归测试就先写。
4. 做最小的契约保持改动。
5. 跑定向测试与静态检查，检查 diff 有无无关改动。
6. 报告改动文件、验证证据、剩余风险，不夸大线上状态。

**Version**: 1.0.0
