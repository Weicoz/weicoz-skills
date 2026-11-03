#!/usr/bin/env python3
"""真实素材选材：搜索 → 候选页 → 下载转码 → 来源记录 → 署名。只用标准库 + ffmpeg/ffprobe。

用法：
  media-source.py search <工程> --q "关键词" --kind photo|video [--sources pexels,pixabay,unsplash,wikimedia]
                  [--orientation landscape|portrait|square|any（默认 landscape）] [--min-width 1920] [--min-dur 秒] [--shot s4]
                  [--per-source 12] [--allow-sa] [--allow-lowres]
  media-source.py get <工程> <source:id> --picked-by user|"agent:理由" [--kind photo|video] [--shot s4]
                  [--name slug] [--fps 30] [--keep-audio] [--allow-sa]
  media-source.py sheet <工程> --name <名> --files a.png b.mp4 ...   用本地图片/视频（视频取第 1 秒）拼联系表
  media-source.py import <工程> <本地文件> --shot s4 --tool "途径" --prompt "提示词" --picked-by user|"agent:理由"
                  [--model 模型名] [--name slug] [--kind photo|video] [--fps 30] [--keep-audio]
  media-source.py fetch <工程> [--all]
  media-source.py credits <工程>

读写：
  search  写 <工程>/media/candidates/<shot|关键词>.json 与同名 .html，并生成缩略图联系表 <名>_sheet.jpg
  sheet   <工程> --name <shot|关键词> [--top 12]：重新生成联系表（代理挑素材前看这一张图）
  get     写 <工程>/public/media/<shot>/<slug>.<ext>，更新 <工程>/media/sources.json（按 file 去重）
  sheet --files  写 <工程>/media/candidates/<名>_sheet.jpg，打印「第 N 张 = 文件路径」（不读候选 json）
  import  导入 AI 生成的本地文件（本脚本不调用任何生成模型）：转码后存两份——
          入库副本 <工程>/media/generated/<shot>/<slug>.<ext>（唯一真相源，必须入库）与
          渲染副本 <工程>/public/media/<shot>/<slug>.<ext>（不入库）；写 sources.json（source=generated）
  fetch   按 sources.json 重新下载缺失文件；src_sha256 变化报错，最终 sha256 变化只警告；
          generated 条目不联网，从 generated_file 复制（缺失则报错）
  credits 写 <工程>/media/CREDITS.md；有 generated 条目时增加「AI 生成」一节与简介声明
环境变量（缺失时跳过该来源并提示，不报错）：
  PEXELS_API_KEY、PIXABAY_API_KEY、UNSPLASH_ACCESS_KEY；Wikimedia 不需要 Key。
  MEDIA_SOURCE_UA 覆盖 Wikimedia 要求的 User-Agent。
许可策略：默认接受 pexels/pixabay/unsplash/cc0/pd/cc-by*；--allow-sa 再接受 cc-by-sa*；NC/ND/unknown 一律拒绝。
说明：同一来源的照片与视频 id 可能重号，get 默认 --kind photo，视频必须写 --kind video（候选页的命令已带上）。
退出码：0 成功；1 业务失败（无结果、许可不合、哈希变化）；2 参数或环境错误。
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 25
DL_TIMEOUT = 120
ALL_SOURCES = ["pexels", "pixabay", "unsplash", "wikimedia"]
KEY_ENV = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY"}
KEY_URL = {"pexels": "https://www.pexels.com/api/", "pixabay": "https://pixabay.com/api/docs/",
           "unsplash": "https://unsplash.com/developers"}
SRC_LABEL = {"pexels": "Pexels", "pixabay": "Pixabay", "unsplash": "Unsplash", "wikimedia": "Wikimedia Commons"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".ogv"}


class Fail(Exception):
    """业务失败，退出码 1。"""


class Usage(Exception):
    """参数或环境错误，退出码 2。"""


# ---------------------------------------------------------------- 网络

def user_agent():
    return os.environ.get("MEDIA_SOURCE_UA") or "weicoz-video-shotcraft-patch/1.0 (media-source)"


def http_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise Fail(f"请求失败 HTTP {e.code}：{url.split('?')[0]}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise Fail(f"请求失败（{e}）：{url.split('?')[0]}")


def download(url, dest, headers=None):
    """下载到 dest，返回 sha256。"""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(), **(headers or {})})
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(req, timeout=DL_TIMEOUT) as r, open(dest, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                h.update(b)
                f.write(b)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Fail(f"下载失败（{e}）：{url.split('?')[0]}")
    return h.hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def get_key(source):
    env = KEY_ENV[source]
    v = os.environ.get(env, "").strip()
    if not v:
        raise Usage(f"未配置 {SRC_LABEL[source]} 凭据。请先配置环境变量：\n"
                    f'  export {env}="..."   # 申请：{KEY_URL[source]}')
    return v


# ---------------------------------------------------------------- 许可

def normalize_license(source, raw=""):
    if source in ("pexels", "pixabay", "unsplash"):
        return source
    s = (raw or "").strip().lower()
    if not s:
        return "unknown"
    toks = set(re.split(r"[^a-z0-9]+", s))
    if toks & {"nc", "nd"}:
        return "unknown"
    if re.search(r"\bcc[ -]?0\b", s) or "public domain dedication" in s:
        return "cc0"
    if s.startswith("public domain") or s == "pd" or s.startswith("pd-") or s.startswith("pd "):
        return "pd"
    m = re.search(r"cc[ -]by[ -]sa[ -]([\d.]+)", s)
    if m:
        return f"cc-by-sa-{m.group(1)}"
    m = re.search(r"cc[ -]by[ -]([\d.]+)", s)
    if m:
        return f"cc-by-{m.group(1)}"
    return "unknown"


def license_ok(lic, allow_sa=False):
    if re.fullmatch(r"cc-by-sa-[\d.]+", lic):
        return allow_sa
    return lic in ("pexels", "pixabay", "unsplash", "cc0", "pd", "generated") or bool(re.fullmatch(r"cc-by-[\d.]+", lic))


def license_label(lic):
    if lic.startswith("cc-by"):
        return _cc_label(lic)
    return {"pexels": "Pexels License", "pixabay": "Pixabay Content License",
            "unsplash": "Unsplash License", "cc0": "CC0", "pd": "Public Domain",
            "generated": "AI 生成"}.get(lic, lic)


def _cc_label(lic):
    m = re.match(r"cc-by(-sa)?-([\d.]+)$", lic)
    if not m:
        return lic
    return f"CC BY{'-SA' if m.group(1) else ''} {m.group(2)}"


# ---------------------------------------------------------------- 解析

def strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def cand(source, kind, id_, **kw):
    c = {"source": source, "id": str(id_), "kind": kind, "title": "", "page_url": "", "thumb": "",
         "preview_url": "", "w": 0, "h": 0, "dur": None, "license": "unknown", "license_url": "",
         "author": "", "author_url": "", "files": [], "rank": 0}
    c.update(kw)
    c["key"] = f"{source}:{id_}"
    return c


def parse_pexels_item(it, kind, rank=0):
    user = it.get("photographer") or (it.get("user") or {}).get("name", "")
    uurl = it.get("photographer_url") or (it.get("user") or {}).get("url", "")
    common = dict(title=it.get("alt") or "", page_url=it.get("url", ""), author=user, author_url=uurl,
                  license="pexels", license_url="https://www.pexels.com/license/", rank=rank,
                  w=it.get("width", 0), h=it.get("height", 0))
    if kind == "photo":
        src = it.get("src", {})
        files = [{"url": src["original"], "w": it.get("width", 0), "h": it.get("height", 0), "type": "image/jpeg"}] \
            if src.get("original") else []
        return cand("pexels", kind, it["id"], thumb=src.get("medium", ""), files=files, **common)
    files = [{"url": f["link"], "w": f.get("width") or 0, "h": f.get("height") or 0, "type": f.get("file_type", "")}
             for f in it.get("video_files", []) if f.get("link") and f.get("file_type") == "video/mp4"]
    prev = min(files, key=lambda f: f["w"] or 1e9)["url"] if files else ""
    return cand("pexels", kind, it["id"], thumb=it.get("image", ""), preview_url=prev, files=files,
                dur=it.get("duration"), **common)


def parse_pexels(data, kind):
    key = "photos" if kind == "photo" else "videos"
    return [parse_pexels_item(it, kind, i) for i, it in enumerate(data.get(key, []))]


def parse_pixabay_item(it, kind, rank=0):
    common = dict(title=(it.get("tags") or ""), page_url=it.get("pageURL", ""), author=it.get("user", ""),
                  author_url=(f"https://pixabay.com/users/{it.get('user','')}-{it['user_id']}/"
                              if it.get("user_id") else ""),
                  license="pixabay", license_url="https://pixabay.com/service/license-summary/", rank=rank)
    if kind == "photo":
        w, h = it.get("imageWidth", 0), it.get("imageHeight", 0)
        if it.get("imageURL"):
            files = [{"url": it["imageURL"], "w": w, "h": h, "type": "image/jpeg"}]
        else:  # 没有原图权限时只有 1280 宽版本
            lw = 1280
            lh = round(h * lw / w) if w else 0
            files = [{"url": it["largeImageURL"], "w": min(w, lw), "h": lh if w > lw else h, "type": "image/jpeg"}]
            w, h = files[0]["w"], files[0]["h"]
        return cand("pixabay", kind, it["id"], thumb=it.get("webformatURL") or it.get("previewURL", ""),
                    w=w, h=h, files=files, **common)
    files = [{"url": v["url"], "w": v.get("width", 0), "h": v.get("height", 0), "type": "video/mp4"}
             for v in (it.get("videos") or {}).values() if v.get("url")]
    big = max(files, key=lambda f: f["w"]) if files else {"w": 0, "h": 0}
    small = min(files, key=lambda f: f["w"])["url"] if files else ""
    vids = it.get("videos") or {}
    # 现行接口在各清晰度条目里给 thumbnail；旧接口只有 picture_id
    thumb = next((vids[k]["thumbnail"] for k in ("medium", "small", "large", "tiny") if (vids.get(k) or {}).get("thumbnail")), "")
    if not thumb and it.get("picture_id"):
        thumb = f"https://i.vimeocdn.com/video/{it['picture_id']}_640x360.jpg"
    return cand("pixabay", kind, it["id"], thumb=thumb, preview_url=small, w=big["w"], h=big["h"],
                dur=it.get("duration"), files=files, **common)


def parse_pixabay(data, kind):
    return [parse_pixabay_item(it, kind, i) for i, it in enumerate(data.get("hits", []))]


def parse_unsplash_item(it, rank=0):
    u = it.get("user") or {}
    urls = it.get("urls") or {}
    return cand("unsplash", "photo", it["id"], title=it.get("description") or it.get("alt_description") or "",
                page_url=(it.get("links") or {}).get("html", ""), thumb=urls.get("small", ""),
                w=it.get("width", 0), h=it.get("height", 0), license="unsplash",
                license_url="https://unsplash.com/license", author=u.get("name", ""),
                author_url=(u.get("links") or {}).get("html", ""), rank=rank,
                files=[{"url": urls.get("full") or urls.get("raw", ""), "w": it.get("width", 0),
                        "h": it.get("height", 0), "type": "image/jpeg"}],
                download_location=(it.get("links") or {}).get("download_location", ""))


def parse_unsplash(data):
    return [parse_unsplash_item(it, i) for i, it in enumerate(data.get("results", []))]


def parse_wikimedia(data, kind, big_thumb=False):
    pages = sorted(((data.get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for i, p in enumerate(pages):
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        mime = ii.get("mime", "")
        if kind == "video" and not (mime.startswith("video/") or mime in ("application/ogg",)):
            continue
        if kind == "photo" and mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        md = ii.get("extmetadata") or {}
        val = lambda k: (md.get(k) or {}).get("value", "")
        lic = normalize_license("wikimedia", val("LicenseShortName"))
        title = re.sub(r"\.\w+$", "", p.get("title", "").replace("File:", "", 1))
        author = strip_html(val("Artist"))
        aurl = ""
        m = re.search(r'href="([^"]+)"', val("Artist"))
        if m:
            aurl = m.group(1)
            if aurl.startswith("//"):
                aurl = "https:" + aurl
        w, h = ii.get("width", 0), ii.get("height", 0)
        furl = ii["url"]
        if kind == "photo" and big_thumb and w > 3840 and ii.get("thumburl"):
            files = [{"url": ii["thumburl"], "w": ii.get("thumbwidth", 0), "h": ii.get("thumbheight", 0), "type": mime}]
        else:
            files = [{"url": furl, "w": w, "h": h, "type": mime}]
        out.append(cand("wikimedia", kind, p["pageid"], title=title, page_url=ii.get("descriptionurl", ""),
                        thumb=ii.get("thumburl", ""), preview_url=furl if kind == "video" else "", w=w, h=h,
                        dur=ii.get("duration"), license=lic, license_url=strip_html(val("LicenseUrl")),
                        author=author, author_url=aurl, files=files, rank=i,
                        license_raw=strip_html(val("LicenseShortName"))))
    return out


# ---------------------------------------------------------------- 搜索与详情

def api_search(source, q, kind, orientation, per):
    qq = urllib.parse.quote(q)
    if source == "pexels":
        h = {"Authorization": get_key("pexels")}
        base = "https://api.pexels.com/v1/search" if kind == "photo" else "https://api.pexels.com/videos/search"
        url = f"{base}?query={qq}&per_page={per}" + (f"&orientation={orientation}" if orientation else "")
        return parse_pexels(http_json(url, h), kind)
    if source == "pixabay":
        key = get_key("pixabay")
        base = "https://pixabay.com/api/" if kind == "photo" else "https://pixabay.com/api/videos/"
        url = f"{base}?key={key}&q={qq}&per_page={max(per, 3)}&safesearch=true"
        if orientation in ("landscape", "portrait") and kind == "photo":
            url += "&orientation=" + ("horizontal" if orientation == "landscape" else "vertical")
        return parse_pixabay(http_json(url), kind)
    if source == "unsplash":
        h = {"Authorization": "Client-ID " + get_key("unsplash")}
        url = f"https://api.unsplash.com/search/photos?query={qq}&per_page={per}" + \
              (f"&orientation={'squarish' if orientation == 'square' else orientation}" if orientation else "")
        return parse_unsplash(http_json(url, h))
    if source == "wikimedia":
        ft = "filetype:video" if kind == "video" else "filetype:bitmap"
        return parse_wikimedia(http_json(wiki_url(f"gsrsearch={urllib.parse.quote(q + ' ' + ft)}&gsrlimit={per}")), kind)
    raise Usage(f"未知来源：{source}")


def wiki_url(extra, width=640):
    return ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
            if extra.startswith("gsr") else
            "https://commons.wikimedia.org/w/api.php?action=query&format=json") + \
        f"&{extra}&prop=imageinfo&iiprop=url|size|mime|extmetadata&iiurlwidth={width}"


def api_detail(source, id_, kind):
    if source == "pexels":
        h = {"Authorization": get_key("pexels")}
        url = f"https://api.pexels.com/v1/photos/{id_}" if kind == "photo" else f"https://api.pexels.com/videos/videos/{id_}"
        return parse_pexels_item(http_json(url, h), kind)
    if source == "pixabay":
        key = get_key("pixabay")
        base = "https://pixabay.com/api/" if kind == "photo" else "https://pixabay.com/api/videos/"
        hits = http_json(f"{base}?key={key}&id={id_}").get("hits", [])
        if not hits:
            raise Fail(f"Pixabay 找不到 {kind} id={id_}（照片与视频 id 分开，检查 --kind）")
        return parse_pixabay_item(hits[0], kind)
    if source == "unsplash":
        h = {"Authorization": "Client-ID " + get_key("unsplash")}
        return parse_unsplash_item(http_json(f"https://api.unsplash.com/photos/{id_}", h))
    if source == "wikimedia":
        res = parse_wikimedia(http_json(wiki_url(f"pageids={id_}", 3840)), kind, big_thumb=True)
        if not res:
            raise Fail(f"Wikimedia 找不到 {kind} pageid={id_}（或 mime 不符，检查 --kind）")
        return res[0]
    raise Usage(f"未知来源：{source}")


# ---------------------------------------------------------------- 打分

def score(c, min_width=1920, orientation="landscape", min_dur=None, per_source=12, allow_lowres=False):
    w, h = c.get("w") or 0, c.get("h") or 0
    s = 40 * min(w / min_width, 1.0) if min_width else 40
    if w < min_width and allow_lowres:
        s -= 15
    ref = {"landscape": 16 / 9, "portrait": 9 / 16, "square": 1.0}.get(orientation or "landscape", 16 / 9)
    weight = 20 if orientation else 10
    if w and h:
        s += weight * (1 - min(abs(w / h - ref) / ref, 1.0))
    if c["kind"] == "video":
        d = c.get("dur") or 0
        if min_dur:
            s += 15 if d >= min_dur else (15 * d / min_dur - 25)
        else:
            s += 15
    else:
        s += 15
    s += 25 * max(0.0, 1 - c.get("rank", 0) / max(per_source, 1))
    return round(s, 1)


def build_attribution(c):
    lic = c["license"]
    a = c.get("author") or "unknown"
    if c["source"] == "unsplash":
        return f"Photo by {a} on Unsplash"
    if c["source"] == "pexels":
        return f"{'Photo' if c['kind'] == 'photo' else 'Video'} by {a} on Pexels"
    if c["source"] == "pixabay":
        return f"{'Image' if c['kind'] == 'photo' else 'Video'} by {a} on Pixabay"
    return f'"{c.get("title") or c["id"]}" by {a}, {license_label(lic)}, via Wikimedia Commons'


# ---------------------------------------------------------------- 工程路径与记录

def slugify(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n] or "x"


def project_root(p):
    root = Path(p).resolve()
    if not root.is_dir():
        raise Usage(f"工程目录不存在：{root}")
    return root


def load_sources(root):
    f = root / "media" / "sources.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        return data
    except (ValueError, AssertionError):
        raise Usage(f"sources.json 不是有效的数组：{f}")


def save_sources(root, items):
    f = root / "media" / "sources.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_source(items, entry):
    for i, e in enumerate(items):
        if e.get("file") == entry["file"]:
            items[i] = entry
            return items
    items.append(entry)
    return items


# ---------------------------------------------------------------- ffmpeg

def need_ff():
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            raise Usage(f"找不到 {t}。请先安装 ffmpeg（macOS：brew install ffmpeg）。")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Fail(f"ffprobe 无法读取文件：{r.stderr.strip()[:200]}")
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise Fail("文件里没有视频流/图像流")
    fps = None
    try:
        n, m = v.get("avg_frame_rate", "0/0").split("/")
        fps = round(float(n) / float(m), 3) if float(m) else None
    except (ValueError, ZeroDivisionError):
        pass
    dur = None
    try:
        dur = round(float(d.get("format", {}).get("duration")), 3)
    except (TypeError, ValueError):
        pass
    return {"codec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"), "fps": fps, "dur": dur}


def transcode_video(src, dest, fps, keep_audio):
    vf = ("scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,"
          f"fps={fps},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-crf", "18",
           "-preset", "medium", "-movflags", "+faststart"]
    cmd += ["-c:a", "aac", "-b:a", "160k"] if keep_audio else ["-an"]
    r = subprocess.run(cmd + [str(dest)], capture_output=True, text=True)
    if r.returncode != 0:
        raise Fail(f"ffmpeg 转码失败：{r.stderr.strip()[:300]}")


def place_photo(src, dest_dir, stem):
    """jpg/png 原样保留，其他转 jpg（质量 92）。返回最终路径。"""
    codec = probe(src)["codec"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    if codec == "mjpeg":
        dest = dest_dir / f"{stem}.jpg"
        shutil.copyfile(src, dest)
    elif codec == "png":
        dest = dest_dir / f"{stem}.png"
        shutil.copyfile(src, dest)
    else:
        dest = dest_dir / f"{stem}.jpg"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-q:v", "2", "-update", "1", str(dest)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise Fail(f"图片转 jpg 失败：{r.stderr.strip()[:300]}")
    return dest


def choose_file(c):
    files = c.get("files") or []
    if not files:
        raise Fail(f"{c['key']} 没有可下载的文件")
    if c["kind"] == "photo":
        return files[0]
    good = [f for f in files if (f.get("w") or 0) >= 1920]
    if good:
        return min(good, key=lambda f: abs(f["w"] - 1920) + abs((f.get("h") or 1080) - 1080))
    print("提示：该视频没有宽度 >=1920 的版本，取最大可用版本。", file=sys.stderr)
    return max(files, key=lambda f: f.get("w") or 0)


def fetch_source_file(c, tmpdir):
    """下载来源原始文件，返回 (路径, src_sha256, 下载地址)。"""
    f = choose_file(c)
    url = f["url"]
    if c["source"] == "unsplash" and c.get("download_location"):  # API 规范：下载前先触发 download_location
        http_json(c["download_location"], {"Authorization": "Client-ID " + get_key("unsplash")})
    raw = Path(tmpdir) / "src.bin"
    sha = download(url, raw)
    return raw, sha, url


def make_final(c, raw, root, shot, stem, fps, keep_audio):
    out_dir = root / "public" / "media" / shot
    if c["kind"] == "video":
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{stem}.mp4"
        transcode_video(raw, dest, fps, keep_audio)
        return dest
    return place_photo(raw, out_dir, stem)


# ---------------------------------------------------------------- 子命令

def cmd_search(a):
    root = project_root(a.project)
    srcs = [s.strip() for s in a.sources.split(",") if s.strip()]
    bad = [s for s in srcs if s not in ALL_SOURCES]
    if bad:
        raise Usage(f"未知来源：{','.join(bad)}（可选 {','.join(ALL_SOURCES)}）")
    pool, filt = [], {"license": 0, "lowres": 0}
    for s in srcs:
        if s == "unsplash" and a.kind == "video":
            print("跳过 unsplash：它只有照片。")
            continue
        try:
            items = api_search(s, a.q, a.kind, None if a.orientation == "any" else a.orientation, a.per_source)
        except Usage as e:
            print(f"跳过 {s}：\n  " + str(e).replace("\n", "\n  "))
            continue
        except Fail as e:
            print(f"警告：{s} 搜索失败，已跳过：{e}")
            continue
        for c in items:
            if not license_ok(c["license"], a.allow_sa):
                filt["license"] += 1
            elif (c["w"] or 0) < a.min_width and not a.allow_lowres:
                filt["lowres"] += 1
            else:
                pool.append(c)
    for c in pool:
        c["score"] = score(c, a.min_width, None if a.orientation == "any" else a.orientation, a.min_dur, a.per_source, a.allow_lowres)
    pool.sort(key=lambda c: -c["score"])
    print(f"过滤：许可不合 {filt['license']} 条，分辨率低于 {a.min_width} 宽 {filt['lowres']} 条。")
    if not pool:
        raise Fail("没有符合条件的候选。可放宽 --min-width / --allow-lowres / --allow-sa，或换关键词、检查 Key 配置。")
    name = a.shot or slugify(a.q)
    out_dir = root / "media" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {"query": a.q, "kind": a.kind, "shot": a.shot or "", "generated": today(), "filtered": filt,
            "candidates": pool}
    (out_dir / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"{name}.html").write_text(render_html(data, root), encoding="utf-8")
    print(f"{'编号':<22}{'分':>6}  {'宽x高':<11}{'时长':>6}  {'许可':<12}{'作者':<18}页面")
    for c in pool[:a.per_source]:
        dur = f"{c['dur']:.0f}s" if c.get("dur") else "-"
        print(f"{c['key']:<22}{c['score']:>6}  {str(c['w'])+'x'+str(c['h']):<11}{dur:>6}  "
              f"{c['license']:<12}{c['author'][:16]:<18}{c['page_url']}")
    print(f"候选已写入：{out_dir / (name + '.json')}\n候选页：{out_dir / (name + '.html')}")
    if not a.no_sheet:
        try:
            build_sheet(root, name)
        except Fail as e:
            print(f"提示：{e}")


def compose_sheet(imgs, sheet, cols=4):
    """把若干图片缩放后平铺成一张联系表 jpg。"""
    rows = (len(imgs) + cols - 1) // cols
    args = ["ffmpeg", "-v", "error", "-y"]
    for d in imgs:
        args += ["-i", str(d)]
    fc = "".join(f"[{i}:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:color=0x202020,setsar=1[v{i}];"
                 for i in range(len(imgs)))
    fc += "".join(f"[v{i}]" for i in range(len(imgs))) + f"concat=n={len(imgs)}:v=1:a=0,tile={cols}x{rows}:padding=6:color=0xffffff"
    r = subprocess.run(args + ["-filter_complex", fc, "-frames:v", "1", str(sheet)], capture_output=True, text=True)
    if r.returncode != 0:
        raise Fail(f"联系表生成失败：{r.stderr.strip()[:200]}")


def build_sheet_files(root, files, name, cols=4):
    """用本地图片/视频（视频取第 1 秒的帧）拼联系表，打印「第 N 张 = 文件路径」。"""
    need_ff()
    out_dir = root / "media" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [Path(f).expanduser().resolve() for f in files]
    for p in paths:
        if not p.is_file():
            raise Usage(f"文件不存在：{p}")
    with tempfile.TemporaryDirectory() as td:
        imgs = []
        for i, p in enumerate(paths):
            if p.suffix.lower() in VIDEO_EXT:
                fr = Path(td) / f"f{i}.jpg"
                for ss in (["-ss", "1"], []):  # 不足 1 秒的视频退回第 1 帧
                    subprocess.run(["ffmpeg", "-y", "-v", "error", *ss, "-i", str(p), "-frames:v", "1", str(fr)],
                                   capture_output=True, text=True)
                    if fr.exists() and fr.stat().st_size > 0:
                        break
                if not fr.exists():
                    raise Fail(f"取不到视频帧：{p}")
                imgs.append(fr)
            else:
                imgs.append(p)
        sheet = out_dir / f"{name}_sheet.jpg"
        compose_sheet(imgs, sheet, cols)
    print(f"联系表：{sheet}（{cols} 列，从左到右、从上到下）")
    for i, p in enumerate(paths, 1):
        print(f"  第 {i:>2} 张 = {p}")
    return sheet


def build_sheet(root, name, top=12, cols=4):
    """把候选前 top 条的缩略图拼成一张联系表（从左到右、从上到下 = 排名顺序），供代理用视觉比较画面内容。"""
    out_dir = root / "media" / "candidates"
    cj = out_dir / f"{name}.json"
    if not cj.exists():
        raise Usage(f"{cj} 不存在，先跑 search。")
    pool = json.loads(cj.read_text(encoding="utf-8"))["candidates"][:top]
    tdir = out_dir / f"{name}_thumbs"
    tdir.mkdir(parents=True, exist_ok=True)
    got = []
    for c in pool:
        if not c.get("thumb"):
            continue
        dest = tdir / (re.sub(r"[^A-Za-z0-9_-]", "_", c["key"]) + ".jpg")
        try:
            if not dest.exists():
                download(c["thumb"], dest)
            got.append((c, dest))
        except Exception as e:  # 单张缩略图失败不影响其他
            print(f"  缩略图下载失败 {c['key']}：{e}", file=sys.stderr)
    if not got:
        raise Fail("没有可用的缩略图，联系表未生成；改看候选页。")
    sheet = out_dir / f"{name}_sheet.jpg"
    compose_sheet([d for _, d in got], sheet, cols)
    print(f"联系表：{sheet}（{cols} 列，从左到右、从上到下）")
    for i, (c, _) in enumerate(got, 1):
        print(f"  第 {i:>2} 张  {c['key']:<22} {c.get('title') or c['page_url'][-60:]}")
    return sheet


def cmd_sheet(a):
    if a.files:
        build_sheet_files(Path(a.project).resolve(), a.files, a.name, 4)
        return
    build_sheet(Path(a.project).resolve(), a.name, a.top)


def get_command(c, root, shot):
    parts = ["python3", str(Path(__file__).resolve()), "get", str(root), c["key"], "--kind", c["kind"]]
    if shot:
        parts += ["--shot", shot]
    parts += ["--picked-by", "user"]
    return " ".join(shlex.quote(p) for p in parts)


def render_html(data, root):
    cards = []
    for c in data["candidates"]:
        e = html.escape
        dur = f"{c['dur']:.0f}s" if c.get("dur") else "-"
        thumb = f'<img loading="lazy" src="{e(c["thumb"])}" alt="">' if c.get("thumb") else '<div class="nt">无预览图</div>'
        prev = f' · <a href="{e(c["preview_url"])}" target="_blank" rel="noopener">预览视频</a>' if c.get("preview_url") else ""
        cmd = get_command(c, root, data.get("shot"))
        cards.append(
            f'<div class="card"><a href="{e(c["page_url"])}" target="_blank" rel="noopener">{thumb}</a>'
            f'<div class="m"><b>{e(c["key"])}</b> <span class="sc">{c["score"]}</span><br>'
            f'{e(SRC_LABEL[c["source"]])} · {e(c["license"])}<br>作者：{e(c["author"] or "-")}<br>'
            f'{c["w"]}×{c["h"]} · {dur}<br><a href="{e(c["page_url"])}" target="_blank" rel="noopener">素材页</a>{prev}'
            f'<br><button data-cmd="{e(cmd, quote=True)}">复制下载命令</button></div></div>')
    title = html.escape(f'{data["query"]}（{data["kind"]}）')
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>候选素材 {title}</title>
<style>
:root{{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--card:#f4f4f6;--mut:#666;--ac:#2563eb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16161a;--fg:#eee;--card:#222228;--mut:#9a9aa6;--ac:#6ea0ff}}}}
body{{margin:0;padding:20px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
h1{{font-size:18px}} .g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}
.card{{background:var(--card);border-radius:8px;overflow:hidden}} .card img,.nt{{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}}
.nt{{display:grid;place-items:center;color:var(--mut)}} .m{{padding:10px;font-size:13px}} .sc{{color:var(--mut)}}
a{{color:var(--ac)}} button{{margin-top:6px;padding:4px 10px;cursor:pointer}}
</style></head><body>
<h1>候选素材：{title}</h1>
<p class="sc">生成于 {data["generated"]}，许可不合 {data["filtered"]["license"]} 条、低分辨率 {data["filtered"]["lowres"]} 条已过滤。下载时以来源详情页的许可为准。</p>
<div class="g">{"".join(cards)}</div>
<script>
document.querySelectorAll("button[data-cmd]").forEach(function(b){{b.onclick=function(){{
var t=b.dataset.cmd;function ok(){{b.textContent="已复制";setTimeout(function(){{b.textContent="复制下载命令"}},1500)}}
if(navigator.clipboard){{navigator.clipboard.writeText(t).then(ok)}}else{{var x=document.createElement("textarea");x.value=t;document.body.appendChild(x);x.select();document.execCommand("copy");x.remove();ok()}}
}}}});
</script></body></html>
"""


def today():
    return datetime.date.today().isoformat()


def parse_key(k):
    if ":" not in k:
        raise Usage(f"编号格式应为 source:id，收到 {k!r}")
    s, i = k.split(":", 1)
    if s not in ALL_SOURCES:
        raise Usage(f"未知来源 {s!r}（可选 {','.join(ALL_SOURCES)}）")
    return s, i


def cmd_get(a):
    need_ff()
    root = project_root(a.project)
    source, id_ = parse_key(a.key)
    if source == "unsplash" and a.kind == "video":
        raise Usage("Unsplash 只有照片。")
    c = api_detail(source, id_, a.kind)
    if not license_ok(c["license"], a.allow_sa):
        raise Fail(f"许可不合策略，拒绝：{c['key']} 的许可为 {c['license']}"
                   f"（{c.get('license_raw', '')}）。SA 许可可加 --allow-sa；NC/ND/未知不可用。")
    shot = a.shot or "misc"
    stem = a.name or slugify(f"{source}-{id_}")
    with tempfile.TemporaryDirectory() as td:
        raw, src_sha, dl_url = fetch_source_file(c, td)
        dest = make_final(c, raw, root, shot, stem, a.fps, a.keep_audio)
    info = probe(dest)
    query = ""
    cj = root / "media" / "candidates" / f"{a.shot or ''}.json"
    if a.shot and cj.exists():
        try:
            query = json.loads(cj.read_text(encoding="utf-8")).get("query", "")
        except ValueError:
            pass
    entry = {"file": dest.relative_to(root / "public").as_posix(), "kind": c["kind"], "source": source,
             "id": c["id"], "url": c["page_url"], "download_url": dl_url, "author": c["author"],
             "author_url": c["author_url"], "license": c["license"], "license_url": c["license_url"],
             "retrieved": today(), "src_sha256": src_sha, "sha256": sha256_file(dest), "w": info["w"],
             "h": info["h"], "dur": info["dur"] if c["kind"] == "video" else None,
             "fps": info["fps"] if c["kind"] == "video" else None, "shot": a.shot or "", "query": query,
             "picked_by": a.picked_by, "keep_audio": bool(a.keep_audio), "transcode_fps": a.fps,
             "attribution": build_attribution(c)}
    items = upsert_source(load_sources(root), entry)
    save_sources(root, items)
    print(f"已保存：{dest}\n{info['w']}x{info['h']} license={c['license']} sha256={entry['sha256'][:12]}…\n"
          f"记录：{root / 'media' / 'sources.json'}")


def cmd_import(a):
    need_ff()
    root = project_root(a.project)
    src = Path(a.file).expanduser().resolve()
    if not src.is_file():
        raise Usage(f"文件不存在：{src}")
    for k, v in (("--tool", a.tool), ("--prompt", a.prompt), ("--picked-by", a.picked_by)):
        if not (v or "").strip():
            raise Usage(f"{k} 不能为空（AI 生成素材无法复现，必须登记途径、提示词和挑选依据）")
    kind = a.kind or ("video" if src.suffix.lower() in VIDEO_EXT else "photo")
    shot = a.shot
    stem = a.name or slugify("gen-" + src.stem)
    gen_dir = root / "media" / "generated" / shot
    if kind == "video":
        gen_dir.mkdir(parents=True, exist_ok=True)
        dest = gen_dir / f"{stem}.mp4"
        transcode_video(src, dest, a.fps, a.keep_audio)
    else:
        dest = place_photo(src, gen_dir, stem)
    pub = root / "public" / "media" / shot / dest.name
    pub.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dest, pub)
    info = probe(dest)
    entry = {"file": pub.relative_to(root / "public").as_posix(), "kind": kind, "source": "generated",
             "license": "generated", "tool": a.tool, "model": a.model or "", "prompt": a.prompt,
             "generated_file": dest.relative_to(root).as_posix(), "retrieved": today(),
             "sha256": sha256_file(dest), "w": info["w"], "h": info["h"],
             "dur": info["dur"] if kind == "video" else None, "fps": info["fps"] if kind == "video" else None,
             "shot": shot, "picked_by": a.picked_by, "keep_audio": bool(a.keep_audio), "transcode_fps": a.fps,
             "attribution": f"AI 生成（{a.tool}）"}
    save_sources(root, upsert_source(load_sources(root), entry))
    print(f"已导入：入库副本 {dest}\n渲染副本 {pub}\n{info['w']}x{info['h']} license=generated "
          f"sha256={entry['sha256'][:12]}…\n记录：{root / 'media' / 'sources.json'}")


def fetch_generated(root, e, force):
    dest = root / "public" / e["file"]
    if dest.exists() and not force:
        return
    gf = e.get("generated_file")
    gp = root / gf if gf else None
    if not gp or not gp.is_file():
        raise Fail(f"{e['file']} 是 AI 生成素材，只能从入库副本复原，但 generated_file 缺失：{gf or '(未记录)'}。"
                   "无法重新生成，请从版本库找回 media/generated/ 下的文件。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(gp, dest)
    if sha256_file(dest) != e.get("sha256"):
        raise Fail(f"{e['file']} 入库副本 sha256 与记录不一致，副本可能被改动。")
    print(f"已复原：{e['file']}（从入库副本复制，sha256 一致）")


def cmd_fetch(a):
    need_ff()
    root = project_root(a.project)
    items = load_sources(root)
    if not items:
        print("sources.json 为空或不存在，无事可做。")
        return
    bad = 0
    for e in items:
        if e.get("source") == "generated":
            try:
                fetch_generated(root, e, a.all)
            except Fail as ex:
                print(f"错误：{ex}")
                bad += 1
            continue
        dest = root / "public" / e["file"]
        if dest.exists() and not a.all:
            continue
        kind = e.get("kind") or ("video" if dest.suffix.lower() in VIDEO_EXT else "photo")
        c = api_detail(e["source"], e["id"], kind)
        with tempfile.TemporaryDirectory() as td:
            raw, sha, _ = fetch_source_file(c, td)
            if sha != e["src_sha256"]:
                print(f"错误：{e['file']} 来源文件已变化（src_sha256 不一致），请核对后重新 get。")
                bad += 1
                continue
            if dest.exists():
                dest.unlink()
            shot = dest.parent.name
            made = make_final(c, raw, root, shot, dest.stem, e.get("transcode_fps") or 30, e.get("keep_audio", False))
        if made.resolve() != dest.resolve():
            print(f"警告：{e['file']} 复原后扩展名变为 {made.name}，请核对 sources.json。")
        if sha256_file(made) != e["sha256"]:
            print(f"警告：{e['file']} 最终 sha256 与记录不同（ffmpeg 版本不同可能导致，来源哈希已校验一致）。")
        else:
            print(f"已复原：{e['file']}（src_sha256 一致，sha256 一致）")
    if bad:
        raise Fail(f"{bad} 个素材无法复原或来源文件已变化。")


def cmd_credits(a):
    root = project_root(a.project)
    items = load_sources(root)
    if not items:
        raise Fail("sources.json 为空或不存在，没有可署名的素材。")
    need = [e for e in items if e["license"].startswith("cc-by") or e["license"] == "unsplash"]
    gen = [e for e in items if e.get("source") == "generated"]
    L = ["# 素材署名 CREDITS", ""]
    L.append("## 需要署名的素材")
    L.append("")
    if need:
        for e in need:
            L.append(f"- `{e['file']}`：{e['attribution']}（{e.get('url', '')}；{license_label(e['license'])}"
                     + (f" {e['license_url']}" if e.get("license_url") else "") + "）")
    else:
        L.append("（无）")
    L += ["", "## 全部素材来源", ""]
    for e in items:
        if e.get("source") == "generated":
            L.append(f"- `{e['file']}`：AI 生成 · {e.get('tool') or '-'}")
            continue
        L.append(f"- `{e['file']}`：{SRC_LABEL.get(e['source'], e['source'])} · {license_label(e['license'])} · "
                 f"{e.get('author') or '-'} · {e.get('url', '')}")
    if gen:
        L += ["", "## AI 生成", ""]
        for e in gen:
            L.append(f"- `{e['file']}`：途径 {e.get('tool') or '-'}；模型 {e.get('model') or '-'}")
    L += ["", "## 视频简介署名文字", "", "```"]
    lines = [e["attribution"] for e in need]
    if gen:
        lines.append("部分画面由 AI 生成。")
    L += lines or ["（无需署名）"]
    L += ["```", ""]
    out = root / "media" / "CREDITS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"已生成：{out}（需署名 {len(need)} 条，共 {len(items)} 条）")


def build_parser():
    ap = argparse.ArgumentParser(description="真实素材选材")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("project")
    s.add_argument("--q", required=True)
    s.add_argument("--kind", required=True, choices=["photo", "video"])
    s.add_argument("--sources", default=",".join(ALL_SOURCES))
    s.add_argument("--orientation", choices=["landscape", "portrait", "square", "any"], default="landscape",
                   help="默认 landscape（成片 16:9）；any 不按画幅过滤与加权")
    s.add_argument("--min-width", type=int, default=1920)
    s.add_argument("--min-dur", type=float)
    s.add_argument("--shot")
    s.add_argument("--per-source", type=int, default=12)
    s.add_argument("--allow-sa", action="store_true")
    s.add_argument("--allow-lowres", action="store_true")
    s.add_argument("--no-sheet", action="store_true", help="不生成缩略图联系表")
    sh = sub.add_parser("sheet")
    sh.add_argument("project")
    sh.add_argument("--name", required=True, help="search 时的 --shot，或关键词 slug；配合 --files 时是输出名")
    sh.add_argument("--files", nargs="+", help="用本地图片/视频拼联系表（不读候选 json）")
    sh.add_argument("--top", type=int, default=12)
    g = sub.add_parser("get")
    g.add_argument("project")
    g.add_argument("key")
    g.add_argument("--picked-by", required=True)
    g.add_argument("--kind", choices=["photo", "video"], default="photo")
    g.add_argument("--shot")
    g.add_argument("--name")
    g.add_argument("--fps", type=int, default=30)
    g.add_argument("--keep-audio", action="store_true")
    g.add_argument("--allow-sa", action="store_true")
    im = sub.add_parser("import")
    im.add_argument("project")
    im.add_argument("file")
    im.add_argument("--shot", required=True)
    im.add_argument("--tool", required=True, help="生成途径，如 gpt-image-2 skill、即梦网页、可灵网页")
    im.add_argument("--prompt", required=True)
    im.add_argument("--picked-by", required=True)
    im.add_argument("--model")
    im.add_argument("--name")
    im.add_argument("--kind", choices=["photo", "video"])
    im.add_argument("--fps", type=int, default=30)
    im.add_argument("--keep-audio", action="store_true")
    f = sub.add_parser("fetch")
    f.add_argument("project")
    f.add_argument("--all", action="store_true")
    c = sub.add_parser("credits")
    c.add_argument("project")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        {"search": cmd_search, "sheet": cmd_sheet, "get": cmd_get, "import": cmd_import, "fetch": cmd_fetch, "credits": cmd_credits}[a.cmd](a)
    except Fail as e:
        print(f"失败：{e}", file=sys.stderr)
        return 1
    except Usage as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
