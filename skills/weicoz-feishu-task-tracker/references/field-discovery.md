# 配置取值：怎么把 config.yaml 填满

只读命令，不改任何数据。全部用 `--as user`。

## 1. tasklist guid

从任务清单链接里取：`.../task_list?guid=<这一串>`。

也可以先搜清单名：

```bash
lark-cli task +tasklist-search --query "任务跟踪" --as user --format json
```

## 2. 自定义字段 guid 与选项

```bash
# 列出清单下所有自定义字段（name / type / guid）
lark-cli task custom_fields list \
  --resource-type tasklist --resource-id <tasklist_guid> \
  --page-size 50 --as user --format json
```

`custom_fields list` 不返回选项。单选字段的选项要单独取：

```bash
lark-cli task custom_fields get --custom-field-guid <field_guid> --as user --format json
```

读 `data.custom_field.single_select_setting.options`，每项有 `name` 与 `guid`。

字段类型与写入值对照：

| type | 写入键 | 值的类型 |
|---|---|---|
| `single_select` | `single_select_value` | option_guid 字符串 |
| `number` | `number_value` | **字符串**，如 `"0.4"` |
| `text` | `text_value` | 字符串 |

## 3. 人员 open_id

```bash
# 按姓名查
lark-cli contact +search-user --query "姓名" --as user --format json

# 已知 open_id 时反查姓名（核对用）
lark-cli contact +search-user --user-ids "ou_xxx,ou_yyy" --as user --format json

# 一次查多人
lark-cli contact +search-user --queries "张三,李四" --as user --format json
```

注意是 `contact` 域，不是 `task` 域。

查不到就停下问用户，**不要猜 open_id**。猜错的 ID 写进 `<at>` 会被服务端吞成空，评论里留一片空白，且不会报错。

## 4. 核对配置是否可用

```bash
CONFIG="${WEICOZ_TASK_TRACKER_CONFIG:-$HOME/.config/weicoz-feishu-task-tracker/config.yaml}"
# 用 read 工具读全文，确认没有残留的 <…> 占位符
```

再把配置里的 tasklist guid 拿去读一次清单：

```bash
lark-cli task tasklists tasks --tasklist-guid <guid> --as user --page-all --format json
```

返回 `ok: true` 且有 items 才算配置可用。
