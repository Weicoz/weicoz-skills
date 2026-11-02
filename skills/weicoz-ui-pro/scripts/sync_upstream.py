#!/usr/bin/env python3
"""Synchronize and decouple weicoz-ui-pro from upstream oil-ui-pro.

This script pulls files from the local oil-ui-pro installation,
strips out account login, remote update check, and proprietary paid
image generation dependencies, and updates weicoz-ui-pro cleanly.
"""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import re
import shutil
import sys

# Relative to this script: skills/weicoz-ui-pro
SKILL_DIR = Path(__file__).resolve().parents[1]

# Files that must NEVER be synced (proprietary auth/billing/update)
EXCLUDED_REL_PATHS = {
    Path("scripts/check_update.py"),
    Path("scripts/check_update.sh"),
    Path("scripts/oiloil-image.mjs"),
    Path("tests/test_check_update.py"),
    Path("tests/test_oiloil_image.py"),
}

# Directories or patterns to ignore
IGNORED_NAMES = {".git", ".DS_Store", "__pycache__"}


def find_default_upstream() -> Path | None:
    env_path = os.environ.get("OIL_UI_PRO_UPSTREAM")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_dir():
            return p

    candidates = [
        Path.home() / ".claude" / "skills" / "oil-ui-pro",
        Path.home() / ".agents" / "skills" / "oil-ui-pro",
        Path.home() / ".cursor" / "skills" / "oil-ui-pro",
    ]
    for c in candidates:
        resolved = c.resolve()
        if resolved.is_dir() and (resolved / "SKILL.md").is_file():
            return resolved
    return None


def transform_skill_md(content: str) -> str:
    # 1. Update name and title
    content = re.sub(r"^name:\s*oil-ui-pro\b", "name: weicoz-ui-pro", content, flags=re.MULTILINE)
    content = re.sub(r"^#\s*oil-ui-pro\b", "# weicoz-ui-pro", content, flags=re.MULTILINE)

    # 2. Ensure top-level version field exists
    if not re.search(r"^version:\s*", content, flags=re.MULTILINE):
        ver_match = re.search(r'version:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?', content)
        ver = ver_match.group(1) if ver_match else "0.29.1"
        content = re.sub(r"^(name:\s*weicoz-ui-pro\n)", rf"\1version: {ver}\n", content, flags=re.MULTILINE)

    # 2. Strip check_update from allowed-tools
    # Look for allowed-tools block and filter out check_update lines
    def clean_allowed_tools(m: re.Match) -> str:
        lines = m.group(0).splitlines()
        filtered = [line for line in lines if "check_update" not in line]
        # If only 'allowed-tools:' remains without items, return empty
        if len(filtered) <= 1:
            return ""
        return "\n".join(filtered)

    content = re.sub(
        r"^allowed-tools:\n(?:[ \t]+-[^\n]+\n?)+",
        clean_allowed_tools,
        content,
        flags=re.MULTILINE,
    )

    # 3. Clean '## 开始前' section (strip check_update)
    start_section_pattern = re.compile(
        r"## 开始前\n\n版本检查：[^\n]+\n\n上面仍是一条命令时[^\n]+\n",
        re.MULTILINE,
    )
    replacement_start = (
        "## 开始前\n\n"
        "本 Skill 为企业/团队自研免登录版。若需要从上游 `oil-ui-pro` 同步最新设计方法与工具改进，运行：\n"
        "```sh\n"
        "python3 scripts/sync_upstream.py\n"
        "```\n"
    )
    content = start_section_pattern.sub(replacement_start, content)

    # 4. Remove oiloil-image references in selection scope
    content = content.replace("或 `oiloil-image.mjs` 积分可用", "可用（如本地配置的生图能力）")
    content = content.replace("或 oiloil-image.mjs 积分可用", "可用（如本地配置的生图能力）")

    return content


def transform_media_md(content: str) -> str:
    # Replace oiloil-image.mjs balance and login requirements with local/free guidelines
    pattern = re.compile(
        r"宿主不能生图且本任务已明确授权使用 oiloil 积分时[^\n]+？下载自动生成 `SOURCES\.md`",
        re.MULTILINE,
    )
    replacement = (
        "宿主不能生图时，优先使用宿主或项目配置的本地/外部生图能力（如 `gpt-image-2`），"
        "或通过 `curate-media.mjs` 从 Poly Haven、Wikimedia Commons、各大博物馆开放馆藏（含日本国立博物馆与国会图书馆）、LOC、Wellcome 和 NASA 检索免登录公开素材到本地 `assets/`。"
        "本 Skill 100% 离线免登录，不消耗第三方商业积分，不产生扣费账单。"
        "授权不允许放进页面的条目也能派上用场：下载到不上线的目录，给生图当参考图，取它的题材、年代、构图和材质线索，不让生成结果复刻原图。"
        "编号拉取、贴图直链、联系表和视频 poster 的命令见 [工具](tools.md#检索和下载真实素材)；下载自动生成 `SOURCES.md`"
    )
    return pattern.sub(replacement, content)


def transform_image_ideation_md(content: str) -> str:
    # Clean references to oiloil-image.mjs
    content = re.sub(
        r"2\.\s*\*\*Oil 生图脚本\*\*：若无宿主生图工具，静默调用 `oiloil-image\.mjs` 的 `balance` 子命令[^\n]+",
        "2. **本地扩展生图**：若无宿主内置生图工具，可使用已配置的本地生图工具（如 gpt-image-2 等）直接处理提示词。",
        content,
    )
    content = content.replace("并发调用 `oiloil-image.mjs` 时", "并发调用生图工具时")
    return content


def transform_readme_md(content: str, is_en: bool = False) -> str:
    if is_en:
        return (
            "# weicoz-ui-pro\n\n"
            "An interface design method for AI agents (weicoz enterprise edition).\n"
            "Derived from Oil UI Pro with complete offline decoupling: **100% login-free**, "
            "no remote update checking, and zero external billing.\n\n"
            "## Highlights\n\n"
            "- **Single-Direction Depth**: Recommends one strong direction by default, refining it against real screenshots.\n"
            "- **Signature Moments**: Focuses craft on key interaction accents while keeping the rest calm.\n"
            "- **Multi-Direction Comparison**: Generates side-by-side interactive explorer only when requested.\n"
            "- **10-Point Review**: Rigorous UI/UX inspection without touching business code.\n"
            "- **Zero External Network Dependencies**: All core guidelines, review protocols, and local screenshot/explorer tools run offline.\n\n"
            "## Sync with Upstream\n\n"
            "When upstream `oil-ui-pro` has updates, synchronize into this repository via:\n\n"
            "```sh\n"
            "python3 scripts/sync_upstream.py\n"
            "```\n"
        )
    return (
        "# weicoz-ui-pro\n\n"
        "面向 AI Agent 的专业级界面设计方法（weicoz 自研免登录版）。\n"
        "吸收 Pro 级设计工作流与审查规范，**彻底脱离账号登录、版本更新检查与远程付费积分生图**，适合团队内部共享与持续维护。\n\n"
        "## 核心特性\n\n"
        "- **默认单方向深化**：深入分析业务场景，默认推荐一个最适配的高完成度方案并深化，避免盲目多方案浪费 token。\n"
        "- **留一处让人记住的地方（Signature Moment）**：把关键交互（动效、反馈、核心卡片）做到极致，其余界面保持克制与统一。\n"
        "- **明确要求才做对比**：仅在用户要求比较时，才生成多风格同屏可交互对比页。\n"
        "- **真实画面与 10 分制评审**：双端视口（Desktop 1440x900 / Mobile 390x844）取证，支持只读独立评审。\n"
        "- **100% 免登录纯本地运行**：移除所有第三方账号校验与远程扣费，生图直接对接本地工具或免费 CC0 素材。\n\n"
        "## 上游同步与更新\n\n"
        "当本机已安装的 `oil-ui-pro` 有新版本特性时，可在本 Skill 根目录运行一键同步更新：\n\n"
        "```sh\n"
        "python3 scripts/sync_upstream.py\n"
        "```\n"
        "该脚本会自动对比上游文件，拉取更新并重新执行免登录脱钩转换。\n"
    )


def transform_content(rel_path: Path, raw_text: str) -> str:
    path_str = rel_path.as_posix()
    if path_str == "SKILL.md":
        return transform_skill_md(raw_text)
    elif path_str == "references/media.md":
        return transform_media_md(raw_text)
    elif path_str == "references/image-ideation.md":
        return transform_image_ideation_md(raw_text)
    elif path_str == "README.md":
        return transform_readme_md(raw_text, is_en=False)
    elif path_str == "README.en.md":
        return transform_readme_md(raw_text, is_en=True)
    return raw_text


def scan_upstream(upstream_dir: Path) -> dict[Path, Path]:
    files = {}
    for root, dirs, filenames in os.walk(upstream_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_NAMES]
        for f in filenames:
            if f in IGNORED_NAMES:
                continue
            full_path = Path(root) / f
            rel_path = full_path.relative_to(upstream_dir)
            if rel_path in EXCLUDED_REL_PATHS:
                continue
            files[rel_path] = full_path
    return files


def sync(upstream_dir: Path, apply: bool = False) -> int:
    print(f"上游目录: {upstream_dir}")
    print(f"目标目录: {SKILL_DIR}")
    print(f"模式: {'执行同步 (APPLY)' if apply else '差异检查 (CHECK ONLY)'}")
    print("-" * 60)

    upstream_files = scan_upstream(upstream_dir)
    modified = []
    added = []
    unchanged = []

    for rel_path, src_path in sorted(upstream_files.items()):
        dest_path = SKILL_DIR / rel_path

        # Determine if binary
        is_binary = False
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                src_text = f.read()
            transformed_text = transform_content(rel_path, src_text)
            new_bytes = transformed_text.encode("utf-8")
        except UnicodeDecodeError:
            is_binary = True
            with open(src_path, "rb") as f:
                new_bytes = f.read()

        if not dest_path.exists():
            added.append(rel_path)
            if apply:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(new_bytes)
                shutil.copymode(src_path, dest_path)
        else:
            old_bytes = dest_path.read_bytes()
            if old_bytes != new_bytes:
                modified.append(rel_path)
                if apply:
                    dest_path.write_bytes(new_bytes)
                    shutil.copymode(src_path, dest_path)
            else:
                unchanged.append(rel_path)

    print(f"新增文件: {len(added)} 个")
    for a in added[:10]:
        print(f"  + {a}")
    if len(added) > 10:
        print(f"    ... 以及另外 {len(added) - 10} 个")

    print(f"更新/转换文件: {len(modified)} 个")
    for m in modified[:10]:
        print(f"  * {m}")
    if len(modified) > 10:
        print(f"    ... 以及另外 {len(modified) - 10} 个")

    print(f"无变动文件: {len(unchanged)} 个")

    if not apply and (added or modified):
        print("\n检测到有差异。若需执行同步，请附加 --apply 参数运行。")
        return 1

    if apply:
        print("\n同步并脱钩完成。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="weicoz-ui-pro 上游同步工具")
    parser.add_argument("--upstream", "-u", type=str, help="上游 oil-ui-pro 目录路径（默认自动探测）")
    parser.add_argument("--apply", "-a", action="store_true", help="实际写入改动；缺省时仅检查差异")
    args = parser.parse_args()

    if args.upstream:
        upstream_dir = Path(args.upstream).expanduser().resolve()
    else:
        upstream_dir = find_default_upstream()

    if not upstream_dir or not upstream_dir.is_dir():
        print(
            "错误：未找到上游 oil-ui-pro 安装目录。\n"
            "请指定 --upstream 路径，或确保 ~/.claude/skills/oil-ui-pro 存在。",
            file=sys.stderr,
        )
        return 2

    return sync(upstream_dir, apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
