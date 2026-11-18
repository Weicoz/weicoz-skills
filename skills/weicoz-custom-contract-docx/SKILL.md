---
name: weicoz-custom-contract-docx
version: 1.1.0
description: "基于现有 .docx 合同模板、客户信息、金额规则和功能清单图片或行数据，生成定制开发合同并完成渲染验收。Use when 需要读取并填写软件定制或功能定制合同模板、先输出预想内容给用户核对、插入功能清单图片、按总价和续费比例计算金额字段，或交付最终合同 .docx。"
---

# Custom Contract Docx

先给用户一版预想内容，再生成正式合同。不要跳过渲染验收。

## Workflow

1. 读取仓库内模板 `assets/定制开发合同-通用模板.docx`，识别待填字段、金额位、联系人位、工期位、需求清单图片占位。
2. 汇总用户已提供的信息，先输出一版“预想内容”给用户核对。只问最少的缺失信息。
3. 缺失的甲方信息保持留空，不要脑补。
4. 用户确认后，在 `${WEICOZ_OUTPUT_ROOT:-$PWD}` 写一份 JSON 配置文件。字段规则和示例见 `references/field-rules.md`。
5. 用带 python-docx 的解释器运行 `scripts/generate_contract.py`（路径用 `$SKILL_DIR`，解析规则见 `references/field-rules.md`）。本机没有就建一个：`python3 -m venv /tmp/contract-env && /tmp/contract-env/bin/pip install python-docx pillow`。
6. 用 genoffice 渲染输出的 `.docx`，逐页检查后再交付。本机 LibreOffice 已失效，不再使用。

只给功能清单或截图页级信息、没有可排版行数据时，先确认能否直接复用截图。行数据可从 xlsx 读出，见 `references/field-rules.md`。

## Required Rules

- 默认不新增“文字版需求摘要”。除非用户明确要求，否则只保留模板原有的项目名称和需求清单图片。
- `甲方（委托方）` 和 `联系人` 默认分开建模。只有用户明确说明两者相同，才同时填同一个值。
- 如果用户只给了续费比例，先算出绝对金额再写入合同。用户完全没给续费信息时按 `references/field-rules.md` 的默认值处理并提示复核。
- 如果模板里甲乙双方联系人、邮箱或类似字段明显错位，可按合同语义修正；不要顺手改无关条款。
- 如果用户只给了功能清单截图，优先复用截图；只有当截图不规整、难以排版，或用户改为提供行数据时，再生成标准化功能清单图片。
- 改动要保持手术式，只围绕合同填写、图片插入和必要的模板纠偏。

## Run Script

先写配置 JSON，再运行：

```bash
# SKILL_DIR 解析顺序见 references/field-rules.md，L3 分层下不要用 $WEICOZ_SKILLS_ROOT
$PYTHON "$SKILL_DIR/scripts/generate_contract.py" \
  --template "$SKILL_DIR/assets/定制开发合同-通用模板.docx" \
  --config /abs/path/contract.json \
  --output /abs/path/output.docx \
  --check
```

`--check` 会在生成后自检占位符残留、`【】` 空方括号和图片数量，发现问题退出码 1。

图片支持三种输入，优先级依次为 `feature_image_paths` > `feature_image_path` > `feature_rows`：

- 有 `feature_rows` 且未指定图片时，脚本按 `feature_rows_per_image` 分块渲染标准化功能清单图，第 2 张起标题加“（续）”，连续相同 `type` / `type_desc` 合并成一格。
- 不分块会给出一张长图，A4 版心放不下。行数超过 12 时设置 `feature_rows_per_image`（建议 8–12）。
- 已有截图页时用 `feature_image_paths` 数组，按页顺序传入，脚本按满版心宽度逐张插入。

## QA Gate

生成完成后，必须执行渲染验收：

```bash
genoffice render /abs/path/output.docx --out /abs/path/rendered --json
```

读返回的 `detail.files` 得到逐页 PNG（约 596×842），逐页看图检查：

- 项目名称是否在括号内正常换行
- 金额、续费、工期是否断到方括号外
- 甲乙双方联系人和邮箱是否填到正确一侧
- 功能清单图片是否清晰、未溢出、未被截断
- 段落末行是否出现单个字或半句被切到下一页

genoffice 不可用时改用 `WEICOZ_DOCUMENTS_RENDERER` 指向的 Codex 渲染器。不要回退到 LibreOffice。

## Resources

- `references/field-rules.md`：配置字段、模板位置、默认规则、金额规则、xlsx 取行方法
- `assets/定制开发合同-通用模板.docx`：合同模板正本，随 skill 一起分发
- `scripts/generate_contract.py`：根据模板和 JSON 配置生成最终合同
