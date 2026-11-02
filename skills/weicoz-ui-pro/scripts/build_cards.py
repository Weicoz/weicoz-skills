#!/usr/bin/env python3
"""Build an offline gallery, including a 360x180 Natural Earth land bitmap.

Python 3.10+, standard library only. No network and no JS dependencies.
"""
from __future__ import annotations
import argparse
import base64
import math
from pathlib import Path
import re
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / 'assets/cards'
NAMES = ['particle-ring', 'flow-object', 'dot-globe', 'line-ribbons', 'showcase',
         'ui-slice', 'terminal', 'metric', 'beam-graph', 'keycaps', 'promo-band',
         'vector-space', 'file-mosaic', 'stream-window', 'portrait-story', 'capture-notes',
         'answer-lens', 'responsive-preview', 'deploy-preview']


def land_mask() -> None:
    with zipfile.ZipFile(CARDS / 'shared/ne_110m_land.zip') as archive:
        data = archive.read('ne_110m_land.shp')
    polygons = []
    offset = 100
    while offset < len(data):
        length = struct.unpack_from('>i', data, offset + 4)[0] * 2
        record = data[offset + 8:offset + 8 + length]
        offset += 8 + length
        if struct.unpack_from('<i', record)[0] != 5:
            continue
        parts, count = struct.unpack_from('<ii', record, 36)
        starts = list(struct.unpack_from(f'<{parts}i', record, 44)) + [count]
        coords = list(struct.iter_unpack('<dd', record[44 + parts * 4:]))
        polygons.extend(coords[starts[i]:starts[i + 1]] for i in range(parts))
    width, height = 360, 180
    bits = bytearray(math.ceil(width * height / 8))
    # Scanline even/odd fill within each ring. Land data contains exterior rings.
    for y in range(height):
        latitude = 90 - (y + .5) * 180 / height
        for ring in polygons:
            hits = []
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > latitude) != (y2 > latitude):
                    hits.append(x1 + (latitude - y1) * (x2 - x1) / (y2 - y1))
            hits.sort()
            for lo, hi in zip(hits[::2], hits[1::2]):
                start = max(0, math.ceil((lo + 180) / 360 * width - .5))
                end = min(width, math.ceil((hi + 180) / 360 * width - .5))
                for x in range(start, end):
                    i = y * width + x
                    bits[i // 8] |= 1 << (i % 8)
    encoded = base64.b64encode(bits).decode()
    (CARDS / 'shared/land-mask.js').write_text(
        '// Generated from Natural Earth 110m land (public domain).\n'
        f'export const LAND_WIDTH = {width};\nexport const LAND_HEIGHT = {height};\n'
        f'export const LAND_BITS = "{encoded}";\n', encoding='utf-8', newline='\n')


def bundle(path: Path) -> str:
    source = path.read_text(encoding='utf-8')
    exports = re.findall(r'export\s+(?:const|let|function|class)\s+(\w+)', source)
    def replace_import(match: re.Match) -> str:
        target = (path.parent / match[2]).resolve().relative_to(CARDS).as_posix()
        return f'const {{{match[1]}}} = modules["{target}"];'
    source = re.sub(r'import\s*\{([^}]+)\}\s*from\s*[\'"]([^\'"]+)[\'"];?', replace_import, source)
    source = re.sub(r'\bexport\s+(?=const|let|function|class)', '', source)
    if re.search(r'^\s*(import|export)\b', source, re.M):
        raise ValueError(f'Unsupported module syntax: {path}')
    key = path.relative_to(CARDS).as_posix()
    return f'modules["{key}"] = (() => {{\n{source}\nreturn {{{", ".join(exports)}}};\n}})();'


def utf8_output() -> None:
    """管道另一头按 UTF-8 读；控制台的代码页可能连中文都没有。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure') and not stream.isatty():
            stream.reconfigure(encoding='utf-8')


def main(argv: list[str] | None = None) -> None:
    utf8_output()
    parser = argparse.ArgumentParser(
        description='维护卡片库时用：把 assets/cards/ 下各个卡片原型重新打包成 assets/cards/gallery.html。',
        epilog='不带参数运行。它会直接改写 Skill 目录里的 gallery.html，所以只在改过卡片原型的源文件之后运行；'
               '做设计时不需要它，直接打开 assets/cards/gallery.html 或读各原型目录里的 card.html、card.css。')
    parser.parse_args(argv)
    land_mask()
    html = (CARDS / 'gallery.template.html').read_text(encoding='utf-8')
    for name in NAMES:
        html = html.replace('{{' + name + '}}', (CARDS / name / 'card.html').read_text(encoding='utf-8'))
    css = '\n'.join((CARDS / p).read_text(encoding='utf-8') for p in
                    ['shared/shell.css', 'gallery.css'] + [f'{n}/card.css' for n in NAMES] + ['shared/finish.css'])
    paths = [CARDS / 'gallery-palette.js', CARDS / 'gallery-catalog.js', CARDS / 'shared/content.js', CARDS / 'shared/runtime.js', CARDS / 'shared/land-mask.js', CARDS / 'line-ribbons/surface.js', CARDS / 'flow-object/material.js'] + [CARDS / n / 'card.js' for n in NAMES]
    js = '(() => {\nconst modules = {};\n' + '\n'.join(bundle(p) for p in paths)
    js += '\n' + (CARDS / 'gallery-content.js').read_text(encoding='utf-8') + '\n' + (CARDS / 'gallery.js').read_text(encoding='utf-8') + '\n})();'
    html = html.replace('{{styles}}', css).replace('{{scripts}}', js.replace('</script', '<\\/script'))
    # Local image slots are embedded at build time, preserving file:// portability.
    def embed_image(match: re.Match) -> str:
        path = (CARDS / match[1]).resolve()
        path.relative_to(CARDS)
        mime = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[path.suffix]
        return 'src="data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode() + '"'
    html = re.sub(r'src="((?:showcase|portrait-story)/images/[^"<>]+)"', embed_image, html)
    if re.search(r'\{\{[\w-]+\}\}', html):
        raise ValueError('Unresolved template slot')
    (CARDS / 'gallery.html').write_text(html, encoding='utf-8', newline='\n')
    print(f'Built assets/cards/gallery.html · {len(html.encode()):,} bytes · {len(NAMES)} templates')



if __name__ == '__main__':
    main()
