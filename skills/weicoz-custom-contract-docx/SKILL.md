---
name: weicoz-custom-contract-docx
description: "基于现有 .docx 合同模板、客户信息、金额规则和功能清单图片或行数据，生成定制开发合同并完成渲染验收。Use when Codex needs to 读取并填写软件定制或功能定制合同模板、先输出预想内容给用户核对、插入功能清单图片、按总价和续费比例计算金额字段，或交付最终合同 .docx。"
---

# Custom Contract Docx

先给用户一版预想内容，再生成正式合同。不要跳过渲染验收。

## Workflow

1. 读取合同模板，识别待填字段、金额位、联系人位、工期位、需求清单图片占位。
2. 汇总用户已提供的信息，先输出一版“预想内容”给用户核对。只问最少的缺失信息。
3. 缺失的甲方信息保持留空，不要脑补。
4. 用户确认后，在 `${WEICOZ_OUTPUT_ROOT:-$PWD}` 写一份 JSON 配置文件。字段规则和示例见 `references/field-rules.md`。
5. 先调用 `load_workspace_dependencies`，再用返回的 Python 运行 `scripts/generate_contract.py`。
6. 用 documents skill 的 `render_docx.py --renderer artifact-tool` 渲染输出的 `.docx`，逐页检查后再交付。

## Required Rules

- 默认不新增“文字版需求摘要”。除非用户明确要求，否则只保留模板原有的项目名称和需求清单图片。
- `甲方（委托方）` 和 `联系人` 默认分开建模。只有用户明确说明两者相同，才同时填同一个值。
- 如果用户只给了续费比例，先算出绝对金额再写入合同。
- 如果模板里甲乙双方联系人、邮箱或类似字段明显错位，可按合同语义修正；不要顺手改无关条款。
- 如果用户只给了功能清单截图，优先复用截图；只有当截图不规整、难以排版，或用户改为提供行数据时，再生成标准化功能清单图片。
- 改动要保持手术式，只围绕合同填写、图片插入和必要的模板纠偏。

## Run Script

先写配置 JSON，再运行：

```bash
$PYTHON "$WEICOZ_SKILLS_ROOT/weicoz-custom-contract-docx/scripts/generate_contract.py" \
  --template /abs/path/template.docx \
  --config /abs/path/contract.json \
  --output /abs/path/output.docx
```

如果配置里提供 `feature_rows` 且没有 `feature_image_path`，脚本会在输出目录旁自动生成一张标准化功能清单图并插入合同。

## QA Gate

生成完成后，必须执行渲染验收：

```bash
$PYTHON "$WEICOZ_DOCUMENTS_RENDERER" \
  /abs/path/output.docx \
  --output_dir /abs/path/rendered \
  --renderer artifact-tool
```

逐页检查：

- 项目名称是否在括号内正常换行
- 金额、续费、工期是否断到方括号外
- 甲乙双方联系人和邮箱是否填到正确一侧
- 功能清单图片是否清晰、未溢出、未被截断

## Resources

- `references/field-rules.md`：配置字段、默认规则、金额规则、模板修正规则
- `scripts/generate_contract.py`：根据模板和 JSON 配置生成最终合同
