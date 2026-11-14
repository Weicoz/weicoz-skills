#!/usr/bin/env python3
"""游戏素材的切分、裁边与检查（依赖 Pillow）。

用法：
  sheet.py key <png 或目录> <输出目录> [--tol 40]            从四角泛洪去掉纯色背景（出图没有透明通道时用）
  sheet.py split <网格图.png> <行> <列> <输出目录> [--pad 4]   切成单帧，逐帧裁透明边后统一留边
  sheet.py check <png 或目录>... [--opaque]                    检查透明背景、主体占比、尺寸
  sheet.py selftest

--opaque：整幅背景、九宫格面板、铺满的图块本来就不透明，只查尺寸。
key 只去掉与四角相连的背景色；主体里同色的像素保留。渐变或带阴影的背景去不干净，改为重出。

check 判据：
  - 四角不透明：背景没去干净（✗）
  - 主体面积 / 画布面积 < 0.35：留白过多，需裁边或重出（⚠）
  - 最长边 > 1024：首包体积风险（⚠）
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("错误：缺少 Pillow。\n请安装：python3 -m pip install Pillow")


def trim(img, pad):
    rgba = img.convert("RGBA")
    box = rgba.getchannel("A").getbbox()
    if not box:
        return rgba
    body = rgba.crop(box)
    out = Image.new("RGBA", (body.width + pad * 2, body.height + pad * 2), (0, 0, 0, 0))
    out.paste(body, (pad, pad))
    return out


def split(sheet, rows, cols, out_dir, pad):
    img = Image.open(sheet)
    w, h = img.width // cols, img.height // rows
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(sheet).stem
    for r in range(rows):
        for c in range(cols):
            cell = img.crop((c * w, r * h, (c + 1) * w, (r + 1) * h))
            path = out / f"{stem}_{r * cols + c:02d}.png"
            if opaque_corners(cell.convert("RGBA")):
                cell.save(path)  # 背景未去除：原样保存，裁边会掩盖问题
                print(f"✗ 背景未去除，未裁边  {path}")
            else:
                trim(cell, pad).save(path)
                print(path)


def key(target, out_dir, tol):
    from PIL import ImageDraw
    files = sorted(Path(target).glob("**/*.png")) if Path(target).is_dir() else [Path(target)]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        img = Image.open(f).convert("RGBA")
        for xy in [(0, 0), (img.width - 1, 0), (0, img.height - 1), (img.width - 1, img.height - 1)]:
            if img.getpixel(xy)[3] > 16:
                ImageDraw.floodfill(img, xy, (0, 0, 0, 0), thresh=tol)
        img.save(out / f.name)
        print(f"{'✗ 四角仍不透明' if opaque_corners(img) else '✓'}  {out / f.name}")


def opaque_corners(img):
    a = img.getchannel("A")
    return any(a.getpixel(p) > 16 for p in [(0, 0), (img.width - 1, 0), (0, img.height - 1), (img.width - 1, img.height - 1)])


def inspect(path, opaque_ok=False):
    img = Image.open(path).convert("RGBA")
    alpha = img.getchannel("A")
    box = alpha.getbbox()
    fill = 0.0 if not box else (box[2] - box[0]) * (box[3] - box[1]) / (img.width * img.height)
    issues = []
    if not opaque_ok and opaque_corners(img):
        issues.append("✗ 四角不透明，背景未去除（sheet.py key 去背景；本来就该铺满时加 --opaque）")
    if not opaque_ok and fill < 0.35:
        issues.append(f"⚠ 主体占比 {fill:.0%}，留白过多")
    if max(img.size) > 1024:
        issues.append(f"⚠ 尺寸 {img.width}×{img.height} 偏大")
    return img.size, fill, issues


def check(targets, opaque_ok=False):
    files = []
    for t in targets:
        p = Path(t)
        files += sorted(p.glob("**/*.png")) if p.is_dir() else [p]
    bad = 0
    for f in files:
        size, fill, issues = inspect(f, opaque_ok)
        bad += any(i.startswith("✗") for i in issues)
        print(f"{'；'.join(issues) or '✓'}  {size[0]}×{size[1]} 主体 {fill:.0%}  {f}")
    return 1 if bad else 0


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        sheet.paste((255, 0, 0, 255), (40, 40, 60, 60))   # 左格中心 20×20 红块
        sheet.paste((0, 0, 255, 255), (100, 0, 200, 100))  # 右格整格不透明
        sheet.save(f"{d}/s.png")
        split(f"{d}/s.png", 1, 2, f"{d}/out", 2)
        left = Image.open(f"{d}/out/s_00.png")
        assert left.size == (24, 24), left.size
        assert inspect(f"{d}/out/s_00.png")[2] == []
        assert inspect(f"{d}/out/s_01.png")[2][0].startswith("✗")
        assert inspect(f"{d}/out/s_01.png", opaque_ok=True)[2] == []
        # key：白底上一个红块，去底后四角透明、红块保留
        flat = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
        flat.paste((255, 0, 0, 255), (15, 15, 35, 35))
        flat.save(f"{d}/flat.png")
        key(f"{d}/flat.png", f"{d}/keyed", 40)
        keyed = Image.open(f"{d}/keyed/flat.png")
        assert not opaque_corners(keyed) and keyed.getpixel((25, 25)) == (255, 0, 0, 255)
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    pad = int(a[a.index("--pad") + 1]) if "--pad" in a else 4
    tol = int(a[a.index("--tol") + 1]) if "--tol" in a else 40
    if a[:1] == ["split"] and len(a) >= 5:
        split(a[1], int(a[2]), int(a[3]), a[4], pad)
    elif a[:1] == ["key"] and len(a) >= 3:
        key(a[1], a[2], tol)
    elif a[:1] == ["check"] and len(a) >= 2:
        sys.exit(check([x for x in a[1:] if x != "--opaque"], "--opaque" in a))
    elif a[:1] == ["selftest"]:
        selftest()
    else:
        sys.exit(__doc__)
