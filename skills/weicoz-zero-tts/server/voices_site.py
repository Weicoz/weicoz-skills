# -*- coding: utf-8 -*-
"""音色库与试听页，挂在 qwen_server 上，全部在远端完成，客户端只发请求。

目录（QWEN_TTS_VOICES_HOME，默认 D:\\TTS_Services\\voices）：
  registry.json   音色清单（顺序即编号：只在末尾追加，已有编号才不会变）
  ref\\<别名>.wav   新增音色的参考音频（3–10 秒）
  site\\demo\\<别名>.m4a  样板声；site\\cache.json  指标缓存

接口（都在 /voices 下）：
  GET  /voices/                  试听页（从 catalog.json 动态渲染，可筛选）
  GET  /voices/catalog.json      全部音色（编号、标签、来源、样板声、指标）
  GET  /voices/demo/<别名>.m4a   样板声
  POST /voices/admin/add         新增音色（可带参考音频 base64）
  POST /voices/admin/update      改名称/标签/来源/备注/参考文本
  POST /voices/admin/rebuild     后台补合成缺少的样板声（走合成队列，不抢占）
  GET  /voices/admin/rebuild     重建进度
"""
import base64, hashlib, io, json, os, re, subprocess, threading, time

import numpy as np
import soundfile as sf
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

HOME = os.environ.get("QWEN_TTS_VOICES_HOME", r"D:\TTS_Services\voices")
REGISTRY = os.path.join(HOME, "registry.json")
REF_DIR = os.path.join(HOME, "ref")
SITE = os.path.join(HOME, "site")
DEMO_DIR = os.path.join(SITE, "demo")
CACHE = os.path.join(SITE, "cache.json")
FFMPEG = os.environ.get("QWEN_TTS_FFMPEG", r"D:\TTS_Services\tools\ffmpeg\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")
DEMO_TEXT = os.environ.get(
    "QWEN_TTS_DEMO_TEXT",
    "大家好，今天我们来聊一聊，为什么同样的数据，换一个统计口径，结论就会完全不同。"
    "先看第一个例子：二零二四年，销售额同比增长百分之十二点五。")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,23}$")

_lock = threading.Lock()
_rebuild = {"running": False, "total": 0, "done": 0, "current": None, "failed": [], "started": None}


# ---------- 注册表 ----------
def load_registry():
    with _lock:
        try:
            with open(REGISTRY, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []


def save_registry(voices):
    os.makedirs(HOME, exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(voices, f, ensure_ascii=False, indent=1)
        os.replace(tmp, REGISTRY)


def get_voice(value):
    """按别名或编号找音色；找不到返回 None。"""
    voices = load_registry()
    value = str(value).strip()
    for v in voices:
        if v["key"] == value:
            return v
    if value.isdigit() and 1 <= int(value) <= len(voices):
        return voices[int(value) - 1]
    return None


def _cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _save_cache(c):
    os.makedirs(SITE, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)


def _sig(v):
    """参考音频、参考文本、样板句任一变化，旧样板声就算过期。"""
    return hashlib.sha1(f"{v['ref']}|{v['prompt']}|{DEMO_TEXT}".encode("utf-8")).hexdigest()[:12]


# ---------- 音频处理 ----------
def ffmpeg(args, data=None):
    return subprocess.run([FFMPEG, "-v", "error", "-y", *args], input=data, capture_output=True)


def hf_ratio(x, sr):
    """2–8kHz 占 80Hz 以上总能量的百分比，反映声音明亮程度（不等于清晰度）。"""
    spec = np.abs(np.fft.rfft(x)) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    total = spec[fr >= 80].sum()
    return round(float(spec[(fr >= 2000) & (fr <= 8000)].sum() / total * 100), 1) if total > 0 else None


def metrics_from_wav(wav_bytes):
    x, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return {"hf": hf_ratio(x, sr), "dur": round(len(x) / sr, 1)}


def voice_profile(wav_bytes):
    """逐句漂移检测用：音高中位数（自相关，60–320Hz）、频谱重心、时长。算法与 weicoz-video-shotcraft-patch 的 voice-consistency.py 原版一致。"""
    r = ffmpeg(["-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], data=wav_bytes)
    if r.returncode != 0 or not r.stdout:
        return None
    x = np.frombuffer(r.stdout, dtype=np.float32)
    sr, fl, hop = 16000, 640, 160
    gate = 0.1 * float(np.sqrt((x ** 2).mean()) or 1e-9)
    lo, hi = int(sr / 320), int(sr / 60)
    f0 = []
    for i in range(0, len(x) - fl, hop):
        f = x[i:i + fl] - x[i:i + fl].mean()
        if np.sqrt((f ** 2).mean()) < gate:
            continue
        ac = np.correlate(f, f, "full")[fl - 1:]
        ac = ac / (ac[0] + 1e-9)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.5:
            f0.append(sr / k)
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    return {"f0": float(np.median(f0)) if f0 else 0.0, "centroid": float((sp * fr).sum() / (sp.sum() + 1e-9)), "dur": len(x) / sr}


def metrics_from_file(path):
    r = ffmpeg(["-i", path, "-ac", "1", "-ar", "24000", "-f", "s16le", "-"])
    if r.returncode != 0 or not r.stdout:
        return {}
    x = np.frombuffer(r.stdout, dtype="<i2").astype("float32")
    return {"hf": hf_ratio(x, 24000), "dur": round(len(x) / 24000, 1)}


# ---------- 目录 ----------
def _group(source):
    if source.startswith("ElevenLabs"):
        return "ElevenLabs"
    if source.startswith("MiniMax"):
        return "MiniMax"
    if "原神" in source or "崩坏" in source:
        return "游戏角色"
    return "本地预置"


def catalog():
    voices, cache, out, dirty = load_registry(), _cache(), [], False
    for i, v in enumerate(voices, 1):
        f = os.path.join(DEMO_DIR, v["key"] + ".m4a")
        has = os.path.isfile(f)
        c = cache.get(v["key"], {})
        if has and "hf" not in c:
            c = {**c, **metrics_from_file(f)}
            cache[v["key"]] = c
            dirty = True
        out.append({
            "number": i, "key": v["key"], "name": v["name"], "gender": v.get("gender", ""),
            "tags": v.get("tags", []), "source": v.get("source", ""), "group": _group(v.get("source", "")),
            "note": v.get("note", ""), "demo": f"demo/{v['key']}.m4a" if has else "",
            "stale": bool(has and c.get("sig") != _sig(v)), "hf": c.get("hf"), "dur": c.get("dur"),
        })
    if dirty:
        _save_cache(cache)
    return out


# ---------- 重建样板声 ----------
def _rebuild_worker(submit, keys, force):
    voices = load_registry()
    cache = _cache()
    todo = []
    for v in voices:
        if keys and v["key"] not in keys:
            continue
        has = os.path.isfile(os.path.join(DEMO_DIR, v["key"] + ".m4a"))
        if force or not has or cache.get(v["key"], {}).get("sig") != _sig(v):
            todo.append(v)
    _rebuild.update(running=True, total=len(todo), done=0, failed=[], current=None, started=time.time())
    os.makedirs(DEMO_DIR, exist_ok=True)
    try:
        for v in todo:
            _rebuild["current"] = v["key"]
            j = submit({"text": DEMO_TEXT, "ref_audio_path": v["ref"], "prompt_text": v["prompt"], "text_lang": "zh"},
                       "voices-rebuild", False, False)
            while j.state in ("queued", "running"):
                time.sleep(0.5)
            if j.state != "done":
                _rebuild["failed"].append(v["key"])
                continue
            out = os.path.join(DEMO_DIR, v["key"] + ".m4a")
            r = ffmpeg(["-i", "pipe:0", "-ac", "1", "-c:a", "aac", "-b:a", "96k", out], j.result)
            if r.returncode != 0:
                _rebuild["failed"].append(v["key"])
                continue
            cache = _cache()
            cache[v["key"]] = {**metrics_from_wav(j.result), "sig": _sig(v)}
            _save_cache(cache)
            _rebuild["done"] += 1
    finally:
        _rebuild.update(running=False, current=None)
        print(f"[voices] 样板声重建结束：成功 {_rebuild['done']}/{_rebuild['total']}，失败 {_rebuild['failed']}", flush=True)


# ---------- 页面 ----------
PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>zero-tts 音色试听</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--mute:#667085;--line:#e4e7ec;--acc:#2563eb;--chip:#eef2ff;--chipfg:#3730a3;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--fg:#e8eaed;--mute:#98a2b3;--line:#262b36;--acc:#6ea0ff;--chip:#1f2745;--chipfg:#b9c6ff;--warn:#f59e0b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,"PingFang SC",system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mute);font-size:13px;margin-bottom:14px}
.bar{position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
input[type=search]{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font-size:15px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}
.chips b{font-size:12px;color:var(--mute);margin-right:2px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:2px 10px;font-size:12.5px;cursor:pointer}
.chip.on{background:var(--acc);border-color:var(--acc);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;margin-top:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.hd{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.no{font-size:20px;font-weight:700;color:var(--acc);min-width:34px}
.nm{font-weight:600}.key{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--mute)}
.tags{margin:6px 0}.tag{display:inline-block;background:var(--chip);color:var(--chipfg);border-radius:6px;padding:0 7px;font-size:12px;margin:0 4px 4px 0}
.src{color:var(--mute);font-size:12px;word-break:break-all}.warn{color:var(--warn);font-size:12px;margin-top:4px}
audio{width:100%;height:34px;margin-top:8px}
.ft{display:flex;justify-content:space-between;align-items:center;margin-top:6px;gap:8px}
button.cp{border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;padding:2px 8px;font-size:12px;cursor:pointer;font-family:ui-monospace,Menlo,monospace}
.m{color:var(--mute);font-size:12px}.none{padding:30px;text-align:center;color:var(--mute)}
</style></head><body><main>
<h1>zero-tts 音色试听</h1>
<div class="sub">共 <span id="n">…</span> 个音色 · 样板声是同一句话，由本服务用当前主力引擎合成 · 标签依据来源描述整理，不是逐条人工试听结论 · 高频占比＝2–8kHz 能量占比，反映声音明亮程度；低只说明偏柔和或低沉，不等于听不清，以耳朵为准</div>
<div class="bar"><input id="q" type="search" placeholder="搜索编号、别名、名称、标签、来源">
<div class="chips" id="fg"></div><div class="chips" id="fs"></div><div class="chips" id="ft"></div></div>
<div class="grid" id="grid"></div><div class="none" id="none" hidden>没有符合条件的音色</div>
<script>
let V=[];const st={g:null,s:null,t:null,q:""};const el=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const uniq=a=>[...new Set(a)];
function chips(box,label,vals,key){el(box).innerHTML="<b>"+label+"</b>";vals.forEach(v=>{const c=document.createElement("button");c.className="chip";c.textContent=v;c.onclick=()=>{st[key]=st[key]===v?null:v;render()};c.dataset.k=key;c.dataset.v=v;el(box).appendChild(c)})}
function render(){
  document.querySelectorAll(".chip").forEach(c=>c.classList.toggle("on",st[c.dataset.k]===c.dataset.v));
  const q=st.q.toLowerCase();
  const list=V.filter(v=>(!st.g||v.gender===st.g)&&(!st.s||v.group===st.s)&&(!st.t||v.tags.includes(st.t))&&
    (!q||(String(v.number)+" "+v.key+" "+v.name+" "+v.tags.join(" ")+" "+v.source).toLowerCase().includes(q)));
  el("grid").innerHTML=list.map(v=>`<div class="card"><div class="hd"><span class="no">${String(v.number).padStart(2,"0")}</span><span class="nm">${esc(v.name)}</span><span class="key">${esc(v.key)}</span></div>
  <div class="tags">${[v.gender,...v.tags].filter(Boolean).map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>
  <div class="src">来源：${esc(v.source||"未记录")}</div>${v.note?`<div class="warn">⚠ ${esc(v.note)}</div>`:""}
  ${v.demo?`<audio controls preload="none" src="${esc(v.demo)}?v=${v.hf}-${v.dur}"></audio>`:`<div class="m">暂无样板声（POST /voices/admin/rebuild 生成）</div>`}
  <div class="ft"><span class="m">${v.hf!=null?"高频 "+v.hf+"%":""}${v.dur?" · "+v.dur+"s":""}${v.stale?" · 样板声待更新":""}</span><button class="cp" data-k="${esc(v.key)}" title="复制命令参数">-v ${esc(v.key)}</button></div></div>`).join("");
  el("none").hidden=list.length>0;
  document.querySelectorAll(".cp").forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText("-v "+b.dataset.k);b.textContent="已复制";setTimeout(()=>b.textContent="-v "+b.dataset.k,900)});
}
fetch("catalog.json",{cache:"no-store"}).then(r=>r.json()).then(d=>{V=d;el("n").textContent=V.length;
  chips("fg","性别",uniq(V.map(v=>v.gender).filter(Boolean)),"g");
  chips("fs","来源",uniq(V.map(v=>v.group)),"s");
  const cnt=t=>V.filter(v=>v.tags.includes(t)).length;
  chips("ft","标签",uniq(V.flatMap(v=>v.tags)).sort((a,b)=>cnt(b)-cnt(a)),"t");render()});
el("q").oninput=e=>{st.q=e.target.value;render()};
</script></main></body></html>
"""


# ---------- 路由 ----------
def register(app, submit, touch):
    """submit：qwen_server 的入队函数，传 None 表示只读页面服务（不挂管理接口）；
    touch：刷新「最近使用」时间，避免边听边被空闲退出。"""

    @app.get("/voices")
    def voices_redirect():
        return RedirectResponse("/voices/")

    @app.get("/voices/")
    def voices_page():
        touch()
        return HTMLResponse(PAGE, headers={"Cache-Control": "no-cache"})

    @app.get("/voices/catalog.json")
    def voices_catalog():
        touch()
        return JSONResponse(catalog(), headers={"Cache-Control": "no-store"})

    @app.get("/voices/demo/{name}")
    def voices_demo(name: str):
        touch()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,23}\.m4a", name):
            return JSONResponse({"error": "bad name"}, status_code=400)
        f = os.path.join(DEMO_DIR, name)
        if not os.path.isfile(f):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(f, media_type="audio/mp4")

    @app.post("/voices/analyze")
    async def voices_analyze(request: Request):
        """逐句漂移检测：items=[{id, wav_b64}]，每批最多 40 条、单条 ≤8MB。只做计算，不用 GPU，常驻页面服务上也能用。"""
        touch()
        b = await request.json()
        items = b.get("items") or []
        if not isinstance(items, list) or not 1 <= len(items) <= 40:
            return JSONResponse({"error": "items 须为 1–40 条"}, status_code=400)
        out = {}
        for it in items:
            try:
                data = base64.b64decode(it.get("wav_b64", ""), validate=True)
            except Exception:
                return JSONResponse({"error": f"{it.get('id')}: wav_b64 无法解码"}, status_code=400)
            if not data or len(data) > 8 * 1024 * 1024:
                return JSONResponse({"error": f"{it.get('id')}: 音频为空或超过 8MB"}, status_code=400)
            out[str(it.get("id"))] = voice_profile(data)
        return JSONResponse(out)

    if submit is None:  # 只读页面服务：不提供需要合成队列的管理接口
        return

    @app.post("/voices/admin/add")
    async def voices_add(request: Request):
        touch()
        b = await request.json()
        key = str(b.get("key", "")).strip()
        if not KEY_RE.match(key):
            return JSONResponse({"error": "key 须为小写字母开头，只含小写字母、数字、下划线，2–24 位"}, status_code=400)
        voices = load_registry()
        if any(v["key"] == key for v in voices):
            return JSONResponse({"error": f"音色 {key} 已存在"}, status_code=409)
        prompt = str(b.get("prompt", "")).strip()
        if not prompt or not b.get("name"):
            return JSONResponse({"error": "name 与 prompt（参考音频逐字文本）必填"}, status_code=400)
        if b.get("ref_wav_b64"):
            os.makedirs(REF_DIR, exist_ok=True)
            ref = os.path.join(REF_DIR, key + ".wav")
            r = ffmpeg(["-i", "pipe:0", "-ac", "1", "-ar", "24000", ref], base64.b64decode(b["ref_wav_b64"]))
            if r.returncode != 0:
                return JSONResponse({"error": "参考音频无法解码：" + r.stderr.decode("utf-8", "ignore")[-200:]}, status_code=400)
        else:
            ref = str(b.get("ref", "")).strip()
            if not ref or not os.path.isfile(ref):
                return JSONResponse({"error": "需要 ref_wav_b64，或服务器上存在的 ref 路径"}, status_code=400)
        info = sf.info(ref)
        dur = info.frames / info.samplerate
        if not 3 <= dur <= 10:
            if b.get("ref_wav_b64"):
                os.remove(ref)
            return JSONResponse({"error": f"参考音频必须 3–10 秒，当前 {dur:.1f} 秒"}, status_code=400)
        v = {"key": key, "name": b["name"], "tag": " / ".join(b.get("tags", [])), "desc": b.get("desc", ""),
             "ref": ref, "prompt": prompt, "source": b.get("source", ""), "gender": b.get("gender", ""),
             "tags": b.get("tags", []), "note": b.get("note", "")}
        voices.append(v)
        save_registry(voices)
        return {"ok": True, "number": len(voices), "key": key, "ref_seconds": round(dur, 1),
                "next": "POST /voices/admin/rebuild 生成样板声"}

    @app.post("/voices/admin/update")
    async def voices_update(request: Request):
        touch()
        b = await request.json()
        voices = load_registry()
        for v in voices:
            if v["key"] == b.get("key"):
                for f in ("name", "gender", "tags", "source", "note", "prompt", "desc"):
                    if f in b:
                        v[f] = b[f]
                if "tags" in b:
                    v["tag"] = " / ".join(b["tags"])
                save_registry(voices)
                return {"ok": True, "key": v["key"], "stale": "prompt" in b}
        return JSONResponse({"error": f"找不到音色 {b.get('key')}"}, status_code=404)

    @app.post("/voices/admin/rebuild")
    async def voices_rebuild(request: Request):
        touch()
        try:
            b = await request.json()
        except ValueError:
            b = {}
        if _rebuild["running"]:
            return JSONResponse({"error": "正在重建", **_rebuild}, status_code=409)
        threading.Thread(target=_rebuild_worker, args=(submit, set(b.get("keys") or []), bool(b.get("force"))),
                         daemon=True).start()
        time.sleep(0.3)
        return {"ok": True, **_rebuild}

    @app.get("/voices/admin/rebuild")
    def voices_rebuild_status():
        touch()
        return _rebuild
