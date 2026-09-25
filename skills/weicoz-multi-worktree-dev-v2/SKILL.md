---
name: weicoz-multi-worktree-dev-v2
description: 仅用于用户明确指定 weicoz-multi-worktree-dev-v2 历史版本的多 worktree 流程或兼容维护。通用 worktree 隔离、并行开发和集成任务使用 weicoz-multi-worktree-dev-v3，不自动套用本历史版的固定数据库、全量测试和人工 main 流程。
---

# 多 Worktree 并行开发测试流程

> 场景：一个项目开多个 AI 会话，每个会话在独立 git worktree 开发一个需求，要求互不干扰、各自可测、合并到 develop 后功能正常。
> 分支模型：feature → **develop（集成分支，所有回归在这里跑）** → main（生产发布，**受保护**）。
> 底稿：`$WEICOZ_KNOWLEDGE_ROOT/notes/多worktree并行开发测试流程-实践指南.md`（细则以该文档为准；调研过程见 `notes/多worktree并行开发-测试流程调研-2026-07-21.md`）。

---

## 0. 铁律（先读这个）

1. **feature 一律从 develop 拉分支**，禁止从 main 拉。
2. **develop 永远保持"可跑、可测、全绿"**——它是交付给用户的唯一状态。
3. **AI agent 的权限边界到 develop 为止**：合 feature、跑回归、清理 worktree 都可以；**任何涉及 main 的操作必须停下来等人**。
4. 测试成立的根基 = **每个 worktree 内完成全部测试** + **每合并一个分支在 develop 全量回归一遍**。

---

## 0.5 开工前必做：引导用户提供信息

🔴 CHECKPOINT：触发本 skill 后**不要直接开干**——信息未收齐前，禁止执行任何 worktree 创建、建库、迁移操作。大多数用户说不清该提供什么，agent 必须主动按下面的清单逐项问（用提问工具分组问，缺什么问什么），收齐后才允许动手。

### A. 首次接入（项目还没跑过这套流程）

| # | 必须向用户收集 | 用途 | 示例答案 |
|---|---|---|---|
| 1 | 项目栈：框架 + 数据库 + 迁移工具 | 填供给脚本的 6 个函数 | Next.js + PostgreSQL + Prisma；Laravel + MySQL |
| 2 | 集成分支名 | feature 从哪拉、回归在哪跑 | develop / dev |
| 3 | 配置是否存在数据库里 | 决定要不要基准库 dump | 是 → 引导做 `baseline.sql`；否 → 用 seed |
| 4 | dev server 启动命令 + 可用端口段 | 每 worktree 独立端口 | `pnpm dev`，3001–3010 |
| 5 | 本地数据库连接方式 | 建库/恢复命令 | `postgres@127.0.0.1:5432`，无密码 |
| 6 | 测试现状：有没有单测 / E2E / CI 命令 | 拼 `test:all` | 有 vitest 无 playwright → 引导补 |

收齐后，带用户**一次性落地三件套**，没落地前不进入并行开发：

1. `scripts/new-worktree.sh`——按用户栈填好 6 个函数（§2.2 有各栈现成示例，用户说不清就按"框架+数据库"替它选）
2. `scripts/baseline.sql`——仅当配置存在数据库里（§2.1）
3. `npm run test:all`（或等价命令）——组件测试 + E2E 合并为一条，与 CI 同命令

🔴 CHECKPOINT：三件套落地后，先跑一次 `./scripts/new-worktree.sh smoke-setup <空闲端口>` 验证全链路（建 worktree → 建库 → 恢复 → 迁移全通），把输出给用户确认环境可跑，**用户确认后**才进入并行开发；验证完按 §4 第 5 步的同一确认流程清理该 smoke worktree（不豁免）。

### B. 日常使用（三件套已存在）

每开一个新需求，只问 4 件事：

1. **需求名**（即分支名，如 `feat-ai-task`）
2. **端口**（先查 `.worktree-registry` 报一个空闲的建议值，让用户确认）
3. **允许改动的模块范围**（按目录划，如 `app/(shop)/**`、`src/modules/order/**`）
4. **共享文件清单 + 依赖关系**：默认共享文件含 schema/迁移目录、`.env*`、根配置、公共布局——任何需求要动必须先声明；有依赖的需求排好合并顺序

用户答不上来时给默认建议，不要卡住：模块范围按路由/目录猜一版请用户确认；端口按 registry 最大值 +1。

---

## 1. 核心原理：三层隔离

`git worktree` 只隔离**代码**，不隔离运行时。并行开发要跑通，必须补齐三层：

| 层 | 隔离手段 | 不隔离的后果 |
|---|---|---|
| 代码 | `git worktree add`，每需求一目录一分支 | agent 互相覆盖文件 |
| 数据 | 每 worktree 一个**独立数据库**（真分库，不是同库不同表） | 迁移/测试数据互相污染，表结构对不上 |
| 运行时 | 每 worktree 独立 `PORT` + 独立 `.env.local`（gitignore，不进仓库） | 端口冲突、读到别人的配置 |

共享中间件同理：Redis 用独立 db index、队列名加 `$NAME` 前缀、对象存储 bucket/目录加前缀——一切"进程外共享状态"都要按 worktree 隔离，否则等价于没隔离。

---

## 2. 环境供给：一条命令出一个可测环境

### 2.1 基准库（配置存在数据库里的系统必做）

若系统把 API key、base URL、支付参数、平台开关存在**数据库设置表**，不能用"空库 + seed"，必须用**基准库 dump**：

```bash
# 一次性：在 develop 开发库手工配好全部配置（key、开关、基础商品/分类/角色），然后导出入库版本化
# 导出命令就是 new-worktree.sh 里配好的 db_dump()，随栈而定：
db_dump > scripts/baseline.sql
```

- 敏感 key 用占位符 `__AI_API_KEY__`，恢复时从环境变量注入。
- 配置变更 → 改 develop 开发库 → 重新 dump → commit `baseline.sql`。
- 原则：**手工配置可以存在，但必须沉淀为可重建、入库版本化的基准文件**——配一次，永久复用。

### 2.2 供给脚本 `scripts/new-worktree.sh`

脚本与编程语言、数据库、框架**全部无关**：栈相关的命令抽成开头 6 个函数，首次接入时按用户栈填一次（§0.5 收集的第 1/5 项），之后永不改动。

```bash
#!/bin/bash
# 用法: ./scripts/new-worktree.sh <需求名> <端口>
# 依赖 bash + 常见 Unix 工具（Windows 请走 WSL）
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"   # 无论从哪里调用都回到仓库根
: "${AI_API_KEY:?请先 export AI_API_KEY（基准库占位符注入要用）}"

# ===== 按项目栈配置这 6 个函数（配一次，全团队复用）=====
# 下面给的是 PostgreSQL + Prisma 示例；其他栈对照表见脚本下方。
# 注意：db_migrate 里要带上依赖安装（新 worktree 没有 node_modules/vendor），
# 无依赖步骤的栈（如 SQLite 单文件）直接写迁移命令即可。
db_dump()    { pg_dump -U postgres --no-owner --no-privileges myapp_dev; }   # 导出基准库到 stdout
db_create()  { createdb -U postgres "$1"; }                                  # 建空库
db_restore() { psql -U postgres -v ON_ERROR_STOP=1 "$1"; }                   # 从 stdin 恢复基准 SQL（遇错即停，拒绝半截恢复）
db_migrate() { pnpm install && npx prisma migrate deploy; }                  # 装依赖 + 跑增量迁移
db_drop()    { dropdb -U postgres "$1"; }                                    # 清理时删库
db_url()     { echo "postgresql://postgres@127.0.0.1:5432/$1"; }             # DATABASE_URL 模板

# ===== 以下部分与栈无关，不要改 =====
NAME=$1          # 如 feat-ai-task
PORT=$2          # 如 3001
DIR="../$(basename "$PWD")-$NAME"
DB="myapp_${NAME//-/_}"   # 库名统一转下划线（psql 不允许连字符；底稿 MySQL 脚本保留连字符，纯 MySQL 项目可去掉这处转换）

# 幂等守卫：重名直接失败并提示，不留半成品
if git show-ref --verify --quiet "refs/heads/$NAME"; then echo "❌ 分支 $NAME 已存在"; exit 1; fi
if [ -e "$DIR" ]; then echo "❌ 目录 $DIR 已存在"; exit 1; fi
if [ -f .worktree-registry ] && awk -F'\t' -v p="$PORT" '$2==p{f=1} END{exit f?0:1}' .worktree-registry; then
  echo "❌ 端口 $PORT 已被其他 worktree 登记占用（见 .worktree-registry）"; exit 1
fi

# feature 分支一律从 develop 拉出
git worktree add "$DIR" -b "$NAME" develop

# 独立数据库：克隆基准库（配置 + 基础数据全带过来）
db_create "$DB"
# sed 注入安全：key 里的 & | \ 先转义，分隔符用 | 不用 /（key 含 / 也不会炸）
ESCAPED_KEY=$(printf '%s' "$AI_API_KEY" | sed 's/[&|\]/\\&/g')
sed "s|__AI_API_KEY__|$ESCAPED_KEY|g" scripts/baseline.sql | db_restore "$DB"

# 独立 env 文件（不进 git；文件名随栈：Next.js 读 .env.local，Laravel 读 .env——按栈改这里和 §1 的说明）
cat > "$DIR/.env.local" <<EOF
PORT=$PORT
DATABASE_URL=$(db_url "$DB")
AI_API_KEY=${AI_API_KEY}
AI_BASE_URL=${AI_BASE_URL:-https://你的测试网关/v1}
PLAYWRIGHT_BASE_URL=http://localhost:$PORT
EOF

(cd "$DIR" && db_migrate)   # 子 shell：只跑本分支新增迁移，不改变本脚本工作目录

# 登记端口/库占用（gitignore）。mkdir 当锁用（macOS/Linux 通用，不依赖 flock）；
# 检查+追加在同一临界区，trap 防锁残留
while ! mkdir .worktree-registry.lock 2>/dev/null; do sleep 0.1; done
trap 'rmdir .worktree-registry.lock 2>/dev/null || true' EXIT
if [ -f .worktree-registry ] && awk -F'\t' -v p="$PORT" '$2==p{f=1} END{exit f?0:1}' .worktree-registry; then
  echo "❌ 端口 $PORT 刚被并发 worktree 抢注"; exit 1
fi
echo -e "$NAME\t$PORT\t$DB\t$DIR" >> .worktree-registry
rmdir .worktree-registry.lock
trap - EXIT

echo "✅ $DIR | 分支 $NAME | 端口 $PORT | 库 $DB"
```

6 个函数的常见栈对照（用户说不清时，agent 按此表替它填）：

| 栈 | db_dump | db_create | db_restore | db_migrate | db_drop |
|---|---|---|---|---|---|
| MySQL + Laravel | `mysqldump -u root myapp_dev` | `mysql -u root -e "CREATE DATABASE \`$1\`"` | `mysql -u root "$1"` | `php artisan migrate` | `mysql -u root -e "DROP DATABASE \`$1\`"` |
| PostgreSQL + Prisma | `pg_dump -U postgres --no-owner myapp_dev` | `createdb -U postgres "$1"` | `psql -U postgres -v ON_ERROR_STOP=1 "$1"` | `pnpm install && npx prisma migrate deploy` | `dropdb -U postgres "$1"` |
| PostgreSQL + Drizzle | 同上 | 同上 | 同上 | `pnpm install && npx drizzle-kit migrate` | 同上 |
| SQLite + 任意框架 | `sqlite3 myapp_dev.db .dump` | `touch "$1.db"` | `sqlite3 "$1.db"` | 项目迁移命令 | `rm "$1.db"` |
| MongoDB | `mongodump --archive` | （免建库） | `mongorestore --archive` | 项目迁移命令 | `mongosh "$1" --eval 'db.dropDatabase()'` |

可选增强：结尾加 `tmux new-window -n "$NAME" -c "$DIR"` 自动开 tmux 窗口；PostgreSQL 项目若基准库常年不变，`db_create` 可改用 `createdb -U postgres "$1" -T myapp_baseline` 模板克隆（秒级），此时 `db_restore` 改为 `true`（空操作）；用 Neon/PlanetScale 的项目可改为数据库 branch（copy-on-write），配合 git `post-checkout` hook 全自动化。

### 2.3 派活提示词：边界写死

每个 AI 会话的开场提示必须包含：

```
你在 <分支名> worktree 工作，dev server 端口 <PORT>，数据库 <库名>（= myapp_ + 分支名连字符转下划线，如 feat-ai-task → myapp_feat_ai_task）。
只允许改动 <模块范围>，不许动 <共享文件清单>。
完成后：跑测试 → playwright-cli --headed 走主流程截图自查 → 增量 commit。
```

---

## 3. Worktree 内开发测试流程（每个需求）

```
1. ./scripts/new-worktree.sh feat-x 3001     # 环境一条命令就绪
2. 开发 + 组件/单元测试（边写边跑）
3. 起 dev server（端口 3001，连自己的库）
4. E2E 冒烟：Playwright 打 http://localhost:3001
5. agent 用 playwright-cli --headed 走主流程、截图自查
6. git diff develop...feat-x 自审：无越界改动、无半成品
7. 增量 commit
```

### 3.1 前端三层测试

| 层 | 工具 | 特点 | 何时跑 |
|---|---|---|---|
| 组件级 | Vitest/Jest + Testing Library | 不起服务不连库，毫秒级；后端接口用 MSW mock | 开发中随时 |
| 页面 E2E | Playwright（`baseURL` 走 env） | 打本 worktree 端口 + 本 worktree 库；`webServer` 自动起服务 | 合并前必过 |
| 视觉回归 | Playwright `toHaveScreenshot()` | 基线截图在 develop 生成并入库，改坏别人的页面立刻 diff 出来 | 合并前必过 |

E2E 不求全覆盖，只保关键业务链路：**登录 → 核心业务操作 → 后台能查到结果**。

### 3.2 测试数据策略

- 配置和基础数据来自基准库（见 2.1）。
- **流程前置数据造中间态**：要测第 5 步，seed 直接写第 4 步完成后的状态（如 `status=success` 的任务、已完成订单），不从第 1 步走起。
- E2E 前置态用 API/直接写库创建，UI 只点被测的那一步；全流程 UI 冒烟保留 1-2 条即可。
- 用例自建数据加唯一前缀（`e2e-<时间戳>-`），避免用例间污染。

### 3.3 AI Agent 异步任务的测试

- **联调**：`.env.local` 配测试网关 key/base URL；各 worktree 共用网关、库独立。
- **自动化测试**：本地起假 OpenAI 兼容端点返回固定结果——E2E 不等真 AI、不烧 token、结果可断言。
- 真 AI 联调只留给人工验收环节。

### 3.4 迁移与 schema 冲突战术（并行最高频炸点）

schema/迁移文件是并行开发几乎必然冲突的地方，规则必须前置：

- **每需求只动自己的表/model**；要动共享表（如 `User`、`Order`）必须提前声明并排好合并顺序（§0.5 B 第 4 项收集）。
- 迁移文件名带模块前缀（如 `20260722_points_mall_init`），降低同目录撞名概率。
- **Prisma 迁移历史错位**（后合并的分支与 develop 上的迁移对不上）：在 develop 上 rebase 后，删掉自己分支生成的迁移，重新 `prisma migrate dev` 生成一条新迁移；**禁止手改已合并进 develop 的迁移文件**。
- Laravel/Doctrine 等按时间戳排序的迁移工具同理：后合者重新生成，不改旧文件。

---

## 4. 合并流程（在 develop worktree 执行）

```
对每个待合并分支：
1. git diff develop...feat-x 审查（越界改动？半成品？与其他分支冲突？）
2. 按依赖顺序 merge 到 develop（被依赖的先合；一律 `git merge --no-ff` 保留 merge commit——回归变红时的 revert 回滚和定位都靠它）
3. 每合一个分支：
   - 跑增量迁移
   - npm run test:all   # = 组件单测 + E2E + 视觉回归，与 CI 同一条命令
   - 绿了再合下一个     # 禁止全合完再测，否则问题定位不到来源
4. 🔴 CHECKPOINT：全部合完、develop 全量回归通过 → **停止并交付用户 UAT**，等反馈，不得自行推进发版
5. 🔴 CHECKPOINT：清理不可逆——先列出待执行清单（`git worktree remove <DIR>`（有未提交改动等脏状态才加 `--force`）+ 删分支 + `db_drop <库名>` + 删 registry 对应行：`sed -i '' "/^<NAME>\t/d" .worktree-registry`（macOS；Linux 去掉 `''`）），核对库名与 registry 行一致，**用户确认后**才执行
```

两道保险：**worktree 内全量测一遍** + **每合并一个分支在 develop 回归一遍**。用户拿到的永远是通过完整回归的 develop，只做业务确认，不替你抓 bug。

### 🔴 CHECKPOINT · 🛑 STOP：main 是人工闸门

- 任何人/任何 AI 会话**不允许直接 push 或 merge 到 main**。
- UAT 通过后，由**人手工发起** `develop → main` 的 PR，**人工审核通过后才能合入**。
- 执行到任何涉及 main 的步骤时，agent 必须**停止并报告**，等待人工操作，不得代为执行。
- 因为 develop 已全绿，人工审核主要是业务确认和 diff 过目，不需要再跑测试。

---

## 5. 失败模式：触发条件 → 一线修复 → 兜底

| 触发条件 | 一线修复 | 仍失败兜底 |
|---|---|---|
| 测试偶发失败、时好时坏 | 检查是否只隔离了代码：确认本 worktree 的 PORT 和数据库确实独立 | `lsof -i :<PORT>` 查端口占用；确认 `.env.local` 没被 `.env` 覆盖（优先级问题） |
| 起服务报端口占用 | 换端口并同步改 `.env.local` 的 `PORT` 和 `PLAYWRIGHT_BASE_URL` | 杀掉占用进程；把端口分配登记到团队共享清单防再撞 |
| 测试库缺配置/缺基础数据 | 检查是否用了空库而不是基准库；重跑 `baseline.sql` 恢复 | 配置有更新时：在 develop 开发库重配 → 重新 dump `baseline.sql` → 重建测试库 |
| 测试依赖手工在库里改的数据，develop 回归必炸 | 把手工数据沉淀进 `baseline.sql` 或用例 seed 里 | 禁止任何"手工改库当测试前置"；全部改为可重建脚本 |
| 合并时 migration 冲突 | 检查两分支是否改了同一张表；按依赖顺序调整合并次序 | 在仓库根建 `OWNERS` 文件登记"迁移目录/schema 文件 → owner"；冲突时由 owner 按 §3.4 规则重新生成迁移 |
| 合并某分支后 develop 回归变红 | 问题定位到刚合的这个分支：`git revert -m 1 <merge-commit>` 恢复 develop 全绿 | 回对应 worktree 修复、重跑 worktree 内全量测试，再重新走合并流程 |
| `git worktree add` 后依赖/迁移报错 | 在新 worktree 内重装依赖、只跑本分支新增迁移 | 核对分支是否从 develop 拉出（`git merge-base`）；从 main 拉错的一律重拉 |
| 两个会话疑似在同一目录跑 | 立即停一个；`git worktree list` 核对目录-分支映射 | 按序重建被污染的 worktree：`git worktree remove --force <DIR>` → `db_drop <库名>` → 删 registry 对应行 → 重跑 `new-worktree.sh` |

---

## 6. 反例黑名单（不要做的事）

- ❌ 两个会话在同一目录跑 → 互相覆盖文件。
- ❌ `.env` 提交进仓库 → 所有 worktree 读同一份配置，隔离失效。配置覆盖一律走 gitignore 的 `.env.local`。
- ❌ 只隔离代码不隔离端口/数据库 → 测试偶发失败，其实在"调试干扰"而不是调试代码。
- ❌ 空库当测试环境 → 系统配置都在库里，必须走基准库 dump 方案。
- ❌ 测试依赖手工在库里改的数据 → 别的 worktree 和 develop 回归都没有，必炸。
- ❌ 任务边界不清 → agent 顺手改共享文件，合并冲突爆炸。
- ❌ 合并不看 diff、全合完再测 → 问题无法定位到分支。
- ❌ feature 从 main 拉分支 → 与 develop 上未发布需求错位。
- ❌ AI agent 代为操作 main（push/merge/发版）→ 必须停下来等人。
- ❌ merge 不加 `--no-ff` → fast-forward 没有 merge commit，回归变红时无法 `revert -m 1` 定位回滚。
- ❌ 未列清单、未经用户确认就执行清理（删库 / 删分支 / `worktree remove --force`）→ 不可逆操作必须先确认。

---

## 7. 一页速查

| 动作 | 命令/位置 |
|---|---|
| 开新需求 | `./scripts/new-worktree.sh feat-x 3001`（从 develop 拉分支） |
| 更新基准配置 | 改 develop 开发库 → `db_dump > scripts/baseline.sql` → commit |
| 本分支测试 | `npm run test:all`（worktree 内） |
| 界面自查 | `playwright-cli open --headed http://localhost:3001` |
| 登录态复用 | `playwright-cli state-save/state-load "$WEICOZ_BROWSER_STATE_ROOT/<site>.json"` |
| 合并前审查 | `git diff develop...feat-x` |
| 合并后回归 | develop 上 `npm run test:all`，每合一个跑一遍 |
| 发版 | 🔴 UAT 通过后**手工发起** develop → main PR，人工审核通过才合入 |
| 清理 | 🔴 先列清单经用户确认：`git worktree remove` + 删分支 + `db_drop` 删库 + 删 registry 行 |
