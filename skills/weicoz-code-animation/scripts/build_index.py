#!/usr/bin/env python3
"""从 references/library 重建 index.json 与 CATALOG.md。

用法（在 skill 根目录执行）：
    python3 scripts/build_index.py           # 重建两个派生文件
    python3 scripts/build_index.py --check   # 只校验，不写入；不一致退出码 1

数据源：references/library/风格提示词/**/*.md（正文唯一来源）
        references/library/风格挑选.html（只取类别顺序与说明，缺失时按目录名排序）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "references" / "library"
STYLES = LIB / "风格提示词"
INDEX = ROOT / "references" / "index.json"
CATALOG = ROOT / "references" / "CATALOG.md"
PICKER = LIB / "风格挑选.html"

BULLET = re.compile(r"^- ([^：:]{1,8})[：:]\s*(.*)$")
H2 = re.compile(r"^##\s+(.+?)\s*$", re.M)
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
EN_PAREN = re.compile(r"[（(]\s*([^（）()]*[A-Za-z][^（）()]*?)\s*[）)]\s*$")
FENCE = re.compile(r"```.*?```", re.S)
CODE_DEF = re.compile(r"\bS\.[A-Za-z0-9_]+\s*=")      # 真正定义了 S.XX 风格函数
JS_FENCE = re.compile(r"```js\b")
ENGINE_REF = re.compile(r"from\s+['\"]\./|engine/")
HELPER_GLOBALS = ("PARENT", "SERIF", "KNIFE", "DAB")

DESC_MAX = 60


def series_key(dir_name: str) -> str:
    """A-G_代码样片 -> AG；L_Lemo-Opuscar -> L。"""
    head = dir_name.split("_", 1)[0]
    return head.replace("-", "").upper()


def series_label(dir_name: str) -> str:
    if "_" not in dir_name:
        return dir_name
    head, tail = dir_name.split("_", 1)
    return f"{head.replace('-', '–')} {tail}"


def picker_meta() -> list[dict]:
    """从挑选页内嵌 JSON 取类别顺序与说明；失败时返回空表。"""
    if not PICKER.exists():
        return []
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        PICKER.read_text(encoding="utf-8"),
        re.S,
    )
    if not m:
        return []
    try:
        return json.loads(m.group(1)).get("meta", []) or []
    except json.JSONDecodeError:
        return []


def picker_entries() -> list[dict]:
    if not PICKER.exists():
        return []
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        PICKER.read_text(encoding="utf-8"),
        re.S,
    )
    if not m:
        return []
    try:
        return json.loads(m.group(1)).get("entries", []) or []
    except json.JSONDecodeError:
        return []


def parse_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("# ") else ""

    sid, _, rest = title.partition(" ")
    sid = sid.strip()
    name = rest.strip()
    name_en = ""
    en = EN_PAREN.search(name)
    if en and not CJK.search(en.group(1)):     # 只剥离纯拉丁的英文名括注，中文括注保留
        name_en = en.group(1).strip()
        name = EN_PAREN.sub("", name).strip()

    fields: dict[str, str] = {}
    for line in lines[:14]:
        m = BULLET.match(line.strip())
        if m:
            fields.setdefault(m.group(1).strip(), m.group(2).strip())

    body = text.split("## 风格提示词", 1)[1] if "## 风格提示词" in text else ""
    prompt_body = body.split("\n## ", 1)[0].strip()
    prose = FENCE.sub("", prompt_body)  # 语言比例只看正文，排除代码块
    cjk = len(CJK.findall(prose))
    latin = len(LATIN.findall(prose))
    ratio = cjk / (cjk + latin) if cjk + latin else 0.0

    still = path.with_suffix(".jpg")
    return {
        "id": sid,
        "name": name,
        "name_en": name_en,
        "cat": fields.get("分类", ""),
        "desc": fields.get("长什么样", "") or fields.get("风格", ""),
        "fit": fields.get("适合", ""),
        "tags": [t for t in re.split(r"[、,，]", fields.get("关键词", "")) if t.strip()],
        "year": fields.get("年份", ""),
        "file": str(path.relative_to(LIB)).replace("\\", "/"),
        "still": str(still.relative_to(LIB)).replace("\\", "/") if still.exists() else "",
        "has_snippet": bool(JS_FENCE.search(text)),
        "has_code": bool(CODE_DEF.search(text)),
        "code_kind": ("incremental" if "s.lt" in text else "pure") if CODE_DEF.search(text) else "",
        # 正文引用了外部 engine / 相对模块（与是否含 S.XX 无关，L20 就属于“有示例但依赖缺失”）
        "needs_engine": bool(ENGINE_REF.search(text)),
        "helper_globals": [g for g in HELPER_GLOBALS if g in text],
        "prompt_chars": len(prompt_body),
        "cjk_ratio": round(ratio, 2),
        "lang": "en" if ratio < 0.05 else ("mixed" if ratio < 0.2 else "zh"),
        "empty": prompt_body == "",
        "sections": [s.strip() for s in H2.findall(text)],
    }


def build() -> dict:
    if not STYLES.is_dir():
        sys.exit(f"缺少风格库目录：{STYLES}")

    files = sorted(STYLES.rglob("*.md"))
    if not files:
        sys.exit(f"风格库为空：{STYLES}")

    by_series: dict[str, list[dict]] = {}
    labels: dict[str, str] = {}
    for path in files:
        dir_name = path.parent.name
        key = series_key(dir_name)
        labels.setdefault(key, series_label(dir_name))
        item = parse_md(path)
        item["series"] = key
        item["series_label"] = labels[key]
        by_series.setdefault(key, []).append(item)

    picker_fit = {e.get("id"): (e.get("fit") or "").strip() for e in picker_entries()}
    for items in by_series.values():
        for item in items:
            if not item["fit"] and picker_fit.get(item["id"]):
                item["fit"] = picker_fit[item["id"]]
                item["fit_from_picker"] = True

    meta = picker_meta()
    order = [m["id"] for m in meta if m.get("id") in by_series]
    notes = {m["id"]: m.get("note", "") for m in meta}
    order += [k for k in sorted(by_series) if k not in order]

    styles: list[dict] = []
    series_out: list[dict] = []
    for key in order:
        items = sorted(by_series[key], key=lambda x: natural_id(x["id"]))
        styles.extend(items)
        series_out.append(
            {
                "id": key,
                "label": labels[key],
                "note": notes.get(key, ""),
                "count": len(items),
                "usable": sum(1 for x in items if not x["empty"]),
                "with_still": sum(1 for x in items if x["still"]),
                "with_code": sum(1 for x in items if x["has_code"]),
                "with_snippet": sum(1 for x in items if x["has_snippet"]),
            }
        )

    seen: dict[str, int] = {}
    for item in styles:
        seen[item["id"]] = seen.get(item["id"], 0) + 1
    dups = sorted(k for k, v in seen.items() if v > 1)
    if dups:
        sys.exit(f"重复的风格 ID：{'、'.join(dups)}。每个 ID 必须唯一。")

    usable = [x for x in styles if not x["empty"]]
    return {
        "meta": {
            "generated_by": "scripts/build_index.py",
            "source": "references/library/风格提示词/**/*.md",
            "total": len(styles),
            "usable": len(usable),
            "empty": len(styles) - len(usable),
            "with_still": sum(1 for x in styles if x["still"]),
            "with_code": sum(1 for x in styles if x["has_code"]),
            "with_snippet": sum(1 for x in styles if x["has_snippet"]),
            "incremental": sum(1 for x in styles if x["code_kind"] == "incremental"),
            "needs_engine": sum(1 for x in styles if x["needs_engine"]),
            "series": series_out,
        },
        "styles": styles,
    }


def natural_id(sid: str) -> tuple:
    m = re.match(r"([A-Za-z]+)(\d+)", sid)
    return (m.group(1), int(m.group(2))) if m else (sid, 0)


def render_catalog(index: dict) -> str:
    meta = index["meta"]
    out = [
        "# 风格总目录",
        "",
        "> 由 `scripts/build_index.py` 从 `references/library/风格提示词/**/*.md` 生成，请勿手改。",
        f"> 共 {meta['total']} 条，可用 {meta['usable']} 条，"
        f"带静帧 {meta['with_still']} 条，带参考实现 {meta['with_code']} 条。",
    ]
    if meta["empty"]:
        empties = "、".join(x["id"] for x in index["styles"] if x["empty"])
        out.append(
            f"> 其中 {meta['empty']} 条为原素材未附内容的空白占位（{empties}），"
            "保留占位以免日后补写时编号错乱。"
        )
    out += [
        "",
        "字段：`代码` 的 `✓`=含可直接粘贴的 `S.XX` 风格函数，`△`=只有片段或示例"
        "（需自备依赖，如 L20 依赖库内没有的 `engine/`）；`静帧`=有同名 jpg 可预览。",
        "",
    ]
    by_series: dict[str, list[dict]] = {}
    for item in index["styles"]:
        by_series.setdefault(item["series"], []).append(item)

    for s in meta["series"]:
        key = s["id"]
        items = by_series.get(key, [])
        out.append(f"## {s['label']}（{s['count']} 条）")
        out.append("")
        if s["note"]:
            out.append(s["note"])
            out.append("")
        out.append("| ID | 名称 | 一句话 | 标签 | 代码 | 静帧 |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for it in items:
            name = it["name"] or "（空条目·待补）"
            desc = it["desc"].replace("|", "／")
            if len(desc) > DESC_MAX:
                desc = desc[:DESC_MAX] + "…"
            tags = "·".join(it["tags"][:4])
            out.append(
                f"| {it['id']} | {name} | {desc or '—'} | {tags or '—'} | "
                f"{'✓' if it['has_code'] else ('△' if it['has_snippet'] else '')} | "
                f"{'✓' if it['still'] else ''} |"
            )
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def check(index: dict, catalog: str) -> int:
    problems: list[str] = []

    if not INDEX.exists():
        problems.append(f"缺少 {INDEX.relative_to(ROOT)}")
    else:
        on_disk = json.loads(INDEX.read_text(encoding="utf-8"))
        if on_disk != index:
            problems.append(f"{INDEX.relative_to(ROOT)} 与库不一致，需重新生成")

    if not CATALOG.exists():
        problems.append(f"缺少 {CATALOG.relative_to(ROOT)}")
    elif CATALOG.read_text(encoding="utf-8") != catalog:
        problems.append(f"{CATALOG.relative_to(ROOT)} 与库不一致，需重新生成")

    missing_md = [x["file"] for x in index["styles"] if not (LIB / x["file"]).exists()]
    if missing_md:
        problems.append(f"正文缺失 {len(missing_md)} 个：{missing_md[:3]}")

    broken_still = [x["still"] for x in index["styles"] if x["still"] and not (LIB / x["still"]).exists()]
    if broken_still:
        problems.append(f"静帧路径失效 {len(broken_still)} 个：{broken_still[:3]}")

    empty = [x["id"] for x in index["styles"] if x["empty"]]
    if empty:
        print(f"提示：{len(empty)} 条空白条目（无名称无提示词）：{'、'.join(empty)}", file=sys.stderr)

    ids = [x["id"] for x in index["styles"]]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        problems.append(f"重复 ID：{'、'.join(dups)}")

    declared_still = [x["still"] for x in index["styles"] if x["still"]]
    if len(declared_still) != index["meta"]["with_still"]:
        problems.append("静帧统计与条目不一致，需重新生成")

    entries = picker_entries()
    missing_img = [
        e.get("img") for e in entries
        if e.get("img") and not (LIB / e["img"]).exists()
    ]
    if missing_img:
        problems.append(f"挑选页声明的静帧文件缺失 {len(missing_img)} 个：{missing_img[:3]}")

    if entries:
        a = {x["id"] for x in index["styles"]}
        b = {x.get("id") for x in entries}
        if a != b:
            only_md = sorted(a - b)
            only_picker = sorted(b - a)
            problems.append(f"挑选页与正文 ID 不一致：正文独有 {only_md[:5]}，挑选页独有 {only_picker[:5]}")

        by_id = {x["id"]: x for x in index["styles"]}
        drift = []
        for e in entries:
            item = by_id.get(e.get("id"))
            if not item:
                continue
            for field in ("name", "fit"):
                want = (e.get(field) or "").strip()
                got = (item.get(field) or "").strip()
                if want and want != got and not (field == "fit" and item.get("fit_from_picker")):
                    drift.append(f"{item['id']}.{field}: 正文「{got}」vs 挑选页「{want}」")
        if drift:
            print(f"提示：索引与挑选页有 {len(drift)} 处字段差异（不影响 --check 结论）：", file=sys.stderr)
            for d in drift[:6]:
                print(f"  - {d}", file=sys.stderr)

    if problems:
        print("CHECK FAILED", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    m = index["meta"]
    print(
        f"CHECK OK — {m['total']} 条（可用 {m['usable']}，静帧 {m['with_still']}，"
        f"参考实现 {m['with_code']}），{len(m['series'])} 个类别"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="重建或校验风格索引")
    ap.add_argument("--check", action="store_true", help="只校验，不写入")
    args = ap.parse_args()

    index = build()
    catalog = render_catalog(index)

    if args.check:
        return check(index, catalog)

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CATALOG.write_text(catalog, encoding="utf-8")

    m = index["meta"]
    print(
        f"已写入 {INDEX.relative_to(ROOT)} 与 {CATALOG.relative_to(ROOT)}："
        f"{m['total']} 条（可用 {m['usable']}，静帧 {m['with_still']}，参考实现 {m['with_code']}）"
    )
    empty = [x["id"] for x in index["styles"] if x["empty"]]
    if empty:
        print(f"其中 {len(empty)} 条为空白条目：{'、'.join(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
