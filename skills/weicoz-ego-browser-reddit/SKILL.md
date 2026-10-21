---
name: weicoz-ego-browser-reddit
version: 1.0.0
description: |
  用 ego-browser 优先执行 Reddit 查询、搜索、帖子阅读、评论提取与结果归档。用户提到“用 ego-browser 查 Reddit”“打开 Reddit 帖子”“搜索 Reddit 关键词”“抓 Reddit 评论”“把 Reddit 查询结果落盘成文件”“一边给我结果一边保存文档”时都应使用本 skill。它负责查询执行、结果整理、标准化落盘和对话内回报；不负责发帖、评论、点赞或账号运营。
allowed-tools: Bash(ego-browser:*), Bash(bsk:*), Bash(mkdir:*), Bash(date:*), Bash(cat:*), Bash(printf:*), Bash(test:*), Bash(pwd:*)
---

# Weicoz Ego Browser Reddit

用 `ego-browser` 优先完成一次性 Reddit 查询任务，并把结果同时交付到对话和文件。

## 触发范围

出现下面任一类需求就用本 skill：

- 用 `ego-browser` 查 Reddit
- 打开某个 Reddit 页面或帖子并确认能否访问
- 搜某个关键词、subreddit、用户或 thread
- 提取帖子正文、评论、链接
- 把本次查询结果保存成 markdown 文件
- 既要即时汇报，也要留下可复用的文档结果

## 默认原则

1. 浏览器固定优先级：`ego-browser` -> `browser-skill` -> `@Chrome`。
2. 只有当前工具不可用，或已确认无法完成当前页面能力时，才进入下一层；必须记录失败信号，不能因操作习惯直接跳级。
3. 每次任务都要有两份输出：
   - 对话内简明结果
   - 文件落盘结果
4. 优先复用已有目录：默认写到 `${WEICOZ_OUTPUT_ROOT:-$PWD}/projects/reddit-research/runs/<timestamp>/`。
5. 不覆盖旧结果。每次新建时间戳目录。
6. 如果任务里打开了额外 tab，结束后关闭自己打开的 tab。

## 默认落盘位置

默认输出根目录：

```text
projects/reddit-research/runs/<YYYY-MM-DD-HHMMSS>/
```

至少写这 3 个文件：

- `report.md`：给用户看的最终结果摘要
- `evidence.md`：原始搜索命中、thread 要点、评论证据
- `run-state.json`：运行时间、查询词、状态、失败信息

如果任务里涉及多个链接，额外写：

- `raw-links.md`

## 浏览器路由

### 1. ego-browser

- 通过 `ego-browser nodejs <<'EOF' ... EOF` 执行。
- 用 `useOrCreateTaskSpace` 创建并复用同一 task space。
- 搜索页用 `openOrReuseTab` 打开 Reddit 搜索 URL，先 `snapshotText()`，需要结构化正文/评论时再用 `js()` 提取。
- 指定帖子直接打开 canonical thread URL，提取 OP、评论、作者、时间和永久链接。
- 任务确认完成后，单独一次 heredoc 调用 `completeTaskSpace(taskId, { keep: false })`。

### 2. browser-skill fallback

仅 ego-browser 不可用或无法完成当前能力时使用。严格执行 `bsk session start` -> `bsk navigate/snapshot/... --session <id>` -> `bsk session stop <id>`，包括失败路径。

### 3. @Chrome fallback

仅 browser-skill 也不可用或无法完成当前能力时使用。加载 `chrome:control-chrome`，按其 `browser-client` 工作流复用 Chrome 登录态和 tab binding。

## 执行流程

### Step 1: 判定任务类型

先判断用户要的是哪一种：

- 可访问性验证
- 关键词搜索
- 指定 thread 阅读
- 多链接整理

没有必要时不要混做。

### Step 2: 执行最短查询

- 搜索类：先打开 Reddit 搜索结果页，再提取候选 thread URL
- 帖子类：直接打开 thread URL，读取 OP 和评论
- 访问验证类：核对标题、URL 和页面正文

如果命令失败，保留失败信息，不要装成功。

### Step 3: 整理结果

对结果只保留高信号信息：

- 查询词
- subreddit
- 标题
- URL
- 正文摘要
- 关键评论/证据
- 本次结论

不要把整页噪音原样倒进去。

### Step 4: 写文件

创建时间戳目录，写入：

- `report.md`
- `evidence.md`
- `run-state.json`
- 需要时 `raw-links.md`

### Step 5: 回给用户

对话里必须同时给出：

- 任务是否成功
- 最关键结果
- 落盘目录路径

## 输出模板

### report.md

```md
# Reddit 查询报告

- 时间：
- 查询类型：
- 查询参数：

## 结果摘要

## 关键发现

## 结论
```

### evidence.md

```md
# Reddit 查询证据

## 搜索命中 / 帖子

## 正文摘要

## 关键评论

## 原始说明
```

### run-state.json

```json
{
  "status": "success",
  "timestamp": "2026-06-28-200000",
  "query_type": "search",
  "query": "example",
  "artifacts": [
    "report.md",
    "evidence.md",
    "run-state.json"
  ],
  "error": ""
}
```

## 失败分支

- Reddit 打不开：记录失败信息，写 `status=failed`，把报错写进 `run-state.json`
- 搜索没结果：照样落盘，明确写“0 命中”
- thread 读取不完整：说明读到哪，缺什么，不要补脑

## 禁止事项

- 不自动发帖、评论、点赞
- 不伪造未读到的评论内容
- 不只在聊天里说结果而不落盘
- 不覆盖旧 run
