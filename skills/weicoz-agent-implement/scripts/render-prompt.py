#!/usr/bin/env python3
"""将票据变量一次替换进模板；变量正文保持原样。"""

import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=值")
    parser.add_argument("--set-file", action="append", default=[], metavar="KEY=路径")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    values = {}
    try:
        for entries, from_file in ((args.set, False), (args.set_file, True)):
            for entry in entries:
                key, separator, value = entry.partition("=")
                if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                    parser.error(f"参数格式应为 KEY=值：{entry}")
                if key in values:
                    parser.error(f"占位值重复：{key}")
                values[key] = Path(value).read_text(encoding="utf-8") if from_file else value
        template = args.template.read_text(encoding="utf-8")
        placeholder = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
        missing = sorted(set(placeholder.findall(template)) - values.keys())
        if missing:
            parser.error("缺少占位值：" + ", ".join(missing))
        rendered = placeholder.sub(lambda match: values[match[1]], template)
        args.out.write_text(rendered, encoding="utf-8")
    except (OSError, UnicodeError) as error:
        parser.error(f"文件读写失败：{error}")


if __name__ == "__main__":
    main()
