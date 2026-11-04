---
name: weicoz-feishu-task-tracker
version: 2.2.0
description: 管理飞书“任务跟踪”清单。用户提到飞书任务、任务跟踪、逾期任务、临期提醒、负责人催办、任务评论汇报、会议纪要转任务、关注人同步时必须使用。默认结合 wx-cli 读取本机微信聊天记录（群聊与私聊的会议排期、任务下发与责任人承诺）交叉比对；识别飞书逾期、漏建与字段缺失任务，把会议安排写进任务评论或改字段，并在评论中 @ 负责人，让关注人可见。
whenToUse: 用户要求盘点飞书任务、催办负责人、把会议纪要/微信沟通记录落到任务评论、核对漏建任务、更新任务状态或截止时间、核对关注人时。
---

# 飞书任务跟踪

把会议纪要、微信沟通记录、逾期盘点落成飞书任务上的**可核对动作**：交叉比对漏建任务、改字段、写评论、@ 负责人、补齐关注人。

本 skill 本体不含任何 token、tasklist guid、人员 open_id。全部走 skill 目录之外的私有配置。

## 四种用法

| 场景 | 入口 |
|---|---|
| 「会议/微信沟通转任务与检查漏建」 | 默认调 `wx-cli` 读群聊/私聊排期与建单指令 → 对照飞书清单识别已建与漏建 → 补建或改字段 |
| 「今天有哪些任务逾期/临期」 | `scripts/task_snapshot.py`（只读，随便跑） |
| 「把这段会议安排写到任务上」 | `scripts/task_comment.py` 写评论 + `lark-cli task tasks patch` 改字段 |
| 「催办一下逾期的负责人」 | `task_snapshot.py` 出名单 → `lark-cli im +messages-send --as user` 逐人私信 |

**先跑脚本，脚本覆盖不到才手敲命令。** 脚本把 @ 语法、评论模板、回读校验都封装了，手敲容易在细节上翻车。

## 第 0 步：读私有配置（每次都做，不许跳）

| 路径 | 说明 |
|---|---|
| `~/.config/weicoz-feishu-task-tracker/config.yaml` | **标准位置**，默认就读这个 |
| `$WEICOZ_TASK_TRACKER_CONFIG` | 环境变量；设了就优先用它 |
| `<skill 目录>/config.example.yaml` | 结构模板，**只做对照，不是配置** |

```bash
CONFIG="${WEICOZ_TASK_TRACKER_CONFIG:-$HOME/.config/weicoz-feishu-task-tracker/config.yaml}"
ls -l "$CONFIG"          # 不存在就停下，让用户先建
```

用 **read 工具**读全文，不要 `cat` 到终端 —— open_id 与清单地址会进终端历史。
每次开工重读一遍，不沿用上一轮缓存。

### 配置键怎么用

| 配置键 | 用在哪儿 |
|---|---|
| `tasklist.guid` | 所有 tasklist 级命令的 `--tasklist-guid` |
| `followers.default` | 新建任务、补关注人时的默认三人名单 |
| `members` | 姓名 → open_id 映射；写评论 @ 人时查这里 |
| `fields.status.guid` | 自定义字段「状态」的 guid |
| `fields.status.options` | 状态名 → option_guid（如 `2.进行中`） |
| `fields.progress.guid` | 自定义字段「任务/开发进度%」的 guid |
| `fields.project.guid` | 自定义字段「项目名称」的 guid |
| `fields.project.options` | 项目名 → option_guid |
| `comment.template` | 评论固定格式 |

### 配置缺失时

**不要猜 guid、不要猜 open_id、不要凭记忆写死** —— 先停，告诉用户照 `config.example.yaml` 建配置。
建法：

```bash
mkdir -p ~/.config/weicoz-feishu-task-tracker
cp <skill 目录>/config.example.yaml ~/.config/weicoz-feishu-task-tracker/config.yaml
chmod 600 ~/.config/weicoz-feishu-task-tracker/config.yaml
```

guid 与 open_id 的取法见 `references/field-discovery.md`。

## 前提检查

```bash
which lark-cli && lark-cli auth status

# 微信聊天分析前置（涉及会议纪要、内部沟通转任务时默认调用）
WX_SH="${HOME}/.agents/skills/wx-cli/scripts/wx.sh"
[ -f "$WX_SH" ] || WX_SH="${HOME}/.agents/skill-tiers/library/wx-cli/scripts/wx.sh"
bash "$WX_SH" daemon status
```

`lark-cli` 不在 PATH 或登录态失效时先停下告知用户；微信 daemon 未启动时按 wx-cli 指引拉起。

## 脚本（优先用，别重写）

两个脚本已把「逐条调 lark-cli、拼评论、@ 人、回读校验」封装好。**先跑脚本，脚本覆盖不到的场景才手敲命令。**

### scripts/task_snapshot.py —— 只读盘点

```bash
python3 scripts/task_snapshot.py                          # 文本表格
python3 scripts/task_snapshot.py --json                   # 机器可读
python3 scripts/task_snapshot.py --now 2026-10-21T14:30:00  # 指定「现在」，便于复现
```

输出四段：逾期未完成（含逾期天数）／临期（`reminder.due_soon_hours`，默认 24h）／关注人缺默认名单／已完成计数。
只读，不写任何飞书数据。可安全反复跑。

### scripts/task_comment.py —— 写评论 + 自动 @ + 回读校验

```bash
# 1. 先预览，确认措辞与 @ 对象
python3 scripts/task_comment.py --task-guid <guid> \
  --status 进行中 --progress "前端对接未完成" \
  --risk "暂无" --next "今日 17:30 前出基础流程结果" --eta "2026-10-21" --dry-run

# 2. 去掉 --dry-run 正式写入（写完自动回读校验，@ 未生效则 exit 1）

# 3. 改已有评论（保留 comment id）
python3 scripts/task_comment.py --task-guid <guid> --comment-id <id> --status ... 

# 4. 只校验某任务评论的 @ 是否生效
python3 scripts/task_comment.py --task-guid <guid> --verify [--comment-id <id>]
```

脚本行为：

- @ 对象从任务的 `members`（role=assignee, type=user）自动取，**不用手填 open_id**。
- 评论模板取自配置 `comment.template`。
- 写完自动走 v1 接口回读，把 @ 渲染成人名才算通过。
- `--verify` 不指定 `--comment-id` 时，历史评论无 @ 标「无@」（正常，不算失败）；只有残留原始 `<at` 标签才判失败。

### 脚本覆盖不到时

批量改字段、补关注人、新建任务、重开任务、私信催办仍用下面的 lark-cli 命令。

## 读任务

```bash
# 清单全部任务
lark-cli task tasklists tasks --tasklist-guid "$GUID" --as user --page-all --format json

# 单任务详情（含 custom_fields）
lark-cli task tasks get --task-guid "$TGUID" --as user --format json
```

评论用 **v2** 接口读：

```bash
lark-cli api GET /open-apis/task/v2/comments \
  --params '{"resource_type":"task","resource_id":"<TGUID>","page_size":50}' --as user
```

不得用 `/open-apis/task/v2/tasks/<guid>/comments`（404）。

## 写评论（含 @ 负责人）

```bash
lark-cli task +comment --task-id "$TGUID" --content "$CONTENT" --as user --format json
```

**@ 语法只有一种有效写法**：`<at id=ou_xxx></at>`

- id 值**不得加引号**。
- 多个 @ 并排写，标签之间留空格。
- 无效写法（已实测，标签会被剥离或吞成空）：`<at user_id="ou_x">名</at>`、`<at open_id="ou_x">`、`<at id="ou_x">`、纯文本 `@名`。

评论固定格式：

```text
<at id=ou_xxx></at> 【任务跟踪｜YYYY-MM-DD】
状态：进行中 / 已完成 / 阻塞 / 逾期
进展：
问题/风险：
下一步：
预计完成：
```

### 改已有评论

必须用完整结构，只传 `content` 会报 `99992402 field validation failed`：

```bash
lark-cli api PATCH /open-apis/task/v2/comments/<COMMENT_ID> \
  --data '{"comment":{"content":"<新内容>"},"update_fields":["content"]}' --as user
```

### 验证 @ 是否真的生效

v2 接口回读仍是原始标签，**看不出来**。唯一可靠路径是 **v1 接口**，它会把标签渲染成人名：

```bash
lark-cli api GET /open-apis/task/v1/tasks/<TGUID>/comments \
  --params '{"page_size":50}' --as user
```

`items[].content` 显示 `@罗嘉理` 即为成功；显示空或残留字面量即失败。

## 改字段

```bash
lark-cli task tasks patch --task-guid "$TGUID" \
  --data '{"update_fields":["due","custom_fields"],"task":{...}}' --as user --format json
```

- 进度：`{"guid":"<progress_guid>","number_value":"0.4"}` —— **字符串**，不是数字。
- 状态：`{"guid":"<status_guid>","single_select_value":"<option_guid>"}`。
- 截止时间：`{"due":{"is_all_day":true,"timestamp":"<ms>"}}`。

**坑**：原任务 `start.is_all_day=false` 时，`due` 也必须 `is_all_day=false` 并给具体时间戳，否则报 `'is_all_day' of start and due must be same.`

清空截止时间：`{"update_fields":["due"],"task":{"due":null}}`。

## 关注人

```bash
lark-cli task +followers --task-id "$TGUID" --add "ou_a,ou_b,ou_c" --as user --format json
```

`--add` 支持逗号分隔多个。新建任务与补齐关注人时都用 `followers.default` 三人名单。

## 重开已完成任务

已标记完成的任务要改状态，先重开：

```bash
lark-cli task +reopen --task-id "$TGUID" --as user --format json
```

## 结合微信聊天记录与会议纪要落成任务动作（默认流程）

涉及会议排期、内部沟通、任务下发或检查漏建时，**默认使用 wx-cli** 读取本机微信聊天记录作为一手事实源，与飞书任务清单交叉比对：

1. **调用 wx-cli 提取沟通事实**：
   ```bash
   WX_SH="${HOME}/.agents/skills/wx-cli/scripts/wx.sh"
   [ -f "$WX_SH" ] || WX_SH="${HOME}/.agents/skill-tiers/library/wx-cli/scripts/wx.sh"

   # 1. 搜索关键词（如 会议、任务、排期、项目名）
   bash "$WX_SH" search "会议" --limit 20
   # 2. 拉取工作群时间段历史（如「嘉云网络」或对应群聊）
   bash "$WX_SH" history "<群名或群ID>" --since YYYY-MM-DD --until YYYY-MM-DD
   # 3. 拉取关键负责人私聊确认记录
   bash "$WX_SH" history "<负责人联系人名>" --since YYYY-MM-DD
   ```

2. **抽提核心契约**：
   - 抽出「谁（负责人）、做什么（具体模块/功能）、承诺什么时候完成（截止日期）、群内是否已下发建单/测试指令、关联方案路径」。

3. **双向比对飞书现有任务清单**：
   - **已建任务**：比对字段完整性（状态是否未填、进度% 是否对齐、截止日是否一致、关注人是否包含三人名单、是否需更新最新评论并 @ 负责人）。
   - **漏建任务**：群内/纪要中已定排期但飞书任务清单无对应条目者，列为「漏建任务」，明确责任人、排期与建议标题。

4. **确认与写入**：
   - 用户要求确认时，一次给出「已建待补字段 N 条 / 漏建需新建 M 条」明细。
   - 新建任务写入默认值：状态「1.待进行」、进度 `0`、截止时间对齐沟通承诺、关注人写入 `followers.default` 三人名单。
   - 写入后逐条回读：字段值、评论数、@ 渲染结果、关注人名单。
   - 汇报时给出任务标题、改动明细与回读结果，不贴 open_id。

## 催办与盘点

1. 读清单，保留标题、负责人、关注人、截止、状态、进度、最近评论。
2. 分类：逾期（截止已过且未完成）、临期（默认 24 小时内）、已完成（不催办）。
3. 去重：同一任务同一自然日最多提醒一次；负责人近期已明确回复的不重复催问。
4. 逾期任务当天必须有评论；未逾期但连续 3 天无评论也提醒。
5. 定时检查默认每周一至周六 10:00、14:30 各一次，周日跳过；两个时间点用两条 cron。
6. 私信提醒用 `lark-cli im +messages-send --as user`，按负责人分组，不得只向用户汇总。
7. 发送后用 `lark-cli im +messages-mget --as user` 逐条回读，确认 `ok: true` 且正文一致。

### 字段完整性检查

每次盘点一并检查：状态、进度、负责人、截止、关注人。缺失或长期未更新进提醒范围。

**评论缺失不等于任务字段缺失** —— 不要把「没有评论」报成「字段未填」。

### 提醒消息要写什么

逾期提醒：说明已逾期，要求回复逾期原因、当前进度、已遇或潜在问题、预计完成时间，并补齐缺失字段。

临期提醒：说明剩余时间，要求尽快处理；状态或进度缺失时一并要求补齐。

### 私信身份与失败处理

- 默认用 `--as user`。**不要先用 bot** —— bot 不在负责人可用范围时会返回 `Bot has NO availability to this user.`。
- `--as user` 失败时记录原始错误并向用户汇总，**不自动改 bot 重试**，不把失败记为已送达。
- 带 `--idempotency-key`（含日期、批次、负责人标识）避免重复发送；同一任务同一自然日仍最多一次。
- 用户汇总与负责人催办是两个独立交付：负责人逐人收到可执行提醒，用户本人收到全局盘点与送达结果。一边成功不能代替另一边。

### 创建任务的默认值

新建任务默认写入：状态「1.待进行」、进度 `0`、开始时间 = 创建时间；关注人用 `followers.default` 三人。

字段不存在或 API 不支持时**明确报告未设置**，不得伪造成功。

## 边界

- 不猜负责人、截止、完成状态；字段缺失标「待确认」。
- 不自动改截止、负责人、关注人、状态，除非用户明确要求。
- 私信不是任务评论：只做盘点或催办时不追加评论。
- 接口未返回字段 ≠ 字段未填写；开发进度 `0` 是有效值。
- 私信结尾统一 `【AI提醒】`；换行必须是真实换行，不得发送字面量 `\n`。
- 发送成功以 `ok: true` 或退出码 0 为准，`messages-mget` 回读为最终证据。
- 不得在输出、日志、提交中回显 token、清单地址或 open_id。

## 输出

默认中文、短表格、先结论后证据。无逾期任务明确写「今日无逾期未完成任务」。
