---
name: weicoz-feishu-receipt-base
description: 用 lark-cli 处理飞书多维表财务收款入账。Use when user sends 银行转账短信、农行转入通知、客户付款消息、要求写入或预览“财务收款表/项目收款表”和“资金流水表”，或需要根据付款公司、时间、金额匹配项目并生成飞书 Base 写入方案。
---

# weicoz-feishu-receipt-base

把银行转账短信转成飞书 Base 入账动作。默认先预览，只有用户明确要求写入或确认后才执行写操作。

## 固定表

Base token: `$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN`

项目收款表 / 财务收款表:
- Table ID: `$WEICOZ_FEISHU_RECEIPT_PROJECT_TABLE_ID`
- URL view: `$WEICOZ_FEISHU_RECEIPT_PROJECT_VIEW_ID`
- 关键字段: `项目`, `客户/渠道公司`, `实收款`, `待收款项`, `业务`, `转款莞云/其他`, `返点渠道`, `变动关联`, `成交时间`, `备注`, `收款总额/项目金额`, `已收款项`
- 公式字段不要写: `实收款`, `待收款项`, `成交时间-提取年月`

资金流水表:
- Table ID: `$WEICOZ_FEISHU_RECEIPT_LEDGER_TABLE_ID`
- URL view: `$WEICOZ_FEISHU_RECEIPT_LEDGER_VIEW_ID`
- 关键字段: `备注`, `原文`, `交易对象`, `变动日期`, `业务`, `资金变动`, `变动类型`, `项目收款表`
- 公式字段不要写: `变动日期-提取年月`

## 工具前置

先确认 `lark-cli` 可用和登录态有效:

```bash
which lark-cli
lark-cli auth status
```

必要时复查字段:

```bash
lark-cli base +field-list --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_PROJECT_TABLE_ID"
lark-cli base +field-list --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_LEDGER_TABLE_ID"
```

## 短信解析

从银行短信抽取:
- `payer`: 付款方公司或个人
- `paid_at`: 转账时间；短信无年份时默认当前年份
- `amount`: 转入金额，正数
- `bank_tail`: 收款账户尾号，如 `<尾号>`
- `raw_text`: 完整短信原文
- 忽略余额、尊称、账户问候语

农行常见格式:

```text
【中国农业银行】尊敬的客户：<付款方>于<月日时分>向贵公司的农行账户（尾号<尾号>）完成转入交易，金额为<金额>，余额为<余额>。
```

解析结果:
- `payer=<付款方>`
- `paid_at=<当前年份>-06-22 11:27`
- `amount=20000`
- `bank_tail=<尾号>`

## 入账规则 v1

1. 必建或准备建资金流水。
2. 再按付款方匹配项目收款表。
3. 唯一匹配时，关联该项目并更新项目已收款项。
4. 多匹配时，只准备资金流水，问用户确认项目。
5. 未匹配时，准备新建项目收款记录，项目名用 `新项目-待补`。

资金流水默认字段:
- `交易对象` = `payer`
- `变动日期` = `paid_at`
- `资金变动` = `amount`
- `变动类型` = `款项入账`
- `原文` = `raw_text`
- `备注`:
  - 已识别项目: `农行短信 MM/DD HH:mm 转入｜<项目名>`
  - 未识别项目: `农行短信 MM/DD HH:mm 转入｜新记录（项目待补）`

新建项目收款默认字段:
- `客户/渠道公司` = `payer`
- `成交时间` = `paid_at` 当天
- `已收款项` = `amount`
- `收款总额/项目金额` = `amount`
- `项目` = `新项目-待补`
- `备注` = `农行短信转入，项目待补`

## 匹配项目

优先用 `record-list` 读取小字段集合，再本地匹配，避免拉无关字段:

```bash
lark-cli base +record-list --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_PROJECT_TABLE_ID" --format json --limit 200 --field-id '客户/渠道公司' --field-id '项目' --field-id '已收款项' --field-id '收款总额/项目金额' --field-id '备注'
```

匹配顺序:
1. `客户/渠道公司` 精确等于付款方。
2. 去掉括号、空格、常见后缀差异后再近似匹配。
3. 结合项目备注和金额判断是否像旧项目尾款。

不要仅凭相似公司名自动更新项目。多条候选或金额归因不清时，问用户一句确认。

## 写入命令模板

写入前先展示将要写入的字段。用户确认后执行。

创建资金流水:

```bash
lark-cli base +record-batch-create --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_LEDGER_TABLE_ID" --json '{"fields":["交易对象","变动日期","资金变动","变动类型","原文","备注","项目收款表"],"rows":[["<payer>","<YYYY-MM-DD HH:mm:ss>",<amount>,["款项入账"],"<raw_text>","<remark>",[{"id":"<project_record_id>"}]]]}'
```

未匹配项目时，`项目收款表` 用空数组 `[]`，或先新建项目后再关联。

新建项目收款:

```bash
lark-cli base +record-batch-create --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_PROJECT_TABLE_ID" --json '{"fields":["客户/渠道公司","成交时间","已收款项","收款总额/项目金额","项目","备注"],"rows":[["<payer>","<YYYY-MM-DD HH:mm:ss>",<amount>,<amount>,"新项目-待补","农行短信转入，项目待补"]]}'
```

更新现有项目已收款项:

```bash
lark-cli base +record-batch-update --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_PROJECT_TABLE_ID" --json '{"record_id_list":["<project_record_id>"],"patch":{"已收款项":<old_received_plus_amount>}}'
```

必要时补关联:

```bash
lark-cli base +record-batch-update --as user --base-token "$WEICOZ_FEISHU_RECEIPT_BASE_TOKEN" --table-id "$WEICOZ_FEISHU_RECEIPT_LEDGER_TABLE_ID" --json '{"record_id_list":["<flow_record_id>"],"patch":{"项目收款表":[{"id":"<project_record_id>"}]}}'
```

## 输出给用户

收到短信后，先输出:
- 解析结果: 付款方、时间、金额、银行尾号
- 匹配判断: 唯一匹配 / 多候选 / 未匹配
- 准备写入: 资金流水字段、项目收款字段或更新字段
- 需要确认: 只有歧义或写入前确认

写入后，输出:
- 创建或更新的表
- 记录 ID
- 未补字段，如 `项目`, `业务`, `收款总额/项目金额`

## 脱敏样例

短信:

```text
【中国农业银行】尊敬的客户：示例付款方有限公司于<月日时分>向贵公司的农行账户（尾号<尾号>）完成转入交易，金额为<金额>，余额为<余额>。
```

解析:
- `payer=示例付款方有限公司`
- `paid_at=<YYYY-MM-DD HH:mm>`
- `amount=<金额>`
- `bank_tail=<尾号>`

默认预览:
- 资金流水: `款项入账`, `交易对象=示例付款方有限公司`, `资金变动=<金额>`, `备注=农行短信 <月日时分> 转入｜新记录（项目待补）`
- 项目收款: 若未匹配旧项目，则新建 `新项目-待补`
