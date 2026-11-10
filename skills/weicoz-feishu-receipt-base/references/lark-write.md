# 飞书批量写入与回读

保留现有 lark-cli 作为唯一写入工具，不自建重试写入客户端。授权只针对本次已展示的计划；用户已确认时直接执行，不重复确认。

写前运行 `receipt_guard.py`，按此文件批量写入；新项目 ID 从创建响应取得，加入计划 `id_map` 后再关联资金流水。每笔流水备注附 `receipt_source_id:<来源唯一键>`，作为回执定位线索，交易指纹仍独立查重。

## 写入命令模板

写入前先展示将要写入的字段，用户确认后执行。JSON 体一律是
`{"create_records":[{字段:值}, …]}` / `{"update_records":{"rec_xxx":{字段:值}}}`，
CLI 不支持 `fields/rows` 形状；以当前 `--help` 为准。

创建资金流水：

```bash
cd <工作目录> && lark-cli base +record-batch-create --base-token "$RECEIPT" --table-id "$FLOW_TBL" --json @./tmp_flow.json
# {"create_records":[{"交易对象":"<payer>","变动日期":"<YYYY-MM-DD HH:mm:ss>","资金变动":<amount>,
#   "变动类型":"款项入账","原文":"<raw_text>","备注":"<remark>","项目收款表":[{"id":"<project_record_id>"}]}]}
```

未匹配项目时 `项目收款表` 传 `[]`，或先新建项目再关联。新建项目收款、更新已收款项、补关联同理，
表 id 换成 `$PROJECT_TBL` / `$FLOW_TBL`，字段名照上文。每次写完删掉临时 json（`rm -f ./tmp_*.json`）。

## lark-cli 实操坑（都实际踩过）

- `--json @file` 的文件**必须是当前目录下的相对路径**。传 `@/tmp/x.json` 报
  `--file must be a relative path within the current directory`；`--json -` 读 stdin 也不支持。
  稳的做法：`cd` 到工作目录，把 JSON 写到 `./tmp_x.json`，用 `--json @./tmp_x.json`。
- 真写之前先加 `--dry-run`：只预览 request body；`ok:true, dry_run:true` 不证明 **Base、表、字段、选项或记录存在**（表 ID 打错也照样回 ok）。仍需最新快照校验。
- 单次批量写上限 200 条。
- **select 单选字段的选项必须先存在**，否则整批失败。加选项走
  `+field-update --field-id <字段名> --json '{"name":"业务","type":"select","multiple":false,"options":[…]}` --yes`：
  这是**全量 PUT 不是 patch**，原有选项要全部带上并保留其 `id`。（`+field-edit` 不存在。）
- **link 字段不能从其他类型转换过来**，也不能转成别的类型 —— 建表时就得定好，错了只能重建表。
- 优先读取响应的 `data.record_id_list` 并与 `data.data` 对齐；本版本可返回记录 ID。若缺失，按当前 CLI 查询能力补查，不能按行号猜 ID。
- `+record-list` 返回的二维数组**列序 = "字段最近使用顺序"**，会随编辑漂移，不要硬编码；先 `+record-get` 一条记录的 `field_id_list` 校准。
- `+record-list` 的数值**有时是字符串**（`"5000"`），本地筛选前先 `float()` 兜底，否则漏行。
- **公式字段异步重算**：写完 `已收款项`/返点字段 后立刻读是旧值，等 3–8 秒再读确认。
- 跨表聚合用 `[表名].FILTER(CurrentValue.[字段]=[本表字段]).[列]`；不要在 FILTER 里再套 FILTER。
- base 子命令统一 `--base-token`（没有 `--app-token`）；身份默认 user；`--limit` 范围 1–200。
- 改字段用 `+field-update`（high-risk，要 `--yes`）；formula 字段改名时 expression 要一并带上（全量 PUT）。


## 失败与完成

- 金额未知、来源不明、计划校验失败时，继续独立的已确认部分；不能用未知值凑齐写入。
- 写入超时或报错时先读当前状态，保存返回的记录 ID。没有状态证据，不重复 create；不要给写 API 自动重试。
- 写后重新运行 `lark_snapshot.py`，再运行 `receipt_guard.py PLAN --after SNAPSHOT`。只有金额、关联、公式值全部匹配才报已验证；请求成功不代表业务成功。
- 已付/待付切换时同时维护支付流水和项目余额。未支付的返点只写待付字段，不创建虚假支出。
- 工资表写入不属于普通收款入账的隐含授权，按用户请求核算和写入。
