# -*- coding: utf-8 -*-
"""Qwen3-TTS (CUDA Graph 加速) 服务，接口兼容 GPT-SoVITS api_v2 的 POST /tts，可与 zero_tts.py 直接互换。"""
import asyncio, collections, io, os, re, threading, time, traceback, urllib.parse, uuid
import numpy as np, soundfile as sf, torch, uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from faster_qwen3_tts import FasterQwen3TTS

MODEL_DIR = os.environ.get("QWEN_TTS_MODEL", r"D:\TTS_Services\qwen3tts\model")
PORT = int(os.environ.get("QWEN_TTS_PORT", "9880"))
TEMPERATURE = float(os.environ.get("QWEN_TTS_TEMPERATURE", "0.9"))
TOP_K = int(os.environ.get("QWEN_TTS_TOP_K", "50"))
MAX_CHUNK = int(os.environ.get("QWEN_TTS_MAX_CHUNK", "70"))
IDLE_MIN = float(os.environ.get("QWEN_TTS_IDLE_MIN", "10"))  # 空闲多少分钟后自动退出并释放显存；0 表示常驻
GAP_SEC = float(os.environ.get("QWEN_TTS_GAP", "0.15"))
VOICES_SITE = os.environ.get("QWEN_TTS_VOICES_SITE", r"D:\TTS_Services\voices\site")  # 音色试听页与样板声目录
WARM_REF = os.environ.get("QWEN_TTS_WARM_REF", r"D:\TTS_GPT_SoVITS\models\voice_models\sunday\【中立】如果这些还不够，就得劳烦你出手了。.wav")
WARM_TXT = "如果这些还不够，就得劳烦你出手了。"
LANG = {"zh": "Chinese", "all_zh": "Chinese", "auto": "Chinese", "en": "English", "all_en": "English",
        "ja": "Japanese", "all_ja": "Japanese", "ko": "Korean", "all_ko": "Korean"}

HEARTBEAT_TIMEOUT = float(os.environ.get("QWEN_TTS_HEARTBEAT", "45"))  # 轮询任务的客户端超过这么多秒没动静，视为掉线并清理
RESULT_TTL = 600                                                      # 完成的任务结果保留秒数
cv = threading.Condition()
queue = collections.deque()   # 等待中的任务，队首先执行
jobs = {}                     # id -> Job
current = None                # 正在合成的任务
last_active = time.time()


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, payload, client, heartbeat):
        self.id = uuid.uuid4().hex[:8]
        self.payload, self.client, self.heartbeat = payload, client or "unknown", heartbeat
        self.state, self.reason, self.error, self.result = "queued", None, None, None
        self.created, self.started, self.finished = time.time(), None, None
        self.last_poll = self.created
        self.cancel = threading.Event()
        t = payload.get("text", "")
        self.chars, self.preview = len(t), t[:16]
model = None
app = FastAPI(title="qwen3-tts-fast")


def split_text(text, limit=MAX_CHUNK):
    """按句末标点切句，再把短句合并到不超过 limit 字；超长句按逗号再切。"""
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?；;\n])", text) if p.strip()]
    out = []
    for p in parts:
        if len(p) <= limit:
            out.append(p); continue
        sub = [s for s in re.split(r"(?<=[，,、：:])", p) if s]
        cur = ""
        for s in sub:
            if len(cur) + len(s) > limit and cur:
                out.append(cur); cur = s
            else:
                cur += s
        if cur:
            out.append(cur)
    merged, cur = [], ""
    for p in out:
        if cur and len(cur) + len(p) > limit:
            merged.append(cur); cur = p
        else:
            cur += p
    if cur:
        merged.append(cur)
    return merged or [text]


def synth(text, lang, ref, ref_text, cancel=None):
    chunks = split_text(text)
    audios, sr = [], 24000
    for c in chunks:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        wavs, sr = model.generate_voice_clone(
            text=c, language=lang, ref_audio=ref, ref_text=ref_text,
            max_new_tokens=min(2048, len(c) * 8 + 80), temperature=TEMPERATURE, top_k=TOP_K)
        audios.append(np.asarray(wavs[0], dtype=np.float32))
        audios.append(np.zeros(int(sr * GAP_SEC), dtype=np.float32))
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    audio = np.concatenate(audios[:-1]) if len(audios) > 1 else audios[0]
    buf = io.BytesIO(); sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue(), len(audio) / sr, len(chunks)


def parse(p):
    text = (p.get("text") or "").strip()
    ref, ref_text = p.get("ref_audio_path"), (p.get("prompt_text") or "").strip()
    if not text or not ref:
        return None, "text and ref_audio_path required"
    if not os.path.exists(ref):
        return None, f"ref_audio_path not found: {ref}"
    return (text, LANG.get((p.get("text_lang") or "zh").lower(), "Chinese"), ref, ref_text), None


def submit(payload, client, force, heartbeat):
    """入队。force=True 时排到队首，并中断正在合成的任务。"""
    global last_active
    j = Job(payload, client, heartbeat)
    with cv:
        jobs[j.id] = j
        if force:
            queue.appendleft(j)
            if current is not None:
                current.reason = f"interrupted_by:{j.client}"
                current.cancel.set()
        else:
            queue.append(j)
        last_active = time.time()
        cv.notify_all()
    return j


def cancel_job(j, reason):
    with cv:
        if j in queue:
            queue.remove(j)
            j.state, j.reason, j.finished = "cancelled", reason, time.time()
        elif current is j:
            j.reason = j.reason or reason
            j.cancel.set()
        cv.notify_all()


def view(j):
    with cv:
        pos = queue.index(j) + 1 if j in queue else 0
    now = time.time()
    return {"id": j.id, "state": j.state, "position": pos, "client": j.client, "chars": j.chars,
            "waited": round((j.started or now) - j.created, 1),
            "elapsed": round(now - j.started, 1) if j.started and not j.finished else None,
            "reason": j.reason, "error": j.error}


def reaper():
    """独立巡检线程（不能放在 worker 里：合成期间 worker 被占住，没人巡检）。
    清理掉线客户端的排队任务；取消掉线客户端正在合成的任务；清理过期结果。"""
    while True:
        time.sleep(1)
        now = time.time()
        with cv:
            for j in list(queue):
                if j.heartbeat and now - j.last_poll > HEARTBEAT_TIMEOUT:
                    queue.remove(j); j.state, j.reason, j.finished = "cancelled", "client_lost", now
                    print(f"[reap] 排队任务 {j.client} {j.chars}字 客户端掉线，已移出队列", flush=True)
            if current and current.heartbeat and not current.cancel.is_set() \
                    and now - current.last_poll > HEARTBEAT_TIMEOUT:
                current.reason = current.reason or "client_lost"; current.cancel.set()
                print(f"[reap] 正在合成的 {current.client} {current.chars}字 客户端掉线，取消合成", flush=True)
            for k, j in list(jobs.items()):
                if j.finished and now - j.finished > RESULT_TTL and j is not current:
                    del jobs[k]


def worker():
    global current, last_active
    while True:
        with cv:
            while not queue:
                cv.wait(timeout=1)
            j = queue.popleft()
            j.state, j.started, current = "running", time.time(), j
        parsed, _ = parse(j.payload)
        try:
            data, dur, n = synth(*parsed, cancel=j.cancel)
            j.result, j.state = data, "done"
            print(f"[tts] {j.client} {j.chars}字 {n}段 音频{dur:.1f}s 排队{j.started-j.created:.1f}s 合成{time.time()-j.started:.1f}s", flush=True)
        except Cancelled:
            j.state = "cancelled"; j.reason = j.reason or "cancelled"
            print(f"[cancel] {j.client} {j.chars}字 原因 {j.reason}", flush=True)
        except Exception as e:
            traceback.print_exc(); j.state, j.error = "failed", str(e)
        with cv:
            j.finished, current, last_active = time.time(), None, time.time()
            cv.notify_all()


def busy():
    with cv:
        return current is not None or bool(queue)


# ---- 音色试听页：GET /voices/ 打开页面，页内样板声走 /voices/demo/<文件> ----
def _touch():
    """浏览试听页也算使用，避免边听边被空闲退出打断。"""
    global last_active
    last_active = time.time()


@app.get("/voices")
def voices_redirect():
    return RedirectResponse("/voices/")


@app.get("/voices/")
def voices_index():
    _touch()
    f = os.path.join(VOICES_SITE, "index.html")
    if not os.path.isfile(f):
        return JSONResponse({"error": "试听页还没发布，在客户端运行 build_voice_page.py --publish"}, status_code=404)
    return FileResponse(f, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


@app.get("/voices/demo/{name}")
def voices_demo(name: str):
    _touch()
    if not re.fullmatch(r"[\w.\-]+\.m4a", name):
        return JSONResponse({"error": "bad name"}, status_code=400)
    f = os.path.join(VOICES_SITE, "demo", name)
    if not os.path.isfile(f):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(f, media_type="audio/mp4")


@app.get("/health")
def health():
    return {"engine": "qwen3-tts-0.6B-fast", "ready": model is not None, "busy": busy()}


@app.get("/status")
def status():
    now = time.time()
    with cv:
        cur = None
        if current:
            cur = {"id": current.id, "client": current.client, "chars": current.chars, "preview": current.preview,
                   "elapsed": round(now - current.started, 1)}
        q = [{"id": j.id, "client": j.client, "chars": j.chars, "waited": round(now - j.created, 1)} for j in queue]
    return {"engine": "qwen3-tts-0.6B-fast", "busy": cur is not None or bool(q), "current": cur,
            "queue": q, "queue_len": len(q)}


@app.post("/jobs")
async def create_job(req: Request):
    """排队协议：提交任务，返回任务号；客户端轮询 GET /jobs/{id}（同时充当心跳）。"""
    p = await req.json()
    parsed, err = parse(p)
    if err:
        return JSONResponse({"message": err}, status_code=400)
    j = submit(p, urllib.parse.unquote(req.headers.get("x-client") or ""), req.headers.get("x-priority") == "force", True)
    return view(j)


@app.get("/jobs/{jid}")
def job_state(jid: str):
    j = jobs.get(jid)
    if not j:
        return JSONResponse({"message": "job not found"}, status_code=404)
    j.last_poll = time.time()
    return view(j)


@app.get("/jobs/{jid}/audio")
def job_audio(jid: str):
    j = jobs.get(jid)
    if not j or j.state != "done" or j.result is None:
        return JSONResponse({"message": "audio not ready"}, status_code=404)
    j.last_poll = time.time()
    return Response(content=j.result, media_type="audio/wav")


@app.delete("/jobs/{jid}")
def job_delete(jid: str):
    j = jobs.get(jid)
    if not j:
        return JSONResponse({"message": "job not found"}, status_code=404)
    cancel_job(j, "client_cancel")
    return view(j)


@app.post("/tts")
async def tts(req: Request):
    """兼容 GPT-SoVITS api_v2 的同步接口：同样走队列（支持 X-Priority: force），连接断开则取消。"""
    try:
        p = await req.json()
        parsed, err = parse(p)
        if err:
            return JSONResponse({"message": err}, status_code=400)
        j = submit(p, (urllib.parse.unquote(req.headers.get("x-client") or "") or "legacy"), req.headers.get("x-priority") == "force", False)
        while j.state in ("queued", "running"):
            if await req.is_disconnected():
                cancel_job(j, "client_disconnected")
                return Response(status_code=499)
            await asyncio.sleep(0.3)
        if j.state == "done":
            return Response(content=j.result, media_type="audio/wav")
        if j.state == "cancelled":
            return JSONResponse({"message": "cancelled", "reason": j.reason}, status_code=409)
        return JSONResponse({"message": "tts failed", "Exception": j.error}, status_code=400)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"message": "tts failed", "Exception": str(e)}, status_code=400)


def idle_watch():
    """空闲超时自动退出，进程结束即释放全部显存；下次调用由客户端按需重新拉起。"""
    while True:
        time.sleep(15)
        if not busy() and time.time() - last_active > IDLE_MIN * 60:
            print(f"[idle] 空闲超过 {IDLE_MIN:g} 分钟，退出以释放显存", flush=True)
            os._exit(0)


if __name__ == "__main__":
    t0 = time.time()
    model = FasterQwen3TTS.from_pretrained(MODEL_DIR)
    model.warmup(prefill_len=100)
    if os.path.exists(WARM_REF):
        synth("先预热一下服务，保证第一个请求不用等待。", "Chinese", WARM_REF, WARM_TXT)
    print(f"[ready] 加载+预热 {time.time()-t0:.1f}s 显存 {torch.cuda.max_memory_allocated()/1e9:.2f}GB 端口 {PORT}", flush=True)
    last_active = time.time()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=reaper, daemon=True).start()
    if IDLE_MIN > 0:
        threading.Thread(target=idle_watch, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
