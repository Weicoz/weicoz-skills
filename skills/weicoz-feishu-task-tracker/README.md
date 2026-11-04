# 维护者备注

不属于使用说明（使用看 [SKILL.md](SKILL.md)）。这里只放**实现口径与踩坑记录**；
真实 tasklist guid、字段 guid、人员 open_id 只活在 `~/.config/weicoz-feishu-task-tracker/config.yaml`。

## 为什么配置外置

skill 要能直接分享给同事，所以本体零凭证。所有环境相关的东西（清单 guid、字段 guid、人员 open_id）都在配置里。
换人、换清单、换字段，只改配置，不改 SKILL.md。

## 评论 @ 人：只有一个写法有效

飞书 task v2 评论的 `content` 字段支持内联提及，但语法试错成本高。实测结论：

| 写法 | 结果 |
|---|---|
| `<at id=ou_xxx></at>` | ✅ 解析成真实提及 |
| `<at id="ou_xxx"></at>` | ❌ 被吞成空 |
| `<at user_id="ou_xxx">名</at>` | ❌ 标签被剥掉，只剩名字文本 |
| `<at open_id="ou_xxx">` | ❌ 被吞成空 |
| 纯文本 `@名` | ❌ 保留为字面量，不形成提及 |

**id 值不能加引号** —— 这是最容易踩的一条。

## 验证 @ 只能用 v1 接口

v2 接口回读 `content`，拿到的还是原始 `<at>` 标签，看不出有没有生效。
v1 接口（`GET /open-apis/task/v1/tasks/<guid>/comments`）会把标签渲染成人名，这才是唯一可靠的判据。

v1 的 `rich_content` 写入路线需要 `task:comment` / `task:comment:writeonly` scope，
普通用户 token 没有，所以**写入走 v2、验证走 v1**，两条路各管一头。

## 改评论必须用完整结构

```json
{"comment": {"content": "..."}, "update_fields": ["content"]}
```

只传 `{"content": "..."}` 会报 `99992402 field validation failed`。

## 截止时间的 is_all_day 约束

原任务 `start.is_all_day` 是 `false` 时，`due` 也必须 `false` 并给毫秒时间戳。
否则报 `'is_all_day' of start and due must be same.`。

清空截止时间用 `{"update_fields":["due"],"task":{"due":null}}`，不要传空对象。

## 数字字段要传字符串

「任务/开发进度%」是 `number` 类型，但 `number_value` 必须传字符串 `"0.4"`，传数字会校验失败。

## 读评论的路径

```
GET /open-apis/task/v2/comments?resource_type=task&resource_id=<guid>
```

`/open-apis/task/v2/tasks/<guid>/comments` 是 404，不要用。

## 已完成任务改状态前先重开

`lark-cli task +reopen --task-id <guid>`，否则 patch 状态不生效。

## 催办口径

- 逾期 = 截止已过且未完成。
- 临期 = 默认 24 小时内（可配置）。
- 同一任务同一自然日最多提醒一次。
- 逾期任务当天必须有评论。
- 私信和评论是两件事：只盘点不追加评论。

## 员工环境

没有配置文件的机器上：不猜 guid、不猜 open_id、不翻别处；告诉使用者照
`config.example.yaml` 建配置，只跑只读盘点，不做任何写入。

## 脚本为什么这么切

手工流程走一遍要几十次 lark-cli 调用，还容易在三个地方出错：@ 写法、评论模板、回读校验。
所以切成两个脚本，边界按「读」和「写」分：

| 脚本 | 职责 | 副作用 |
|---|---|---|
| `scripts/task_snapshot.py` | 拉全量任务、算逾期/临期/关注人缺口 | 无，纯只读 |
| `scripts/task_comment.py` | 拼模板、自动取负责人 @、写入或更新、v1 回读校验 | 写评论 |

只读脚本不写任何数据，可以随便反复跑；写脚本内置 `--dry-run`，先看再发。

批量改字段、补关注人、新建任务、重开任务、私信催办**没有**做成脚本：
这些操作每次的字段组合都不一样，参数化收益低，手敲 lark-cli 更直接。

### verify 的判定口径

`--verify` 不指定 `--comment-id` 时是「体检模式」，会列出该任务全部评论：

- 有 `@人名` → `OK`
- 无 `@` → `无@`，不算失败（历史评论本来就没 @）
- 残留原始 `<at` 标签 → `FAIL`（说明服务端没解析）

指定 `--comment-id` 时是「验收模式」，那一条必须有 @，否则 `FAIL`。
早期版本对全部评论一律要求有 @，导致历史评论被误判，已改。

## 变更记录

### 2.3.0

- 增加飞书聊天记录（`lark-cli im`）检索支持，形成「微信 + 飞书」双通道事实读取机制。
- 支持从飞书全局消息、业务群及消息内云文档链接提取会议纪要、排期与资料，与飞书任务清单交叉比对。

### 2.2.0

- 默认集成 `wx-cli` 读取本机微信聊天记录（群聊与私聊），交叉分析会议结论、排期承诺与建单指令。
- 新增双向比对能力：识别飞书已建任务的字段缺口与微信已定但飞书漏建的任务清单。

### 2.1.0

- 新增 `scripts/task_snapshot.py`：只读盘点，输出逾期 / 临期 / 关注人缺口 / 已完成。
- 新增 `scripts/task_comment.py`：评论模板 + 自动 @ 负责人 + 写入/更新 + v1 回读校验。
- SKILL.md 新增「脚本（优先用，别重写）」章节。

### 2.0.0

- 配置外置到 `~/.config/weicoz-feishu-task-tracker/config.yaml`。
- 补齐 @ 语法、v1 回读、is_all_day 约束、数字字段传字符串等实测结论。
