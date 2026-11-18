# Field Rules

## Canonical Template

标准模板只有一份，放在 skill 目录的 `assets/`，**不入 git**（模板含银行卡号与手机号，公开仓库会泄露）：

```
$SKILL_DIR/assets/定制开发合同-通用模板.docx
```

新设备拉下仓库后 `assets/` 是空的，需要从桌面副本或备份复制一次，或设置 `$WEICOZ_CONTRACT_TEMPLATE` 指向任一可读副本。模板被移动或删除时先找这两个位置，不要另造模板。

先解析 `SKILL_DIR`，取第一个存在模板的目录：

1. `$WEICOZ_CONTRACT_SKILL_DIR`（显式指定时优先）
2. `$HOME/.agents/skill-tiers/library/weicoz-custom-contract-docx`（L3 分层副本）
3. `${WEICOZ_SKILLS_REPO:-$HOME/File/git/weicoz-skills}/skills/weicoz-custom-contract-docx`（主仓）

不要用 `$WEICOZ_SKILLS_ROOT/weicoz-custom-contract-docx`：该软链指向 L3 生成桩，桩里只有 `SKILL.md`，没有 `scripts/` 和 `assets/`。

`$HOME/Desktop/定制开发合同--通用（非标准功能售卖）.docx` 是同一份文件的桌面副本，md5 一致。桌面文件被移动、改名或删除时，用 skill 内这份，不要另找模板。

同目录曾有三份同名副本（`_副本.docx`、`_副本2.docx`），md5 与主模板一致，已移入废纸篓。模板正文留有错字占位符 `{{[price}}`、`{{[price_zh}}`，以及把 `{{customer_name}}`/`{{customer_email}}` 放在乙方联系人位的写法；脚本按段落前缀整段重写这些位置，错字不会进入成品，`--check` 兜底。

模板关键占位：`{{title:功能名称}}`、`{{image:需求清单}}`、`{{price}}`、`{{price_zh}}`、`{{price_after}}`、`{{year}}/{{month}}/{{day}}`。

## Config JSON Schema

最小可用结构：

```json
{
  "principal_name": "何勇军",
  "customer_contact": "何勇军",
  "project_title": "链动1+1滑落调整定制开发",
  "price": "7000",
  "price_after_percent": "20",
  "delivery_days": "5",
  "vendor_contact": "<乙方联系人>",
  "vendor_email": "<乙方邮箱>",
  "feature_title": "链动1+1滑落调整需求功能清单",
  "feature_rows": [
    {
      "type": "管理后台",
      "type_desc": "基础设置",
      "module_name": "滑落设置",
      "feature_desc": "不滑落用户，基于不滑落机制进行奖励"
    },
    {
      "type": "管理后台",
      "type_desc": "奖励设置",
      "module_name": "奖励发放调整",
      "feature_desc": "按月度发放指定奖励类型，可自定义发放日期"
    }
  ]
}
```

## Supported Fields

- `contract_no`
- `sign_year`
- `sign_month`
- `sign_day`
- `principal_name`
- `principal_same_as_contact`
- `customer_contact`
- `customer_phone`
- `customer_address`
- `customer_landline`
- `customer_bank`
- `customer_email`
- `project_title`
- `price`
- `price_zh`
- `price_after`
- `price_after_percent`
- `delivery_days`
- `vendor_contact`
- `vendor_email`
- `feature_title`
- `feature_image_path`
- `feature_image_paths`
- `feature_headers`
- `feature_rows`
- `feature_rows_per_image`
- `feature_image_width`
- `feature_image_output`

## Business Rules

- 未提供的甲方字段留空。
- `principal_same_as_contact=true` 且 `principal_name` 为空时，自动把 `customer_contact` 复制给 `principal_name`。
- `price_after` 为空但提供了 `price_after_percent` 时，脚本按 `price * percent / 100` 自动计算。
- `price_zh` 为空时，脚本只对整数金额自动生成中文大写金额主体，例如 `7000 -> 柒仟`。
- 如果金额带小数，优先让用户显式提供 `price_zh`，避免模板尾部的 `圆整` 与真实金额冲突。
- 用户没给续费比例时，默认按开发费的 20%/年计（历史合同惯例：360000 -> 72000）。写入后提示用户复核。
- 甲方联系人/邮箱全空时，脚本写入全角空位供手填，不留 `【】`。

## Feature Image Rules

- 优先级：`feature_image_paths` > `feature_image_path` > `feature_rows`。
- 用户已给出整页截图时用 `feature_image_paths`，按页顺序传入，脚本按满版心宽度逐张插入。
- 只有行数据时脚本渲染标准化功能清单图。默认宽度 1600px，按 155.9mm 版心插入后约 7.5pt，可读。
- `feature_rows` 的单行字段：
  - `type`
  - `type_desc`
  - `module_name`
  - `feature_desc`
- 连续相同的 `type` 合并为第一列大单元格，连续相同的 `type_desc` 合并为第二列大单元格。
- `feature_rows_per_image` 控制每张图的行数。不设置时只出一张长图，A4 版心放不下；超过 12 行必须分块，建议 8–12 行。第 2 张起标题自动加“（续）”。

## Reading Rows From XLSX

功能清单 xlsx 常见结构：A 列使用端、B 列一级分类、C 列模块名称、D 列功能描述，A/B 列用合并单元格。取行时对 A、B 列做向下填充，再整理成 `feature_rows`：

```python
import openpyxl

ws = openpyxl.load_workbook(path)["功能清单"]
rows, cur_type, cur_desc = [], "", ""
for r in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True):
    if r[0]: cur_type = str(r[0]).strip()
    if r[1]: cur_desc = str(r[1]).strip()
    if not r[2]: continue
    rows.append({"type": cur_type, "type_desc": cur_desc,
                 "module_name": str(r[2]).strip(), "feature_desc": str(r[3]).strip()})
```

不要直接把 xlsx 转 PDF 再截图：默认打印版式会把 A–C 列和 D 列拆到不同页，合同里无法使用。

## Template Mapping Rules

当前脚本按段落前缀匹配并替换这类段落：

- `合同编号：`
- `签约时间：`
- `1.1  本合同的甲方（委托方）：`
- `联系人：`
- `联系电话：`
- `公司地址：`
- `固话号码：`
- `银行开户行及账号：`
- `2.1甲方委托乙方进行开发软件：`
- `{{image:需求清单}}`
- `2.2.1一年免费服务期到期后`
- `3.1 本合同软件开发费用总额为：`
- `2）甲方确认原型图（或功能需求清单）的次日算`
- `合同签订后3天内，甲方应向乙方一次性支付全额开发费用`
- `甲方指定联系人：`
- `乙方指定联系人：`

如果模板明显存在甲乙方联系人/邮箱错位，允许脚本按合同语义修正。
