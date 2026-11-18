#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Mm
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont


DEFAULT_VENDOR_CONTACT = os.environ.get("WEICOZ_CONTRACT_VENDOR_CONTACT", "<乙方联系人>")
DEFAULT_VENDOR_EMAIL = os.environ.get("WEICOZ_CONTRACT_VENDOR_EMAIL", "<乙方邮箱>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill a custom contract DOCX template from JSON config.")
    parser.add_argument("--template", required=True, help="Absolute path to the source DOCX template.")
    parser.add_argument("--config", required=True, help="Absolute path to the JSON config file.")
    parser.add_argument("--output", required=True, help="Absolute path to the generated DOCX.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run post-generation checks (placeholder residue, empty brackets, image count) and fail on findings.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_decimal(value: Any) -> Decimal:
    text = to_text(value)
    if not text:
        return Decimal("0")
    return Decimal(text)


def money_text(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.quantize(Decimal("1")):
        return str(int(normalized))
    return format(normalized.normalize(), "f")


def integer_rmb_upper_body(amount: Decimal) -> str:
    if amount != amount.quantize(Decimal("1")):
        raise ValueError("Only integer amounts can be auto-converted to price_zh for this template.")

    digits = "零壹贰叁肆伍陆柒捌玖"
    small_units = ["仟", "佰", "拾", ""]
    big_units = ["", "万", "亿", "兆"]
    integer = int(amount)

    if integer == 0:
        return "零"

    def group_to_cn(group_value: int) -> str:
        chars: list[str] = []
        zero_pending = False
        divisors = [1000, 100, 10, 1]
        for divisor, unit in zip(divisors, small_units):
            digit = group_value // divisor % 10
            if digit:
                if zero_pending and chars:
                    chars.append("零")
                chars.append(digits[digit] + unit)
                zero_pending = False
            elif chars:
                zero_pending = True
        return "".join(chars)

    groups: list[int] = []
    while integer > 0:
        groups.append(integer % 10000)
        integer //= 10000

    result: list[str] = []
    need_zero = False
    for index in range(len(groups) - 1, -1, -1):
        group_value = groups[index]
        if group_value == 0:
            need_zero = True
            continue
        if result and (need_zero or group_value < 1000):
            result.append("零")
        result.append(group_to_cn(group_value))
        result.append(big_units[index])
        need_zero = False
    return "".join(result)


def apply_defaults(config: dict[str, Any]) -> dict[str, Any]:
    data = dict(config)
    data.setdefault("contract_no", "")
    data.setdefault("sign_year", "")
    data.setdefault("sign_month", "")
    data.setdefault("sign_day", "")
    data.setdefault("principal_name", "")
    data.setdefault("principal_same_as_contact", False)
    data.setdefault("customer_contact", "")
    data.setdefault("customer_phone", "")
    data.setdefault("customer_address", "")
    data.setdefault("customer_landline", "")
    data.setdefault("customer_bank", "")
    data.setdefault("customer_email", "")
    data.setdefault("project_title", "")
    data.setdefault("price", "")
    data.setdefault("price_zh", "")
    data.setdefault("price_after", "")
    data.setdefault("price_after_percent", "")
    data.setdefault("delivery_days", "")
    data.setdefault("vendor_contact", DEFAULT_VENDOR_CONTACT)
    data.setdefault("vendor_email", DEFAULT_VENDOR_EMAIL)
    data.setdefault("feature_title", "需求功能清单")
    data.setdefault("feature_headers", ["类型", "类型描述", "模块名称", "功能描述"])
    data.setdefault("feature_image_path", "")
    data.setdefault("feature_image_paths", [])
    data.setdefault("feature_rows", [])
    data.setdefault("feature_image_output", "")

    if data["principal_same_as_contact"] and not to_text(data["principal_name"]):
        data["principal_name"] = to_text(data["customer_contact"])

    price_text = to_text(data["price"])
    if price_text:
        price_value = to_decimal(price_text)
        if not to_text(data["price_after"]) and to_text(data["price_after_percent"]):
            percent_value = to_decimal(data["price_after_percent"])
            renewal_value = (price_value * percent_value / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            data["price_after"] = money_text(renewal_value)
        if not to_text(data["price_zh"]):
            data["price_zh"] = integer_rmb_upper_body(price_value)

    return data


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    content = to_text(text) or " "
    lines: list[str] = []
    current = ""
    for char in content:
        probe = current + char
        left, _, right, _ = draw.textbbox((0, 0), probe, font=font)
        if right - left <= max_width or not current:
            current = probe
            continue
        lines.append(current)
        current = char
    if current:
        lines.append(current)
    return lines


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    left, top, right, bottom = box
    tx0, ty0, tx1, ty1 = draw.textbbox((0, 0), to_text(text), font=font)
    x = left + (right - left - (tx1 - tx0)) / 2
    y = top + (bottom - top - (ty1 - ty0)) / 2
    draw.text((x, y), to_text(text), font=font, fill=fill)


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    padding_x: int = 20,
) -> None:
    left, top, right, bottom = box
    inner_left = left + padding_x
    inner_right = right - padding_x
    lines = wrap_text(draw, to_text(text), font, inner_right - inner_left)
    _, top0, _, bottom0 = draw.textbbox((0, 0), "测试", font=font)
    line_height = bottom0 - top0 + 12
    total_height = line_height * len(lines)
    start_y = top + (bottom - top - total_height) / 2
    for index, line in enumerate(lines):
        draw.text((inner_left, start_y + index * line_height), line, font=font, fill=fill)


def _normalize_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Fill 类型描述 down so merged-column sources (xlsx exports) render once per group."""
    normalized: list[dict[str, str]] = []
    current_desc = ""
    for row in rows:
        desc = to_text(row.get("type_desc"))
        if desc:
            current_desc = desc
        normalized.append(
            {
                "type": to_text(row.get("type")),
                "type_desc": current_desc,
                "module_name": to_text(row.get("module_name")),
                "feature_desc": to_text(row.get("feature_desc")),
            }
        )
    return normalized


def _group_runs(rows: list[dict[str, str]], key: str) -> list[tuple[int, int, str]]:
    runs: list[tuple[int, int, str]] = []
    start = 0
    for index in range(1, len(rows) + 1):
        if index == len(rows) or rows[index][key] != rows[start][key]:
            runs.append((start, index, rows[start][key]))
            start = index
    return runs


def _chunk_rows(rows: list[dict[str, str]], per_image: Any) -> list[list[dict[str, str]]]:
    try:
        size = int(to_text(per_image))
    except ValueError:
        size = 0
    if size <= 0 or size >= len(rows):
        return [rows]
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def render_feature_image(
    rows: list[dict[str, str]],
    title: str,
    image_path: Path,
    headers: list[str],
    width: int = 1600,
) -> Path:
    scale = width / 1600
    title_height = round(96 * scale)
    header_height = round(104 * scale)
    border = max(2, round(3 * scale))
    blue = "#A5B7E1"
    green_left = "#E6F4ED"
    green_right = "#BFE4D3"
    line = "#2E2E2E"
    text = "#111111"

    col_widths = [round(186 * scale), round(250 * scale), round(340 * scale)]
    col_widths.append(width - sum(col_widths))

    title_font = load_font(round(38 * scale))
    header_font = load_font(round(30 * scale))
    body_font = load_font(round(29 * scale))

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    row_heights: list[int] = []
    for row in rows:
        wrapped = wrap_text(probe, row["feature_desc"], body_font, col_widths[3] - 60)
        row_heights.append(max(round(120 * scale), round((42 * len(wrapped) + 40) * scale)))

    height = title_height + header_height + sum(row_heights) + border * 3
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    xs = [0]
    for column_width in col_widths:
        xs.append(xs[-1] + column_width)

    draw.rectangle((0, 0, width - 1, title_height), fill=blue, outline=line, width=border)
    draw_centered_text(draw, (0, 0, width, title_height), title, title_font, text)

    draw.rectangle((0, title_height, width - 1, title_height + header_height), fill=blue, outline=line, width=border)
    for index, label in enumerate(headers):
        draw.rectangle((xs[index], title_height, xs[index + 1], title_height + header_height), outline=line, width=border)
        draw_centered_text(
            draw, (xs[index], title_height, xs[index + 1], title_height + header_height), label, header_font, text
        )

    tops: list[int] = []
    y = title_height + header_height
    for row_height in row_heights:
        tops.append(y)
        y += row_height
    body_bottom = y

    for index, row in enumerate(rows):
        top = tops[index]
        bottom = top + row_heights[index]
        draw.rectangle((xs[2], top, xs[3], bottom), fill=green_left, outline=line, width=border)
        draw.rectangle((xs[3], top, xs[4], bottom), fill=green_right, outline=line, width=border)
        draw_centered_text(draw, (xs[2], top, xs[3], bottom), row["module_name"], header_font, text)
        draw_wrapped_text(draw, (xs[3], top, xs[4], bottom), row["feature_desc"], body_font, text, round(30 * scale))

    for column_index, key in ((0, "type"), (1, "type_desc")):
        for start, stop, label in _group_runs(rows, key):
            top = tops[start]
            bottom = tops[stop - 1] + row_heights[stop - 1]
            draw.rectangle((xs[column_index], top, xs[column_index + 1], bottom), fill=green_left, outline=line, width=border)
            draw_centered_text(draw, (xs[column_index], top, xs[column_index + 1], bottom), label, header_font, text)

    draw.rectangle((0, 0, width - 1, body_bottom), outline=line, width=border)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path)
    return image_path


def build_feature_images(config: dict[str, Any], output_docx: Path) -> list[Path]:
    image_paths: list[Path] = []
    paths_raw = config.get("feature_image_paths") or []
    if isinstance(paths_raw, str):
        paths_raw = [paths_raw]
    for raw in paths_raw:
        if to_text(raw):
            image_paths.append(Path(to_text(raw)).expanduser().resolve())
    source_image = to_text(config.get("feature_image_path"))
    if source_image and not image_paths:
        image_paths.append(Path(source_image).expanduser().resolve())

    for path in image_paths:
        if not path.exists():
            raise FileNotFoundError(f"feature image does not exist: {path}")
    if image_paths:
        return image_paths

    rows = _normalize_feature_rows(config.get("feature_rows") or [])
    if not rows:
        raise ValueError("Provide feature_image_path or feature_rows in the contract config.")

    chunks = _chunk_rows(rows, config.get("feature_rows_per_image"))
    headers = config.get("feature_headers") or ["类型", "类型描述", "模块名称", "功能描述"]
    title = to_text(config.get("feature_title")) or "需求功能清单"
    width_raw = to_text(config.get("feature_image_width"))
    width = int(width_raw) if width_raw.isdigit() and int(width_raw) >= 1200 else 1600

    feature_output = to_text(config.get("feature_image_output"))
    generated: list[Path] = []
    for index, chunk in enumerate(chunks):
        suffix = "" if len(chunks) == 1 else f"-{index + 1:02d}"
        chunk_title = title if index == 0 else f"{title}（续）"
        if feature_output:
            base = Path(feature_output).expanduser().resolve()
            image_path = base.with_name(f"{base.stem}{suffix}{base.suffix}")
        else:
            image_path = output_docx.with_name(f"{output_docx.stem}-功能清单{suffix}.png")
        generated.append(render_feature_image(chunk, chunk_title, image_path, headers, width))
    return generated


def replace_paragraph(paragraph, text: str) -> None:
    paragraph.text = text


def maybe_fill_contact_detail(paragraph, config: dict[str, Any], paragraph_text: str, in_party_a: bool) -> bool:
    if not in_party_a:
        return False
    stripped = paragraph_text.lstrip()
    if stripped.startswith("联系人："):
        replace_paragraph(paragraph, f"     联系人：{to_text(config['customer_contact'])}")
        return True
    if stripped.startswith("联系电话："):
        replace_paragraph(paragraph, f"     联系电话：{to_text(config['customer_phone'])}")
        return True
    if stripped.startswith("公司地址："):
        replace_paragraph(paragraph, f"     公司地址：{to_text(config['customer_address'])}")
        return True
    if stripped.startswith("固话号码："):
        replace_paragraph(paragraph, f"     固话号码：{to_text(config['customer_landline'])}")
        return True
    if stripped.startswith("银行开户行及账号："):
        replace_paragraph(paragraph, f"     银行开户行及账号：{to_text(config['customer_bank'])}")
        return True
    return False


def fill_contract(template: Path, config: dict[str, Any], output_docx: Path, feature_image_paths: list[Path]) -> Path:
    doc = Document(str(template))
    image_inserted = False
    in_party_a = False

    for paragraph in doc.paragraphs:
        raw = paragraph.text or ""
        stripped = raw.strip()

        if stripped.startswith("合同编号："):
            replace_paragraph(paragraph, f"合同编号：{to_text(config['contract_no'])}")
            continue

        if stripped.startswith("签约时间："):
            replace_paragraph(
                paragraph,
                f"签约时间：{to_text(config['sign_year'])} 年 {to_text(config['sign_month'])} 月 {to_text(config['sign_day'])} 日",
            )
            continue

        if stripped.startswith("1.1") and "甲方（委托方）" in stripped:
            in_party_a = True
            replace_paragraph(paragraph, f"1.1  本合同的甲方（委托方）：{to_text(config['principal_name'])}")
            continue

        if stripped.startswith("1.2") and "乙方（受托方）" in stripped:
            in_party_a = False
            continue

        if maybe_fill_contact_detail(paragraph, config, raw, in_party_a):
            continue

        if stripped.startswith("2.1甲方委托乙方进行开发软件：") or "{{title:功能名称}}" in raw:
            replace_paragraph(
                paragraph,
                f"2.1甲方委托乙方进行开发软件：【{to_text(config['project_title'])}】，具体定制项目需求清单由甲方设计及提供，乙方根据甲方提供的需求进行技术开发，需求清单如下图：",
            )
            continue

        if "{{image:需求清单}}" in raw:
            replace_paragraph(paragraph, "")
            section = doc.sections[0]
            available_width = section.page_width - section.left_margin - section.right_margin
            anchor = paragraph
            for index, image_path in enumerate(feature_image_paths):
                if index:
                    picture_paragraph = Paragraph(OxmlElement("w:p"), anchor._parent)
                    anchor._p.addnext(picture_paragraph._p)
                    anchor = picture_paragraph
                anchor.alignment = WD_ALIGN_PARAGRAPH.CENTER
                anchor.add_run().add_picture(str(image_path), width=available_width - Mm(6))
            image_inserted = True
            continue

        if stripped.startswith("2.2.1一年免费服务期到期后"):
            replace_paragraph(
                paragraph,
                f"2.2.1一年免费服务期到期后，甲方应另外按照【{to_text(config['price_after'])}】元/年的标准续费,售后技术支持服务生效，双方另行按照该标准签订续费合同。",
            )
            continue

        if stripped.startswith("3.1 本合同软件开发费用总额为："):
            replace_paragraph(
                paragraph,
                f"3.1 本合同软件开发费用总额为：￥【{to_text(config['price'])}】元（人民币大写：【{to_text(config['price_zh'])}】圆整）。",
            )
            continue

        if stripped.startswith("2）甲方确认原型图（或功能需求清单）的次日算"):
            replace_paragraph(
                paragraph,
                f"2）甲方确认原型图（或功能需求清单）的次日算，暂计在【{to_text(config['delivery_days'])}】个工作日完成整个项目发布（如甲方另外增加需求除外），乙方应向甲方指定邮箱发送《项目发布通知》，甲方收到《通知》后应积极提供相关服务器信息进行软件部署。",
            )
            continue

        if stripped.startswith("合同签订后3天内，甲方应向乙方一次性支付全额开发费用"):
            replace_paragraph(
                paragraph,
                f"合同签订后3天内，甲方应向乙方一次性支付全额开发费用，即人民币 ￥【{to_text(config['price'])}】元（人民币大写：【{to_text(config['price_zh'])}】圆整）。",
            )
            continue

        if stripped.startswith("甲方指定联系人："):
            contact = to_text(config["customer_contact"])
            email = to_text(config["customer_email"])
            if contact or email:
                replace_paragraph(
                    paragraph,
                    f"甲方指定联系人：【{contact}】，指定联系邮箱：【{email}】；",
                )
            else:
                replace_paragraph(
                    paragraph,
                    "甲方指定联系人：【\u3000\u3000\u3000\u3000\u3000\u3000】，"
                    "指定联系邮箱：【\u3000\u3000\u3000\u3000\u3000\u3000\u3000\u3000】；",
                )
            continue

        if stripped.startswith("乙方指定联系人："):
            vendor_contact = to_text(config["vendor_contact"])
            vendor_email = to_text(config["vendor_email"])
            if vendor_contact or vendor_email:
                replace_paragraph(
                    paragraph,
                    f"乙方指定联系人：【{vendor_contact}】，指定联系邮箱：【{vendor_email}】。",
                )
            continue

    if not image_inserted:
        raise ValueError("Did not find the feature image placeholder in the template.")
    if not feature_image_paths:
        raise ValueError("No feature images were inserted.")

    for paragraph in doc.paragraphs:
        paragraph.paragraph_format.widow_control = True

    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return output_docx


def _all_paragraphs(doc):
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph


def check_output(docx_path: Path, expected_images: int) -> list[str]:
    doc = Document(str(docx_path))
    findings: list[str] = []

    for paragraph in _all_paragraphs(doc):
        content = paragraph.text
        if "{{" in content or "}}" in content:
            findings.append(f"placeholder residue: {content.strip()[:60]}")
        if "【】" in content or "【 】" in content:
            findings.append(f"empty bracket: {content.strip()[:60]}")

    actual_images = len(doc.inline_shapes)
    if expected_images and actual_images != expected_images:
        findings.append(f"image count {actual_images} != expected {expected_images}")
    if actual_images == 0:
        findings.append("no inline images found")
    return findings


def main() -> None:
    args = parse_args()
    template = Path(args.template).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    output_docx = Path(args.output).expanduser().resolve()

    if not template.exists():
        raise FileNotFoundError(f"Template not found: {template}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    config = apply_defaults(read_json(config_path))
    feature_image_paths = build_feature_images(config, output_docx)
    generated_docx = fill_contract(template, config, output_docx, feature_image_paths)

    print(f"Generated DOCX: {generated_docx}")
    for path in feature_image_paths:
        print(f"Feature image: {path}")

    if args.check:
        findings = check_output(generated_docx, len(feature_image_paths))
        if findings:
            print("CHECK FAILED:")
            for item in findings:
                print(f"  - {item}")
            raise SystemExit(1)
        print(f"CHECK PASSED: {len(feature_image_paths)} image(s), no placeholder residue, no empty brackets")


if __name__ == "__main__":
    main()
