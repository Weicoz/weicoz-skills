#!/usr/bin/env python3
"""镜头源码的确定性检查：类型检查是否真能跑、字号下限、禁用非确定 API、镜头内字幕、色板外颜色。

用法：check-shots.py <工程目录> [--min-font 32] [--tokens src/tokens.ts]
                     [--glob 'src/shots/*.tsx' --glob 'src/lib/*.tsx']
类型检查：node_modules/.bin/tsc 存在才跑 tsc --noEmit，不存在报错（原因见 references/process-hygiene.md）；加 --no-tsc 跳过。
字幕：旁白字幕只能由全局字幕层渲染。镜头或公共组件里把 caption 当属性（`caption?: string`、
      `caption={...}`）会让字幕绕过全局层、叠成双层，给警告。这是启发式，数组或别的用途的 caption 字段不报。
退出码：有「错误」项返回 1。色板外颜色只给警告，加 --strict-colors 才算错误。
白名单：工程根的 .shotcraft-colors-allow，每行一个十六进制颜色（可带 # 注释）。
"""
import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path

HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
FONT = re.compile(r"fontSize\s*[:=]\s*\{?\s*(\d+(?:\.\d+)?)\s*[,}]")
CAPTION = re.compile(r"\bcaptions?\??\s*:\s*(?:string\b(?!\s*\[)|React)|\bcaptions?\s*=\s*\{")
NONDET = re.compile(r"\b(Math\.random|Date\.now|new Date\()")


def norm(h: str) -> str:
    h = h.lower().lstrip("#")
    return h if len(h) == 6 else "".join(c * 2 for c in h)


NEUTRAL = {"ffffff", "000000"}  # 纯白、纯黑不算色板外


def strip_comment(line: str) -> str:
    i = line.find("//")
    return line if i < 0 else line[:i]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--min-font", type=float, default=32)
    ap.add_argument("--tokens", default="src/tokens.ts")
    ap.add_argument("--glob", action="append", default=None)
    ap.add_argument("--strict-colors", action="store_true")
    ap.add_argument("--no-tsc", action="store_true")
    a = ap.parse_args()
    root = Path(a.project)
    patterns = a.glob or [
        "src/shots/*.tsx", "src/segments/*.tsx", "src/scenes/*.tsx",
        "src/components/*.tsx", "src/lib/*.tsx", "src/lib/*.ts",
    ]

    allowed = set(NEUTRAL)
    tok = root / a.tokens
    if tok.exists():
        allowed |= {norm(h) for h in HEX.findall(tok.read_text(encoding="utf-8"))}
    allow_file = root / ".shotcraft-colors-allow"
    if allow_file.exists():
        for ln in allow_file.read_text(encoding="utf-8").splitlines():
            m = HEX.match(ln.strip())  # 行首十六进制，后面可跟 # 注释
            if m:
                allowed.add(norm(m.group(0)))
    if allowed == NEUTRAL:
        print(f"提示：{a.tokens} 里没有读到色板，色板外颜色检查跳过。")

    errors, warns = [], []
    if not a.no_tsc and not (root / "tsconfig.json").exists():
        print("提示：没有 tsconfig.json，未检查类型。")
    if not a.no_tsc and (root / "tsconfig.json").exists():
        tsc = root / "node_modules/.bin/tsc"
        if not tsc.exists():
            errors.append("类型检查跑不了：node_modules/.bin/tsc 不存在。运行 npm i -D typescript，并在 package.json 加 \"check\": \"tsc --noEmit\"")
        else:
            r = subprocess.run([str(tsc), "--noEmit"], cwd=root, capture_output=True, text=True)
            if r.returncode != 0:
                first = (r.stdout or r.stderr).strip().splitlines()[:5]
                errors.append("tsc --noEmit 失败：" + " | ".join(first))
    files = sorted({f for p in patterns for f in glob.glob(str(root / p), recursive=True)})
    if not files:
        print("错误：没有匹配到任何镜头文件，检查 --glob。")
        return 2
    for f in files:
        rel = str(Path(f).relative_to(root))
        for n, raw in enumerate(Path(f).read_text(encoding="utf-8").splitlines(), 1):
            line = strip_comment(raw)
            if NONDET.search(line):
                errors.append(f"{rel}:{n} 非确定 API：{NONDET.search(line).group(0)}（渲染必须可逐帧复现）")
            if CAPTION.search(line):
                warns.append(f"{rel}:{n} caption 当属性使用：旁白字幕只能由全局字幕层渲染")
            for m in FONT.finditer(line):
                if float(m.group(1)) < a.min_font:
                    errors.append(f"{rel}:{n} 字号 {m.group(1)} < {a.min_font:g}")
            if allowed != NEUTRAL:
                for m in HEX.finditer(line):
                    if norm(m.group(0)) not in allowed:
                        warns.append(f"{rel}:{n} 色板外颜色 {m.group(0)}")
    bad = errors + (warns if a.strict_colors else [])
    for e in bad:
        print("错误", e)
    for w in warns if not a.strict_colors else []:
        print("警告", w)
    print(f"\n检查 {len(files)} 个文件：错误 {len(bad)}，警告 {0 if a.strict_colors else len(warns)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
