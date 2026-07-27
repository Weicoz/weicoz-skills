# Field Rules

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
- `feature_headers`
- `feature_rows`
- `feature_image_output`

## Business Rules

- 未提供的甲方字段留空。
- `principal_same_as_contact=true` 且 `principal_name` 为空时，自动把 `customer_contact` 复制给 `principal_name`。
- `price_after` 为空但提供了 `price_after_percent` 时，脚本按 `price * percent / 100` 自动计算。
- `price_zh` 为空时，脚本只对整数金额自动生成中文大写金额主体，例如 `7000 -> 柒仟`。
- 如果金额带小数，优先让用户显式提供 `price_zh`，避免模板尾部的 `圆整` 与真实金额冲突。

## Feature Image Rules

- 优先使用 `feature_image_path` 指向的原图。
- 如果没有原图但提供了 `feature_rows`，脚本会生成标准化功能清单图。
- `feature_rows` 的单行字段：
  - `type`
  - `type_desc`
  - `module_name`
  - `feature_desc`
- 连续相同的 `type` 会在图片里合并为第一列的大单元格。

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
