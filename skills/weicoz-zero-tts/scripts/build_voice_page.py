#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 weicoz-zero-tts 音色试听页。

为 zero_tts.py 当前可用的每个音色（内置预设 + 用户音色文件）合成同一句样板声，
再生成带编号、标签、来源和筛选的单页 HTML，方便按场合挑选音色。

输出都放在 ZERO_TTS_HOME（默认 ~/.local/share/weicoz-zero-tts）：
  demo/NN_<别名>.m4a   样板声（已存在的会跳过，--force 重做）
  index.html           试听页

用法：
  python3 build_voice_page.py            # 补齐缺少的样板声并生成页面
  python3 build_voice_page.py --open     # 同时用浏览器打开
  python3 build_voice_page.py --force    # 全部样板声重新合成
  python3 build_voice_page.py --html-only
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zero_tts  # noqa: E402

DEMO_TEXT = os.environ.get(
    "ZERO_TTS_DEMO_TEXT",
    "大家好，今天我们来聊一聊，为什么同样的数据，换一个统计口径，结论就会完全不同。"
    "先看第一个例子：二零二四年，销售额同比增长百分之十二点五。",
)


def synth_demo(key, out_m4a):
    """调用客户端合成样板声并转成 m4a；成功返回 True。"""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "demo.wav"
        cmd = [sys.executable, str(Path(zero_tts.__file__)), DEMO_TEXT, "-v", key, "-o", str(wav), "--no-play"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not wav.exists():
            print(f"  合成失败 {key}：{(r.stdout + r.stderr).strip()[-200:]}", file=sys.stderr)
            return False
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1",
                        "-c:a", "aac", "-b:a", "96k", str(out_m4a)], check=True)
        return True


def _rms_db(path, filt):
    """用 ffmpeg 的 astats 取整段 RMS 电平（dB）；失败返回 None。"""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        f"{filt},astats=metadata=0:reset=0", "-f", "null", "-"],
                       capture_output=True, text=True)
    last = None
    for line in r.stderr.splitlines():
        if "RMS level dB" in line:
            last = line.split(":")[-1].strip()
    try:
        return float(last)
    except (TypeError, ValueError):
        return None


def _hf_ratio_numpy(audio_path):
    """FFT 精确算 2–8kHz 占 80Hz 以上总能量的百分比；没有 numpy 返回 None。"""
    try:
        import numpy as np
    except ImportError:
        return None
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio_path), "-ac", "1", "-ar", "24000",
                        "-f", "s16le", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    x = np.frombuffer(r.stdout, dtype="<i2").astype("float32")
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / 24000)
    total = spec[freqs >= 80].sum()
    if total <= 0:
        return None
    return round(float(spec[(freqs >= 2000) & (freqs <= 8000)].sum() / total * 100), 1)


def clarity_metrics(audio_path):
    """时长与 2–8kHz 能量占比（反映明亮程度，不直接等于清晰度）。
    优先用 numpy（与技能文档里的历史数字同口径）；没有 numpy 时退回 ffmpeg 滤波估算，
    数值每项约偏高 0.2–0.7，只适合看大致排序。"""
    out = {}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(audio_path)], capture_output=True, text=True)
    try:
        out["duration"] = round(float(r.stdout.strip()), 1)
    except ValueError:
        pass
    ratio = _hf_ratio_numpy(audio_path)
    if ratio is None:
        total = _rms_db(audio_path, "highpass=f=80")
        band = _rms_db(audio_path, "highpass=f=2000,lowpass=f=8000")
        if total is not None and band is not None:
            ratio = round(10 ** ((band - total) / 10) * 100, 1)
        out["estimated"] = True
    if ratio is not None:
        out["hf_ratio"] = ratio
    return out


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>zero-tts 音色试听</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--mute:#667085;--line:#e4e7ec;--acc:#2563eb;--chip:#eef2ff;--chipfg:#3730a3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--fg:#e8eaed;--mute:#98a2b3;--line:#262b36;--acc:#6ea0ff;--chip:#1f2745;--chipfg:#b9c6ff}}
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
.hd{display:flex;gap:10px;align-items:baseline}.no{font-size:20px;font-weight:700;color:var(--acc);min-width:34px}
.nm{font-weight:600}.key{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--mute)}
.tags{margin:6px 0}.tag{display:inline-block;background:var(--chip);color:var(--chipfg);border-radius:6px;padding:0 7px;font-size:12px;margin:0 4px 4px 0}
.src{color:var(--mute);font-size:12px;word-break:break-all}audio{width:100%;height:34px;margin-top:8px}
.ft{display:flex;justify-content:space-between;align-items:center;margin-top:6px;gap:8px}
button.cp{border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;padding:2px 8px;font-size:12px;cursor:pointer;font-family:ui-monospace,Menlo,monospace}
.m{color:var(--mute);font-size:12px}.none{padding:30px;text-align:center;color:var(--mute)}
</style></head><body><main>
<h1>zero-tts 音色试听</h1>
<div class="sub">共 <span id="n"></span> 个音色 · 所有样板声是同一句话，用当前主力引擎合成 · 标签依据来源描述整理，不是逐条人工试听结论 · 高频占比＝2–8kHz 能量占比，反映声音明亮程度；低只说明偏柔和或低沉，不等于听不清，以耳朵为准</div>
<div class="bar"><input id="q" type="search" placeholder="搜索编号、别名、名称、标签、来源">
<div class="chips" id="fg"></div><div class="chips" id="fs"></div><div class="chips" id="ft"></div></div>
<div class="grid" id="grid"></div><div class="none" id="none" hidden>没有符合条件的音色</div>
<script>
const V=__DATA__;
const st={g:null,s:null,t:null,q:""};
const el=id=>document.getElementById(id);
function chips(box,label,vals,key){el(box).innerHTML="<b>"+label+"</b>";vals.forEach(v=>{const c=document.createElement("button");c.className="chip";c.textContent=v;c.onclick=()=>{st[key]=st[key]===v?null:v;render()};c.dataset.k=key;c.dataset.v=v;el(box).appendChild(c)})}
const uniq=a=>[...new Set(a)];
chips("fg","性别",uniq(V.map(v=>v.gender).filter(Boolean)),"g");
chips("fs","来源",uniq(V.map(v=>v.group)),"s");
chips("ft","标签",uniq(V.flatMap(v=>v.tags)).sort((a,b)=>V.filter(v=>v.tags.includes(b)).length-V.filter(v=>v.tags.includes(a)).length),"t");
el("n").textContent=V.length;
function render(){
  document.querySelectorAll(".chip").forEach(c=>c.classList.toggle("on",st[c.dataset.k]===c.dataset.v));
  const q=st.q.toLowerCase();
  const list=V.filter(v=>(!st.g||v.gender===st.g)&&(!st.s||v.group===st.s)&&(!st.t||v.tags.includes(st.t))&&
    (!q||(String(v.number)+" "+v.key+" "+v.name+" "+v.tags.join(" ")+" "+v.source).toLowerCase().includes(q)));
  el("grid").innerHTML=list.map(v=>`<div class="card"><div class="hd"><span class="no">${String(v.number).padStart(2,"0")}</span><span class="nm">${v.name}</span><span class="key">${v.key}</span></div>
  <div class="tags">${[v.gender,...v.tags].filter(Boolean).map(t=>`<span class="tag">${t}</span>`).join("")}</div>
  <div class="src">来源：${v.source||"未记录"}</div>
  ${v.demo?`<audio controls preload="none" src="${v.demo}"></audio>`:`<div class="m">暂无样板声</div>`}
  <div class="ft"><span class="m">${v.hf!=null?"高频 "+v.hf+"%":""}${v.dur?" · "+v.dur+"s":""}</span><button class="cp" data-k="${v.key}" title="复制命令参数">-v ${v.key}</button></div></div>`).join("");
  el("none").hidden=list.length>0;
  document.querySelectorAll(".cp").forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText("-v "+b.dataset.k);b.textContent="已复制";setTimeout(()=>b.textContent="-v "+b.dataset.k,900)});
}
el("q").oninput=e=>{st.q=e.target.value;render()};
render();
</script></main></body></html>
"""


def group_of(item):
    s = item.get("source", "")
    if s.startswith("ElevenLabs"):
        return "ElevenLabs"
    if s.startswith("MiniMax"):
        return "MiniMax"
    if "原神" in s or "崩坏" in s:
        return "游戏角色"
    return "本地预置"


def publish(home):
    """用 scp 把 index.html 和 demo/*.m4a 传到远端服务的试听页目录。
    主机取自 ZERO_TTS_SSH_HOST（逗号分隔，按序尝试）；目录取自 ZERO_TTS_REMOTE_VOICES_DIR
    （默认 D:/TTS_Services/voices/site，需与服务端 QWEN_TTS_VOICES_SITE 一致）。"""
    hosts = [h.strip() for h in os.environ.get("ZERO_TTS_SSH_HOST", "").split(",") if h.strip()]
    if not hosts:
        print("错误：未设置 ZERO_TTS_SSH_HOST，无法上传。", file=sys.stderr)
        return False
    rdir = os.environ.get("ZERO_TTS_REMOTE_VOICES_DIR", "D:/TTS_Services/voices/site").rstrip("/")
    files = sorted((home / "demo").glob("*.m4a"))
    for host in hosts:
        mk = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                             f'pwsh -NoProfile -Command "New-Item -ItemType Directory -Force {rdir}/demo | Out-Null"'],
                            capture_output=True)
        if mk.returncode != 0:
            print(f"  {host} 连接或建目录失败，换下一台", file=sys.stderr)
            continue
        ok = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", str(home / "index.html"),
                             f"{host}:{rdir}/index.html"]).returncode == 0
        ok = ok and subprocess.run(["scp", "-q", "-o", "BatchMode=yes", *map(str, files),
                                    f"{host}:{rdir}/demo/"]).returncode == 0
        if ok:
            print(f"已发布到 {host}:{rdir}（页面 1 个、样板声 {len(files)} 个）")
            return True
        print(f"  {host} 上传失败，换下一台", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser(description="生成 zero-tts 音色试听页")
    ap.add_argument("--force", action="store_true", help="重新合成全部样板声")
    ap.add_argument("--html-only", action="store_true", help="不合成，只用已有样板声生成页面")
    ap.add_argument("--open", action="store_true", help="生成后用默认浏览器打开本机文件")
    ap.add_argument("--publish", action="store_true",
                    help="把页面和样板声上传到远端服务托管（需 ZERO_TTS_SSH_HOST），之后随时用 zero_tts.py --voices-page 打开")
    args = ap.parse_args()

    home = zero_tts.VOICES_HOME
    demo_dir = home / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    failed = []
    for key, item in zero_tts.VOICES.items():
        m4a = demo_dir / f"{item['number']:02d}_{key}.m4a"
        if not args.html_only and (args.force or not m4a.exists()):
            print(f"合成样板声 {item['number']:02d} {key} ……", flush=True)
            if not synth_demo(key, m4a):
                failed.append(key)
        metrics = {}
        if m4a.exists():
            cache = m4a.with_suffix(".json")
            if cache.exists() and cache.stat().st_mtime >= m4a.stat().st_mtime:
                metrics = json.loads(cache.read_text(encoding="utf-8"))
            if "hf_ratio" not in metrics or (metrics.get("estimated") and _hf_ratio_numpy(m4a) is not None):
                metrics = clarity_metrics(m4a)
                cache.write_text(json.dumps(metrics), encoding="utf-8")
        rows.append({
            "number": item["number"], "key": key, "name": item["name"], "gender": item.get("gender", ""),
            "tags": item.get("tags") or [], "source": item.get("source", ""), "group": group_of(item),
            "demo": f"demo/{m4a.name}" if m4a.exists() else "",
            "hf": metrics.get("hf_ratio"), "dur": metrics.get("duration"),
        })

    out = home / "index.html"
    out.write_text(PAGE.replace("__DATA__", json.dumps(rows, ensure_ascii=False)), encoding="utf-8")
    print(f"已生成 {out}（{len(rows)} 个音色，样板声失败 {len(failed)} 个：{failed or '无'}）")
    if args.publish and not publish(home):
        sys.exit(1)
    if args.open:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(out)])


if __name__ == "__main__":
    main()
