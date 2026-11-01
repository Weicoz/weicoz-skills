#!/usr/bin/env python3
"""weicoz-skill-tiers：按 manifest 把 skill 分为 L1 常驻 / L2 短描述桩 / L3 领域 Hub 收纳。

只改各 harness 发现目录里的软链，并在独立目录生成桩与 Hub；原 skill 文件不改动。
所有变更前先写快照，可用 restore 精确回滚。仅依赖 Python 标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("HOME", str(Path.home())))
ROOT = Path(os.environ.get("SKILL_TIERS_HOME", str(HOME / ".agents" / "skill-tiers"))).expanduser()
DEFAULT_DISCOVERY = [
    "~/.agents/skills",
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.dsh/skills",
    "~/.grok/skills",
    "~/.kimi-code/skills",
    "~/.gemini/config/skills",
]
MARK = "<!-- generated-by: weicoz-skill-tiers -->"


def fallback(ctx: "Ctx") -> str:
    """跨 skill 调用的回退规则：被引用的 skill 可能已分层为仅手动调用或已收纳。"""
    return (
        f"所读 skill 指示使用其他 skill 时，先按常规方式调用；调用被拒绝（仅限用户手动调用）或找不到时，"
        f"完整读取 `{ctx.lib}/<skill名>/SKILL.md` 并按其执行，不得据此判定该 skill 未安装。"
    )


def expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()


def die(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(1)


class Ctx:
    def __init__(self, manifest_path: Path):
        if not manifest_path.exists():
            die(
                f"未找到 manifest：{manifest_path}\n"
                f"请先复制示例：cp <skill_dir>/references/manifest.example.json {manifest_path}\n"
                "或设置环境变量 SKILL_TIERS_HOME 指向自定义目录。"
            )
        try:
            self.m = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die(f"manifest 不是合法 JSON：{e}")
        self.root = manifest_path.parent
        self.gen = self.root / "generated"
        self.lib = self.root / "library"
        self.backups = self.root / "backups"
        self.dirs = [expand(d) for d in self.m.get("discovery_dirs", DEFAULT_DISCOVERY)]
        self.dirs = [d for d in self.dirs if d.is_dir()]
        self.l1 = list(self.m.get("l1", []))
        self.l2 = dict(self.m.get("l2", {}))
        self.hubs = dict(self.m.get("hubs", {}))
        # L3 默认生成手动调用桩；不支持“仅手动调用”的 harness 目录写进排除列表
        self.l3_manual = bool(self.m.get("l3_manual", True))
        self.l3_manual_exclude = {expand(d) for d in self.m.get("l3_manual_exclude_dirs", [])}
        self.l3 = {}
        for hub, spec in self.hubs.items():
            for name, note in spec.get("skills", {}).items():
                self.l3[name] = (hub, note)
        self._validate()
        # 记录各发现目录原本安装过哪些 skill，L3 移除后可按原范围恢复
        self.state_file = self.root / "installed.json"
        self.installed: dict[str, set[str]] = {}
        if self.state_file.exists():
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.installed = {k: set(v) for k, v in raw.items()}
        for d in self.dirs:
            s = self.installed.setdefault(str(d), set())
            s.update(p.name for p in d.iterdir() if p.is_symlink() and not self.is_ours(p))

    def save_state(self) -> None:
        self.state_file.write_text(
            json.dumps({k: sorted(v) for k, v in self.installed.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def _validate(self) -> None:
        seen: dict[str, str] = {}
        dup = []
        for tier, names in (("l1", self.l1), ("l2", self.l2), ("hub", self.l3)):
            for n in names:
                if n in seen:
                    dup.append(f"{n}（{seen[n]} 与 {tier}）")
                seen[n] = tier
        for h in self.hubs:
            if h in seen:
                dup.append(f"{h}（Hub 名与 skill 重名）")
        if dup:
            die("manifest 中名称重复：" + "、".join(dup))

    def manual_in(self, d: Path) -> bool:
        return self.l3_manual and d not in self.l3_manual_exclude

    def is_ours(self, link: Path) -> bool:
        if not link.is_symlink():
            return False
        t = os.readlink(link)
        return str(Path(t)).startswith(str(self.gen))

    def original_target(self, name: str) -> str | None:
        """原 skill 的真实目录：优先 library 记录，其次任一发现目录中的非本工具软链。"""
        lib = self.lib / name
        if lib.is_symlink():
            return os.readlink(lib)
        for d in self.dirs:
            p = d / name
            if p.is_symlink() and not self.is_ours(p):
                return os.readlink(p)
        # 只有真实目录时，供 library/Hub 引用；真实目录本身不改动
        for d in self.dirs:
            p = d / name
            if p.is_dir() and not p.is_symlink():
                return str(p)
        return None


# ---------- 生成 ----------

def fm_escape(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def write_stub(ctx: Ctx, name: str, desc: str) -> None:
    lib = ctx.lib / name
    d = ctx.gen / name
    d.mkdir(parents=True, exist_ok=True)
    # 从 L3 调回 L2 时，去掉手动调用桩留下的 Codex 策略文件
    policy = d / "agents" / "openai.yaml"
    if policy.exists():
        policy.unlink()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {fm_escape(desc)}\n---\n{MARK}\n\n"
        f"# {name}（L2 短描述桩）\n\n"
        f"本 skill 的完整说明位于 `{lib}/SKILL.md`。\n\n"
        f"1. 执行前必须完整读取该文件，并按其指引执行。\n"
        f"2. 该文件中的相对路径（scripts/、references/ 等）以 `{lib}/` 为基准。\n"
        f"3. 该文件的 frontmatter（如 context、allowed-tools）在桩模式下不自动生效，需要时按其意图手动遵守。\n"
        f"4. {fallback(ctx)}\n",
        encoding="utf-8",
    )


def write_manual(ctx: Ctx, name: str, hub: str, note: str) -> None:
    """L3 手动调用桩：可斜杠/$ 调用，不进入模型的 skill 列表。"""
    lib = ctx.lib / name
    d = ctx.gen / name
    (d / "agents").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {fm_escape(note)}\ndisable-model-invocation: true\n---\n{MARK}\n\n"
        f"# {name}（L3 手动调用桩，所属 {hub}）\n\n"
        f"本 skill 的完整说明位于 `{lib}/SKILL.md`。\n\n"
        f"1. 执行前必须完整读取该文件，并按其指引执行。\n"
        f"2. 该文件中的相对路径（scripts/、references/ 等）以 `{lib}/` 为基准。\n"
        f"3. 该文件的 frontmatter（如 context、allowed-tools）在桩模式下不自动生效，需要时按其意图手动遵守。\n"
        f"4. {fallback(ctx)}\n",
        encoding="utf-8",
    )
    # Codex 不认 disable-model-invocation，用 agents/openai.yaml 关闭隐式调用
    (d / "agents" / "openai.yaml").write_text(
        f"interface:\n  display_name: {fm_escape(name)}\n  short_description: {fm_escape(note)}\n"
        "policy:\n  allow_implicit_invocation: false\n",
        encoding="utf-8",
    )


def write_hub(ctx: Ctx, hub: str, spec: dict) -> None:
    d = ctx.gen / hub
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, note in spec.get("skills", {}).items():
        rows.append(f"| `{name}` | {note} | `{ctx.lib / name}/SKILL.md` |")
    see = spec.get("see_also", [])
    see_line = f"\n同领域的常驻或桩 skill（可直接调用）：{'、'.join(f'`{s}`' for s in see)}。\n" if see else ""
    intro = f"{spec['intro']}\n\n" if spec.get("intro") else ""
    (d / "SKILL.md").write_text(
        f"---\nname: {hub}\ndescription: {fm_escape(spec.get('description', ''))}\n---\n{MARK}\n\n"
        f"# {hub}（领域 Hub）\n\n{intro}"
        "## 用法\n\n"
        "1. 按“何时用”列选出最匹配的 1–2 个 skill；近义项按说明里的优先级取舍。\n"
        "2. 用文件读取工具完整读取所选 skill 的 SKILL.md，再按其指引执行。\n"
        "3. 所选 skill 中的相对路径以其 SKILL.md 所在目录为基准。\n"
        "4. 表内没有合适项时，说明未命中，不得勉强套用。\n"
        f"5. {fallback(ctx)}\n"
        f"{see_line}\n"
        "## 索引\n\n| skill | 何时用 | 说明文件 |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


# ---------- 快照与动作 ----------

def snapshot(ctx: Ctx) -> Path:
    data = {}
    for d in ctx.dirs:
        data[str(d)] = {p.name: os.readlink(p) for p in sorted(d.iterdir()) if p.is_symlink()}
    ctx.backups.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, indent=1)
    # 首次 apply 的状态单独保留，后续快照不覆盖它
    base = ctx.backups / "baseline.json"
    if not base.exists():
        base.write_text(body, encoding="utf-8")
    f = ctx.backups / f"snapshot-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**9:09d}.json"
    f.write_text(body, encoding="utf-8")
    return f


def relink(path: Path, target: str, dry: bool) -> None:
    if dry:
        return
    if path.is_symlink():
        path.unlink()
    path.symlink_to(target)


def unlink(path: Path, dry: bool) -> None:
    if not dry and path.is_symlink():
        path.unlink()


def plan_actions(ctx: Ctx) -> tuple[list[tuple], list[str]]:
    """返回 (动作列表, 警告)。动作：(op, dir, name, target)。op ∈ link/unlink。"""
    acts: list[tuple] = []
    warns: list[str] = []
    managed = set(ctx.l1) | set(ctx.l2) | set(ctx.l3)
    for name in sorted(managed):
        if ctx.original_target(name) is None:
            warns.append(f"{name}：任何发现目录中都没有原始软链，已跳过")
    for d in ctx.dirs:
        for name in sorted(managed):
            p = d / name
            orig = ctx.original_target(name)
            if orig is None:
                continue
            if p.exists() and not p.is_symlink():
                warns.append(f"{p}：是真实目录，不处理")
                continue
            cur = os.readlink(p) if p.is_symlink() else None
            # 只替换现存链接，不补回缺失项：缺失可能是用户或其他管理器（如 skills-manager）主动取消部署。
            # 例外：被 l3_manual_exclude_dirs 排除的目录中，L3 链接由本工具移除，调层时按安装记录恢复。
            if d in ctx.l3_manual_exclude:
                installed = cur is not None or name in ctx.installed.get(str(d), set())
            else:
                installed = cur is not None
            if name in ctx.l1:
                if installed and (cur is None or ctx.is_ours(p)):
                    acts.append(("link", d, name, orig))
            elif name in ctx.l2:
                tgt = str(ctx.gen / name)
                if installed and cur != tgt:
                    acts.append(("link", d, name, tgt))
            elif ctx.manual_in(d):
                tgt = str(ctx.gen / name)
                if installed and cur != tgt:
                    acts.append(("link", d, name, tgt))
            elif cur is not None:
                acts.append(("unlink", d, name, None))
        for hub in sorted(ctx.hubs):
            p = d / hub
            tgt = str(ctx.gen / hub)
            if p.exists() and not p.is_symlink():
                warns.append(f"{p}：是真实目录，Hub 不覆盖")
                continue
            if not (p.is_symlink() and os.readlink(p) == tgt):
                acts.append(("link", d, hub, tgt))
        # 已从 manifest 移除的旧 Hub/桩链接：恢复原始或清除
        for p in d.iterdir():
            if ctx.is_ours(p) and p.name not in managed and p.name not in ctx.hubs:
                orig = ctx.lib.joinpath(p.name)
                acts.append(("link", d, p.name, os.readlink(orig)) if orig.is_symlink() else ("unlink", d, p.name, None))
    return acts, warns


def cmd_apply(ctx: Ctx, dry: bool) -> None:
    acts, warns = plan_actions(ctx)
    for w in warns:
        print(f"[警告] {w}")
    if not dry:
        snap = snapshot(ctx)
        ctx.save_state()
        print(f"快照：{snap}")
        # library 先建好，桩与 Hub 指向它
        ctx.lib.mkdir(parents=True, exist_ok=True)
        for name in set(ctx.l2) | set(ctx.l3):
            orig = ctx.original_target(name)
            lp = ctx.lib / name
            if orig and not lp.is_symlink():
                lp.symlink_to(orig)
        for name, desc in ctx.l2.items():
            if (ctx.lib / name).is_symlink():
                write_stub(ctx, name, desc)
        if ctx.l3_manual:
            for name, (hub, note) in ctx.l3.items():
                if (ctx.lib / name).is_symlink():
                    write_manual(ctx, name, hub, note)
        for hub, spec in ctx.hubs.items():
            write_hub(ctx, hub, spec)
    summary: dict[str, dict[str, int]] = {}
    for op, d, name, tgt in acts:
        s = summary.setdefault(str(d), {"link": 0, "unlink": 0})
        s[op] += 1
        if op == "link":
            relink(d / name, tgt, dry)
        else:
            unlink(d / name, dry)
    print(("[预演] " if dry else "") + f"共 {len(acts)} 项动作")
    for d, s in summary.items():
        print(f"  {d}：改链 {s['link']}，移除 {s['unlink']}")


def cmd_restore(ctx: Ctx, snap: Path, dry: bool) -> None:
    data = json.loads(snap.read_text(encoding="utf-8"))
    n = 0
    for d_str, links in data.items():
        d = Path(d_str)
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if ctx.is_ours(p) and p.name not in links:
                unlink(p, dry); n += 1
        for name, tgt in links.items():
            p = d / name
            if p.exists() and not p.is_symlink():
                continue
            if not (p.is_symlink() and os.readlink(p) == tgt):
                relink(p, tgt, dry); n += 1
    print(("[预演] " if dry else "") + f"按 {snap.name} 恢复 {n} 个链接")


def desc_len(skill_dir: Path) -> int:
    f = skill_dir / "SKILL.md"
    if not f.exists():
        return 0
    t = f.read_text(encoding="utf-8", errors="ignore")
    if not t.startswith("---"):
        return 0
    fm = t.split("---", 2)[1]
    m = re.search(r"^description:\s*(.*?)(?=^\w[\w-]*:|\Z)", fm, re.S | re.M)
    if not m or "disable-model-invocation: true" in fm:
        return 0
    return len(re.sub(r"\s+", " ", m.group(1)).strip())


def global_rule_state(ctx: Ctx) -> list[tuple[Path, bool]]:
    """manifest 的 global_rules 列出的全局规则文件中，是否写有指向 library 的回退规则。"""
    out = []
    lib_tilde = "~/" + str(ctx.lib.relative_to(HOME)) if ctx.lib.is_relative_to(HOME) else str(ctx.lib)
    for f in ctx.m.get("global_rules", []):
        p = expand(f)
        text = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
        out.append((p, str(ctx.lib) in text or lib_tilde in text))
    return out


def cmd_status(ctx: Ctx) -> None:
    managed = set(ctx.l1) | set(ctx.l2) | set(ctx.l3)
    print(f"manifest：L1 {len(ctx.l1)}，L2 {len(ctx.l2)}，Hub {len(ctx.hubs)}（收纳 {len(ctx.l3)}）")
    for d in ctx.dirs:
        entries = [p for p in d.iterdir() if (p.is_symlink() or p.is_dir()) and not p.name.startswith(".")]
        lens = [desc_len(p) for p in entries]
        visible = sum(1 for n in lens if n > 0)
        unmanaged = [p for p in entries if p.name not in managed and p.name not in ctx.hubs]
        print(f"{d}：条目 {len(entries)}，模型可见 {visible}，描述合计约 {sum(lens)} 字符，未分层 {len(unmanaged)}")
    acts, _ = plan_actions(ctx)
    print(f"漂移：{len(acts)} 项" + ("（运行 apply 修正）" if acts else ""))
    gaps = deps_gaps(ctx)
    print(f"L3 引用缺口：{len(gaps)} 个" + ("（运行 deps 查看）" if gaps else ""))
    for p, ok in global_rule_state(ctx):
        print(f"全局回退规则：{p} {'已写入' if ok else '缺失'}")
    first = ctx.dirs[0] if ctx.dirs else None
    if first:
        un = sorted(
            p.name + ("（仅手动）" if desc_len(p) == 0 else "")
            for p in first.iterdir()
            if (p.is_symlink() or p.is_dir()) and not p.name.startswith(".")
            and p.name not in managed and p.name not in ctx.hubs
        )
        if un:
            print(f"{first} 未分层（保持原样）：{', '.join(un)}")


def read_desc(skill_dir: Path) -> str:
    f = skill_dir / "SKILL.md"
    if not f.exists():
        return ""
    t = f.read_text(encoding="utf-8", errors="ignore")
    fm = t.split("---", 2)[1] if t.startswith("---") else ""
    m = re.search(r"^description:\s*(.*?)(?=^\w[\w-]*:|\Z)", fm, re.S | re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip(" >|\"'") if m else ""


def cmd_find(ctx: Ctx, terms: list[str]) -> None:
    """按名称与描述查找 skill（含已收纳的 L3），报告层级与调用方式。"""
    rows = []
    names = set(ctx.l1) | set(ctx.l2) | set(ctx.l3)
    for d in ctx.dirs:
        names.update(p.name for p in d.iterdir() if not p.name.startswith(".") and not ctx.is_ours(p))
    for name in sorted(names):
        orig = ctx.original_target(name)
        desc = read_desc(Path(orig)) if orig else ""
        if name in ctx.l1:
            tier, extra = "L1 常驻", ""
        elif name in ctx.l2:
            tier, extra = "L2 桩", ctx.l2[name]
        elif name in ctx.l3:
            hub, extra = ctx.l3[name]
            tier = f"L3 · {hub}"
        else:
            tier, extra = "未分层", ""
        hay = f"{name} {extra} {desc}".lower()
        if all(t.lower() in hay for t in terms):
            rows.append((name, tier, extra or desc[:80], f"{orig}/SKILL.md" if orig else "-"))
    if not rows:
        print("未找到匹配的 skill。可换关键词，或用 status 查看未分层清单。")
        return
    for name, tier, note, path in rows:
        print(f"{name}  [{tier}]\n  {note}\n  {path}")
    print(f"\n共 {len(rows)} 个。L1/L2/未分层可直接调用；L3 用 /<name>（Codex 用 $<name>）手动调用，或经所属 Hub 选用。")


def skill_refs(text: str, name: str) -> bool:
    """按 skill 引用语境判断：`name`、/name、$name，或与“skill”相邻；排除普通单词式的误报。"""
    n = re.escape(name)
    b = r"(?![\w-])"
    pats = [
        rf"`[/$]?{n}`",
        rf"[\"“]{n}[\"”]",
        rf"(?<![\w-])[/$]{n}{b}",
        rf"(?<![\w-]){n}{b}\s*(?:skill|Skill|技能)",
        rf"(?:skill|Skill|技能)\s*[:：]?\s*[`'\"“]?{n}{b}",
    ]
    return any(re.search(p, text) for p in pats)


def deps_gaps(ctx: Ctx) -> dict[str, list[str]]:
    """原文直接加载的 skill（L1 与未分层）对 L3 的引用；这类调用不经过桩与 Hub 的回退规则。"""
    callers = set(ctx.l1)
    for d in ctx.dirs:
        callers.update(
            p.name for p in d.iterdir()
            if not p.name.startswith(".") and not ctx.is_ours(p)
            and p.name not in ctx.l2 and p.name not in ctx.l3 and p.name not in ctx.hubs
        )
    found = {}
    for caller in sorted(callers):
        orig = ctx.original_target(caller)
        f = Path(orig) / "SKILL.md" if orig else None
        if not f or not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        hits = sorted(n for n in ctx.l3 if n != caller and skill_refs(text, n))
        if hits:
            found[caller] = hits
    return found


def cmd_deps(ctx: Ctx) -> None:
    found = deps_gaps(ctx)
    if not found:
        print("无缺口：L1 与未分层 skill 没有引用 L3 skill。")
        return
    print("以下 skill 原文直接加载，却引用了 L3 skill（调用可能被拒绝）：")
    for caller, hits in found.items():
        tier = "L1" if caller in ctx.l1 else "未分层"
        print(f"  [{tier}] {caller} -> {', '.join(f'{h}（{ctx.l3[h][0]}）' for h in hits)}")
    print("\n处理：核对确属模型自动调用后，把被引用的 skill 从 Hub 移到 L2（写短描述），再 apply。"
          "\n已在全局规则写入回退规则时（见 status），这些调用也能经回退读取原文；仅手动调用的引用（如让用户输入 /name）无需处理。")


def main() -> None:
    ap = argparse.ArgumentParser(description="skill 三层 + 领域 Hub 分层工具")
    ap.add_argument("--manifest", default=str(ROOT / "manifest.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="查看分层状态、描述体量与漂移")
    sub.add_parser("plan", help="预演 apply，不改动任何文件")
    sub.add_parser("apply", help="写快照后按 manifest 改链并生成桩与 Hub")
    sub.add_parser("deps", help="检查 L1 与未分层 skill 对 L3 的引用缺口")
    f = sub.add_parser("find", help="按名称与描述查找 skill（含 L3），报告层级与调用方式")
    f.add_argument("terms", nargs="+")
    r = sub.add_parser("restore", help="按快照恢复发现目录的软链")
    r.add_argument("snapshot")
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ctx = Ctx(expand(a.manifest))
    if a.cmd == "status":
        cmd_status(ctx)
    elif a.cmd == "plan":
        cmd_apply(ctx, dry=True)
    elif a.cmd == "apply":
        cmd_apply(ctx, dry=False)
    elif a.cmd == "deps":
        cmd_deps(ctx)
    elif a.cmd == "find":
        cmd_find(ctx, a.terms)
    elif a.cmd == "restore":
        cmd_restore(ctx, expand(a.snapshot), a.dry_run)


if __name__ == "__main__":
    main()
