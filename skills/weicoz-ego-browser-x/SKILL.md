---
name: weicoz-ego-browser-x
version: 1.0.0
description: |
  用 ego-browser 优先执行 x.com 查询、搜索、用户页读取、线程提取与结果归档。用户提到“用 ego-browser 查 x.com”“搜索 X 推文”“抓 x.com 帖子和回复”“看某个账号最近发了什么”“把 X 查询结果落盘成文件”“一边给我结果一边保存文档”时都应使用本 skill。它负责查询执行、结果整理、标准化落盘和对话内回报；不负责发帖、回复、点赞、转发或账号运营。
allowed-tools: Bash(ego-browser:*), Bash(bsk:*), Bash(mkdir:*), Bash(date:*), Bash(cat:*), Bash(printf:*), Bash(test:*), Bash(pwd:*)
---

# Weicoz Ego Browser X

用 `ego-browser` 优先完成一次性 `x.com` 查询任务，并把结果同时交付到对话和文件。

## 触发范围

出现下面任一类需求就用本 skill：

- 用 `ego-browser` 查 `x.com`
- 打开某个 `x.com` 页面或帖子并确认能否访问
- 搜某个关键词、账号、thread
- 提取推文正文、回复、链接
- 看某个账号最近发了什么
- 把本次查询结果保存成 markdown 文件
- 既要即时汇报，也要留下可复用的文档结果

## 默认原则

1. 浏览器固定优先级：`ego-browser` -> `browser-skill` -> `@Chrome`。
2. 只有当前工具不可用，或已确认无法完成当前页面能力时，才进入下一层；必须记录失败信号，不能因操作习惯直接跳级。
3. 优先直接打开 X 搜索页、thread URL 或用户时间线，不做无关页面探索。
4. 每次任务都要有两份输出：
   - 对话内简明结果
   - 文件落盘结果
5. 优先复用已有目录：默认写到 `${WEICOZ_OUTPUT_ROOT:-$PWD}/projects/x-research/runs/<timestamp>/`。
6. 不覆盖旧结果。每次新建时间戳目录。
7. 如果任务里打开了额外 tab，结束后关闭自己打开的 tab。

## 默认落盘位置

默认输出根目录：

```text
projects/x-research/runs/<YYYY-MM-DD-HHMMSS>/
```

至少写这 3 个文件：

- `report.md`：给用户看的最终结果摘要
- `evidence.md`：原始搜索命中、thread 要点、回复证据
- `run-state.json`：运行时间、查询词、状态、失败信息

如果任务里涉及多个链接，额外写：

- `raw-links.md`

## 浏览器路由

### 1. ego-browser

- 通过 `ego-browser nodejs <<'EOF' ... EOF` 执行。
- 用 `useOrCreateTaskSpace` 创建并复用同一 task space。
- 搜索、thread、用户页均用 `openOrReuseTab` 打开真实 `x.com` URL；先 `snapshotText()`，需要结构化正文/回复时再用 `js()` 提取。
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
- 用户资料/时间线读取
- 多链接整理

没有必要时不要混做。

### Step 2: 执行最短查询

- 搜索类：打开 X 搜索结果页，提取命中推文 URL
- 帖子类：直接打开 thread URL，读取正文和回复
- 用户类：打开用户页或时间线
- 访问验证类：核对标题、URL 和页面正文

如果命令失败，保留失败信息，不要装成功。

### Step 3: 整理结果

对结果只保留高信号信息：

- 查询词
- 账号 / handle
- 标题或首句
- URL
- 正文摘要
- 关键回复/证据
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
# X 查询报告

- 时间：
- 查询类型：
- 查询参数：

## 结果摘要

## 关键发现

## 结论
```

### evidence.md

```md
# X 查询证据

## 搜索命中 / 帖子

## 正文摘要

## 关键回复

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

- `x.com` 打不开：记录失败信息，写 `status=failed`，把报错写进 `run-state.json`
- 搜索没结果：照样落盘，明确写“0 命中”
- thread 读取不完整：说明读到哪，缺什么，不要补脑
- 用户页读取受登录态限制：明确写登录态限制，不要伪造数据

## 禁止事项

- 不自动发帖、回复、点赞、转发
- 不伪造未读到的回复内容
- 不只在聊天里说结果而不落盘
- 不覆盖旧 run
