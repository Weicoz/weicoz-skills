#!/usr/bin/env python3
"""只读检查各 Harness 的 AGENTS.md 入口是否仍与唯一维护源同一文件（硬链接或软链接）。

编辑器“整文件替换”保存会给维护源换新 inode，原有硬链接入口仍指向旧内容，规则从此悄悄分叉。
发现分叉时退出码为 1；不修复，修复方法见 SKILL.md。
"""
import argparse
import os
from pathlib import Path

DEFAULT_SOURCE = '.agents/AGENTS.md'
DEFAULT_ENTRIES = ('.codex/AGENTS.md', '.dsh/AGENTS.md', '.kimi-code/AGENTS.md',
                   '.gemini/AGENTS.md', '.grok/AGENTS.md')


def same_file(a, b):
    sa, sb = a.stat(), b.stat()
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def check(home, source_rel, entry_rels):
    source = home / source_rel
    if not source.is_file():
        return [f'维护源不存在：{source}'], []
    drift, ok = [], []
    for rel in entry_rels:
        entry = home / rel
        if not entry.exists():
            continue
        if same_file(entry, source):
            ok.append(rel)
            continue
        same_text = entry.read_bytes() == source.read_bytes()
        delta = len(source.read_text(encoding='utf-8').splitlines()) - len(
            entry.read_text(encoding='utf-8').splitlines())
        drift.append(f'{rel}：不是维护源的同一文件（内容{"相同" if same_text else "不同"}，'
                     f'维护源比它多 {delta} 行）')
    return drift, ok


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('HOME', '~')).expanduser())
    args = parser.parse_args()
    source = os.environ.get('HARNESS_AGENTS_SOURCE', DEFAULT_SOURCE)
    entries = [e for e in os.environ.get('HARNESS_AGENTS_ENTRIES', ':'.join(DEFAULT_ENTRIES)).split(':') if e]
    drift, ok = check(args.home, source, entries)
    for rel in ok:
        print(f'一致：{rel}')
    for line in drift:
        print(f'分叉：{line}')
    raise SystemExit(1 if drift else 0)


if __name__ == '__main__':
    main()
