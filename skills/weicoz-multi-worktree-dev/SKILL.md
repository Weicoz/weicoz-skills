---
name: weicoz-multi-worktree-dev
version: 1.0.0
description: 仅用于用户明确指定 weicoz-multi-worktree-dev 历史版本的多 worktree 流程或兼容维护。通用 worktree 隔离、并行开发和集成任务使用 weicoz-multi-worktree-dev-v3，不自动套用本历史版的固定数据库、全量测试和人工 main 流程。
---

# 多 Worktree 并行开发测试流程

适用场景：一个项目用多个 AI 会话 + git worktree 同时开发多个需求，要求互不干扰、各自可测、合并到 develop 后功能正常。

分支模型：feature 分支 → **develop（集成分支，所有回归在这里跑）** → main（生产发布分支，**受保护**：仅手工发起 PR + 人工审核通过后从 develop 合入）。

底稿：`$WEICOZ_KNOWLEDGE_ROOT/notes/多worktree并行开发测试流程-实践指南.md`（详情以该文档为准）。

## 一、核心原理：三层隔离

git worktree 只隔离**代码**，不隔离运行时。并行开发要跑通，必须补齐三层：

| 层 | 隔离手段 | 不隔离的后果 |
|---|---|---|
| 代码 | `git worktree add`，每需求一目录一分支 | agent 互相覆盖文件 |
| 数据 | 每 worktree 一个**独立数据库**（真分库，不是同库不同表） | 迁移/测试数据互相污染，表结构对不上 |
| 运行时 | 每 worktree 独立 `PORT` + 独立 `.env.local`（不进 git） | 端口冲突、读到别人的配置 |

测试成立的根基：**每个 worktree 内完成全部测试，merge 到 develop 后再跑全量回归**。develop 永远保持"可跑、可测、全绿"状态。

## 二、环境供给：一条命令出一个可测环境

### 基准库（关键，针对配置存在数据库里的系统）

系统把 AI API key、base URL、支付参数、平台开关存在**数据库设置表**里时，不能用"空库 + seed"，要用**基准库 dump**：

```bash
# 一次性：在 develop 开发库里手工配好所有配置（AI key、base URL、开关、基础商品/分类/角色）
# 然后导出为基准文件，入库版本化
mysqldump -u root myapp_dev > scripts/baseline.sql
```

- 敏感 key 用占位符：`__AI_API_KEY__`，恢复时从 `.env.local` 注入。
- 配置变更时重新 dump 更新 `baseline.sql`。
- 原则：**手工配置可以存在，但必须沉淀为可重建、入库版本化的基准文件**——配一次，永久复用。

### 供给脚本 `scripts/new-worktree.sh`

```bash
#!/bin/bash
# 用法: ./scripts/new-worktree.sh <需求名> <端口>
set -euo pipefail
NAME=$1          # 如 feat-ai-task
PORT=$2          # 如 3001
DIR="../$(basename "$PWD")-$NAME"

# feature 分支一律从 develop 拉出
git worktree add "$DIR" -b "$NAME" develop

# 独立数据库：克隆基准库（配置 + 基础数据全带过来）
mysql -u root -e "CREATE DATABASE \`myapp_$NAME\`"
sed "s/__AI_API_KEY__/${AI_API_KEY}/g" scripts/baseline.sql | mysql -u root "myapp_$NAME"

# 独立 env（不进 git）
cat > "$DIR/.env.local" <<EOF
PORT=$PORT
DATABASE_URL=mysql://root@127.0.0.1:3306/myapp_$NAME
AI_API_KEY=${AI_API_KEY}
AI_BASE_URL=${AI_BASE_URL:-https://你的测试网关/v1}
PLAYWRIGHT_BASE_URL=http://localhost:$PORT
EOF

cd "$DIR" && php artisan migrate   # 只跑本分支新增的迁移
echo "✅ $DIR | 分支 $NAME | 端口 $PORT | 库 myapp_$NAME"
```

可选增强：

- 结尾加 `tmux new-window -n "$NAME" -c "$DIR"`，自动开 tmux 窗口（契合现有 tmux 习惯）。
- 用 Neon/PlanetScale 的项目可改成数据库 branch（copy-on-write，秒级带数据副本），并用 git `post-checkout` hook 全自动完成上述步骤。

### 任务提示词里写死边界

每个 AI 会话的开场提示必须包含：

```
你在 <分支名> worktree 工作，dev server 端口 <PORT>，数据库 myapp_<分支名>。
只允许改动 <模块范围>，不许动 <共享文件清单>。
完成后：跑测试 → playwright-cli 走一遍主流程截图自查 → 增量 commit。
```

## 三、每个需求（worktree 内）的开发测试流程

```
1. ./scripts/new-worktree.sh feat-x 3001        # 环境一条命令就绪（从 develop 拉分支）
2. 开发 + 组件/单元测试（边写边跑）
3. 起 dev server（端口 3001，连自己的库）
4. E2E 冒烟：Playwright 打 http://localhost:3001
5. agent 用 playwright-cli --headed 走主流程、截图自查
6. git diff develop...feat-x 自审：无越界改动、无半成品
7. 增量 commit
```

### 前端页面三层测试

| 层 | 工具 | 特点 | 何时跑 |
|---|---|---|---|
| 组件级 | Vitest/Jest + Testing Library | 不起服务不连库，毫秒级；后端接口用 MSW mock | 开发中随时 |
| 页面 E2E | Playwright（`baseURL` 走 env） | 打本 worktree 端口 + 本 worktree 库；`webServer` 自动起服务 | 合并前必过 |
| 视觉回归 | Playwright `toHaveScreenshot()` | 基线截图在 develop 生成并入库，改坏别人的页面立刻 diff 出来 | 合并前必过 |

E2E 不求全覆盖，只保关键业务链路：登录 → 核心业务操作 → 后台能查到结果。

### 测试数据策略

- **基准库**提供配置和基础数据。
- **流程前置数据造中间态**：要测第 5 步，seed 直接写出第 4 步完成后的状态（如 `status=success` 的 AI 任务、已完成订单），不从第 1 步走起。
- E2E 用例的前置态用 API/直接写库创建，UI 只点被测的那一步；全流程 UI 冒烟保留 1-2 条即可。
- 用例自建数据加唯一前缀（`e2e-<时间戳>-`），避免用例间污染。

### AI Agent 异步任务的测试

- **联调**：`.env.local` 配测试网关 key/base URL，各 worktree 共用网关、库独立。
- **自动化测试**：本地起假 OpenAI 兼容端点返回固定结果，E2E 不等真 AI、不烧 token、结果可断言。
- 真 AI 联调留给人工验收环节。

## 四、合并流程（develop worktree）

```
对每个待合并分支：
1. git diff develop...feat-x 审查（越界改动？半成品？与其他分支冲突？）
2. 按依赖顺序 merge 到 develop（被依赖的先合）
3. 每合一个分支：
   - 跑增量迁移
   - npm run test:all   # = 组件单测 + E2E + 视觉回归，与 CI 同一条命令
   - 绿了再合下一个     # 不要全合完再测，出问题定位不到来源
4. 全部合完、develop 全量回归通过 → 交付用户 UAT
5. 清理：git worktree remove + 删分支 + DROP 对应数据库
```

两道保险：**worktree 内全量测一遍** + **每合并一个分支在 develop 回归一遍**。用户拿到的永远是通过完整回归的 develop，只做业务确认，不替你抓 bug。

### main 是生产发布分支，受保护

- 任何人/任何 AI 会话都**不允许直接 push 或 merge 到 main**。
- UAT 通过后，由人手工发起 `develop → main` 的合并申请（PR），**人工审核通过后才能合入**。
- AI agent 的权限边界到 develop 为止：合并 feature → develop、跑回归、清理 worktree 都可以做；涉及 main 的任何操作必须停下来等人。
- 因为 develop 上已全绿，审核主要是业务确认和 diff 过目，不需要再跑测试。

## 五、防坑清单

- ❌ 两个会话在同一目录跑 → 互相覆盖文件。
- ❌ `.env` 提交进仓库 → 所有 worktree 读同一份配置，隔离失效。配置覆盖一律走 gitignore 的 `.env.local`。
- ❌ 只隔离代码不隔离端口/数据库 → 测试偶发失败，其实在"调试干扰"而不是调试代码。
- ❌ 空库当测试环境 → 系统配置（AI key、base URL）都在库里，必须走基准库 dump 方案。
- ❌ 测试依赖手工在库里改的数据 → 别的 worktree 和 develop 回归都没有，必炸。手工配置必须沉淀进 `baseline.sql`。
- ❌ 任务边界不清 → agent 顺手改共享文件，合并冲突爆炸。
- ❌ 合并不看 diff、全合完再测 → 问题无法定位到分支。
- ❌ feature 从 main 拉分支 → 会和 develop 上未发布的需求错位，一律从 develop 拉。
- ⚠️ 迁移冲突：要么指定 migration owner，要么约定每个需求只动自己的表。

## 六、一页速查

| 动作 | 命令/位置 |
|---|---|
| 开新需求 | `./scripts/new-worktree.sh feat-x 3001`（从 develop 拉分支） |
| 更新基准配置 | 改 develop 开发库 → `mysqldump ... > scripts/baseline.sql` → commit |
| 本分支测试 | `npm run test:all`（worktree 内） |
| 界面自查 | `playwright-cli open --headed http://localhost:3001` |
| 登录态复用 | `playwright-cli state-save/state-load "$WEICOZ_BROWSER_STATE_ROOT/<site>.json"` |
| 合并前审查 | `git diff develop...feat-x` |
| 合并后回归 | develop 上 `npm run test:all`，每合一个跑一遍 |
| 发版 | UAT 通过后**手工发起** develop → main 的 PR，**人工审核通过**才合入（禁止直接 push/merge 到 main） |
| 清理 | `git worktree remove` + 删分支 + `DROP DATABASE` |
