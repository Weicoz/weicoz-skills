#!/usr/bin/env python3
"""本地 UI 原型与验收工具。无模型调用；像素比较按需使用 Pillow。"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import quote, urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = {"browser", "os", "fonts", "dpr", "zoom", "reduced_motion"}


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("清单顶层必须为对象")
    return value


def write_json(path, value, force=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 排他创建保护已有文件；显式覆盖只针对文件，不删除目录。
    with path.open("w" if force else "x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def local_candidate(value, base):
    raw = base / value
    path = raw.resolve()
    if not inside(path, base) or not path.is_file():
        raise ValueError(f"候选必须是清单目录内的真实文件：{value}")
    if any(part.is_symlink() for part in [raw, *raw.parents] if inside(part, base)):
        raise ValueError("候选路径不得经过软链")
    if path.suffix.lower() not in {".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        raise ValueError("候选仅支持 HTML 或图片")
    if path.suffix.lower() in {".html", ".htm"} and path.parent == base:
        raise ValueError("本地 HTML 放在各自子目录，防止复制无关数据")
    tree = path.parent if path.suffix.lower() in {".html", ".htm"} else path
    if tree.is_dir() and any(p.is_symlink() for p in tree.rglob("*")):
        raise ValueError("候选资源树含软链，请先导出独立资源目录")
    return path, tree


def compare(manifest, output):
    manifest = Path(manifest).resolve()
    spec = read_json(manifest)
    entries = spec.get("candidates", [])
    if not isinstance(entries, list) or not entries:
        raise ValueError("candidates 必须是非空数组")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("对比页输出目录已存在；请选择新目录")
    prepared = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise ValueError("每个候选必须有非空 name")
        if ("path" in entry) == ("url" in entry):
            raise ValueError("每个候选恰好提供 path 或 url")
        if "url" in entry:
            address = urlsplit(entry["url"])
            if address.scheme not in {"http", "https"} or not address.hostname or address.username or address.password:
                raise ValueError("外部地址必须是无凭据的 HTTP(S) URL")
            prepared.append((entry, None, None))
        else:
            path, tree = local_candidate(entry["path"], manifest.parent)
            if inside(output, tree) or inside(tree, output):
                raise ValueError("输出目录不得与候选资源树重叠")
            prepared.append((entry, path, tree))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui-compare-", dir=output.parent) as temp:
        stage = Path(temp) / "result"
        stage.mkdir()
        rows = []
        for i, (entry, path, tree) in enumerate(prepared):
            if tree:
                dest = stage / f"candidate-{i + 1}"
                if tree.is_dir():
                    shutil.copytree(tree, dest, ignore=shutil.ignore_patterns(".*", "node_modules"))
                else:
                    dest.mkdir()
                    shutil.copy2(tree, dest / tree.name)
                url = f"candidate-{i + 1}/{quote(path.name, safe='')}"
            else:
                url = entry["url"]
            esc = lambda text: html.escape(str(text), quote=True)
            image = path and path.suffix.lower() not in {".html", ".htm"}
            preview = f'<img src="{esc(url)}" alt="{esc(entry["name"])}">' if image else f'<iframe sandbox="allow-scripts allow-same-origin allow-forms" src="{esc(url)}" title="{esc(entry["name"])}" loading="lazy"></iframe>'
            rows.append(f'<article><h2>{esc(entry["name"])}</h2><p>{esc(entry.get("note", ""))}</p><div class="preview">{preview}</div><div class="actions"><button class="choose" data-name="{esc(entry["name"])}">选择此方向</button><a target="_blank" rel="noopener" href="{esc(url)}">全尺寸打开</a></div></article>')
        template = (ROOT / "assets/compare.html").read_text(encoding="utf-8")
        (stage / "index.html").write_text(template.replace("{{title}}", html.escape(str(spec.get("title", "设计方向")))).replace("{{rows}}", "\n".join(rows)), encoding="utf-8")
        for name in ["compare.css", "compare.js"]:
            shutil.copy2(ROOT / "assets" / name, stage / name)
        stage.rename(output)
    return {"page": str(output / "index.html"), "candidates": len(entries)}


def environment_valid(value):
    return (isinstance(value, dict) and ENV_KEYS <= value.keys()
            and all(isinstance(value[k], str) and value[k].strip() for k in ["browser", "os", "fonts"])
            and all(type(value[k]) in (int, float) and math.isfinite(value[k]) and value[k] > 0 for k in ["dpr", "zoom"])
            and type(value["reduced_motion"]) is bool)


def sheet(manifest, output):
    from PIL import Image, ImageDraw, ImageOps
    manifest = Path(manifest).resolve()
    entries = read_json(manifest).get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("sources 必须为非空数组")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("素材输出目录已存在；请选择新目录")
    images, notes = [], ["# 素材来源", "", "编号对应 sheet.png。usage 为 check/reference 的素材不能直接作为发布许可。", ""]
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or entry.get("usage") not in {"page", "check", "reference"}:
            raise ValueError("每项素材必须声明 usage：page/check/reference")
        if not all(isinstance(entry.get(key), str) and entry[key].strip() for key in ["title", "license", "source_url"]):
            raise ValueError("每项必须有 title、license 和 source_url；未知许可标 unknown")
        if entry["usage"] == "page" and entry["license"].lower() == "unknown":
            raise ValueError("未知许可不能声明 page 使用")
        if ("path" in entry) == ("url" in entry):
            raise ValueError("素材恰好提供 path 或 url")
        if "url" in entry:
            address = urlsplit(entry["url"])
            if address.scheme not in {"http", "https"} or not address.hostname or address.username or address.password:
                raise ValueError("素材地址必须为无凭据 HTTP(S) URL")
            import io
            with urllib.request.urlopen(entry["url"], timeout=20) as response:
                data = response.read(20_000_001)
            if len(data) > 20_000_000:
                raise ValueError("单个素材超过 20 MB；请先手动导出小图")
            source = io.BytesIO(data)
        else:
            source = (manifest.parent / entry["path"]).resolve()
            if not source.is_relative_to(manifest.parent):
                raise ValueError("本地素材必须在清单目录内")
        with Image.open(source) as image:
            image.load()
            original_size = image.size
            image = ImageOps.exif_transpose(image).convert("RGBA")
            images.append(image.copy())
        notes.extend([f"## {index:02d} {entry['title']}", f"- 来源：{entry['source_url']}", f"- 许可：{entry['license']}", f"- 用途：{entry['usage']}", f"- 原尺寸：{original_size[0]} × {original_size[1]}", ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui-media-", dir=output.parent) as temp:
        stage = Path(temp) / "result"
        stage.mkdir()
        canvas = Image.new("RGB", (900, 230 * math.ceil(len(images) / 3)), "#f2f0e9")
        draw = ImageDraw.Draw(canvas)
        for index, image in enumerate(images):
            image.save(stage / f"asset-{index + 1:02d}.png")
            thumb = ImageOps.contain(image, (280, 190))
            x, y = index % 3 * 300 + 10, index // 3 * 230 + 10
            canvas.paste(thumb, (x + (280 - thumb.width) // 2, y), thumb)
            draw.text((x, y + 195), f"{index + 1:02d} / {image.width} x {image.height}", fill="#252823")
        canvas.save(stage / "sheet.png")
        (stage / "SOURCES.md").write_text("\n".join(notes), encoding="utf-8")
        stage.rename(output)
    return {"sheet": str(output / "sheet.png"), "assets": len(images), "sources": str(output / "SOURCES.md")}


def parity(manifest):
    from PIL import Image, ImageChops
    manifest = Path(manifest).resolve()
    spec = read_json(manifest)
    expected = spec.get("expected_states")
    cases = spec.get("cases")
    if (not isinstance(expected, list) or not expected or any(not isinstance(x, str) or not x for x in expected)
            or len(expected) != len(set(expected)) or not isinstance(cases, list)):
        raise ValueError("expected_states 必须为不重复的非空状态数组，cases 必须为数组")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    coverage = len(ids) == len(cases) == len(expected) and len(set(ids)) == len(ids) and set(ids) == set(expected)
    source = spec.get("reference_source")
    provenance = spec.get("scope") in {"self-regression", "authorized-reference"} and isinstance(source, str) and bool(source.strip())
    results = []
    for case in cases:
        if not isinstance(case, dict):
            results.append({"id": None, "passed": False, "error": "case 必须为对象"})
            continue
        result = {"id": case.get("id"), "passed": False}
        try:
            reference_env, candidate_env = case.get("reference_environment"), case.get("candidate_environment")
            result["environment_match"] = environment_valid(reference_env) and environment_valid(candidate_env) and reference_env == candidate_env
            result["tasks_passed"] = case.get("reference_task_passed") is True and case.get("candidate_task_passed") is True
            paths = [manifest.parent / case[key] for key in ["reference", "candidate"]]
            result["sha256"] = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
            with Image.open(paths[0]) as a, Image.open(paths[1]) as b:
                a.load(); b.load()
                result["dimensions"] = [list(a.size), list(b.size)]
                if a.size != b.size:
                    result["error"] = "尺寸不同"
                else:
                    diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
                    maximum = diff.getchannel(0)
                    for channel in list(diff.split())[1:]:
                        maximum = ImageChops.lighter(maximum, channel)
                    result["different_pixels"] = a.width * a.height - maximum.histogram()[0]
                    result["passed"] = result["different_pixels"] == 0 and result["environment_match"] and result["tasks_passed"]
        except (OSError, KeyError, TypeError, ValueError) as error:
            result["error"] = str(error)
        results.append(result)
    return {"scope": spec.get("scope"), "reference_source": source, "coverage_complete": coverage,
            "provenance_declared": provenance, "pixel_tolerance": 0, "cases": results,
            "passed": bool(coverage and provenance and all(row["passed"] for row in results)),
            "limitation": "只验证声明的基线、状态与任务结果；来源和任务结果由调用方提供，不能自动证明清单穷尽或第三方原版等同。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["gallery", "compare", "sheet", "review", "parity"]:
        command = sub.add_parser(name)
        if name in {"compare", "sheet", "parity"}:
            command.add_argument("manifest", type=Path)
        command.add_argument("--output", type=Path, required=True)
        if name in {"review", "parity"}:
            command.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "gallery":
            shutil.copytree(ROOT / "assets/gallery", args.output)
            result = {"page": str(args.output / "index.html")}
        elif args.command == "compare":
            result = compare(args.manifest, args.output)
        elif args.command == "sheet":
            result = sheet(args.manifest, args.output)
        elif args.command == "review":
            result = {"design_contract": {}, "tasks": [], "evidence": [], "findings": [],
                      "dimensions": {key: {"score": None, "evidence": []} for key in ["方向", "层级", "排版", "素材", "交互", "动效", "一致性"]},
                      "reference_parity": "未验证", "task_acceptance": "未验证"}
            write_json(args.output, result, args.force)
        else:
            result = parity(args.manifest)
            write_json(args.output, result, args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "parity" and not result["passed"] else 0
    except ModuleNotFoundError as error:
        print(f"缺少依赖 {error.name}：像素比较使用 Pillow，请用已有环境或 uv run --with pillow 运行。", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError) as error:
        print(f"失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
