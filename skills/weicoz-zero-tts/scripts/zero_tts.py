#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weicoz-zero-tts 语音合成客户端
调用基于 GPT-SoVITS api_v2 的远端 GPU 语音合成服务。
遵循开源零硬编码原则，服务端点由环境变量 ZERO_TTS_API_URL 驱动。
"""

import sys
import os
import getpass
import signal
import argparse
import tempfile
import subprocess
import json
import socket
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

# 远端模型/参考音频根路径（可通过环境变量自定义部署路径）
REMOTE_BASE = os.environ.get("ZERO_TTS_REMOTE_BASE", r"D:\TTS_GPT_SoVITS")

# 内置预设音色库
PRESET_VOICES = {
    "zhongli": {
        "name": "原神·钟离 (CV: 彭博)",
        "tag": "沉稳典雅 / 知识科普",
        "desc": "声线低沉温润，博古通今，适合深度知识讲解、历史文化、哲学评测与长篇叙事。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\zhongli\【默认】不用担心，我刚才看过周围，没有其他危险。.wav",
        "prompt": "不用担心，我刚才看过周围，没有其他危险。",
    },
    "neuvillette": {
        "name": "原神·那维莱特 (CV: 桑毓泽)",
        "tag": "端正严谨 / 规范解读",
        "desc": "庄重大气、条理极强，适合技术标准、行业规范、规则制度与法律条例解读。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\neuvillette\【默认】你们应该已经喝过名为「枫达」的饮料。实际上枫丹有许多饮品工厂，其中也有只提供纯净水的品牌。.wav",
        "prompt": "你们应该已经喝过名为「枫达」的饮料。实际上枫丹有许多饮品工厂，其中也有只提供纯净水的品牌。",
    },
    "alhaitham": {
        "name": "原神·艾尔海森 (CV: 杨超然)",
        "tag": "理性冷静 / 逻辑推演",
        "desc": "语调平稳干练，不带多余情绪，适合架构分析、算法逻辑推导与冷峻技术研判。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\alhaitham\【默认】卡维那家伙，说不定还会回来…啧，懒得讨论这些，要不还是换个地方吧。.wav",
        "prompt": "卡维那家伙，说不定还会回来…啧，懒得讨论这些，要不还是换个地方吧。",
    },
    "tighnari": {
        "name": "原神·提纳里 (CV: 莫然)",
        "tag": "敏锐清晰 / 自然科普",
        "desc": "清澈干脆、专业度高，适合自然生态、科学实验、学术问答与快速技能指导。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\tighnari\【默认】赤王的技术吧。遗留至今，竟然还有这种威能….wav",
        "prompt": "赤王的技术吧。遗留至今，竟然还有这种威能…",
    },
    "welt": {
        "name": "星穹铁道·瓦尔特 (CV: 彭博)",
        "tag": "成熟儒雅 / 宏大叙事",
        "desc": "长者风范、沉静博学，适合科技前沿、世界观解构、行业导师视角与深度访谈。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\welt\【中立】保持住这一本心，贯彻「探索」、「了解」、「建立」、「连结」的开拓之道吧。.wav",
        "prompt": "保持住这一本心，贯彻「探索」、「了解」、「建立」、「连结」的开拓之道吧。",
    },
    "dr_ratio": {
        "name": "星穹铁道·真理医生 (CV: 桑毓泽)",
        "tag": "锐利严苛 / 学术批判",
        "desc": "自信傲岸、语带锋芒，适合观点交锋、学术辨析、漏洞批判与硬核技术打假。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\dr_ratio\【中立】你知道对待穷途末路的猎物该怎么做么？——追逐，直至死地。.wav",
        "prompt": "你知道对待穷途末路的猎物该怎么做么？——追逐，直至死地。",
    },
    "ruan_mei": {
        "name": "星穹铁道·阮•梅 (CV: 张文钰)",
        "tag": "空灵淡雅 / 生命科学",
        "desc": "知性柔和、语调空灵，适合生命科学、前沿探索、知性散文与高雅美学解说。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\ruan_mei\【中立】在那里，一眼可以望见地平线尽头的恒星。.wav",
        "prompt": "在那里，一眼可以望见地平线尽头的恒星。",
    },
    "sunday": {
        "name": "星穹铁道·星期日 (CV: 徐翔)",
        "tag": "优美庄严 / 愿景阐述",
        "desc": "声线优美如诵诗，适合哲学思考、理念布道、蓝图宣讲与庄重开篇。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\sunday\【中立】如果这些还不够，就得劳烦你出手了。.wav",
        "prompt": "如果这些还不够，就得劳烦你出手了。",
    },
    "jingyuan": {
        "name": "星穹铁道·景元 (CV: 孙晔)",
        "tag": "闲适从容 / 战略漫谈",
        "desc": "松弛从容、大局在胸，适合商业战略、宏观趋势分析、职场漫谈与通透解构。",
        "ref": rf"{REMOTE_BASE}\models\voice_models\jingyuan\【中立】当年的驭空绝不是如今这般模样，案牍劳形，枯坐书斋。.wav",
        "prompt": "当年的驭空绝不是如今这般模样，案牍劳形，枯坐书斋。",
    },
    "lohen": {
        "name": "原神·洛恩 (CV: 林婧南 - 纯净干声)",
        "tag": "清朗自洽 / 青年独白",
        "desc": "自洽清朗、情绪真实，适合角色短剧、旁白讲述、青年自白与个性表达。",
        "ref": rf"{REMOTE_BASE}\ref_audio\lohen_clean_ref.wav",
        "prompt": "迟早的事而已，不如说能拖上这么久，已经算我们走运了。",
    },
    "mitya": {
        "name": "原神·米提亚 (CV: 苏尚卿)",
        "tag": "灵动朝气 / 少年冒险",
        "desc": "明快鲜活、少年感十足，适合轻快科技讲解、游戏解说与探险日常。",
        "ref": rf"{REMOTE_BASE}\ref_audio\mitya_studio_ref.wav",
        "prompt": "你去看剧院昨天的演出了吗？",
    },
    "news": {
        "name": "标准新闻播报",
        "tag": "端庄正式 / 资讯快报",
        "desc": "专业播音员腔调，适合每日资讯速递、官方通报与科技动态快讯。",
        "ref": rf"{REMOTE_BASE}\ref_audio\male_01_anchor.wav",
        "prompt": "各位观众晚上好，欢迎收看今天的整点新闻，接下来为您播报详细内容。",
    },
    "cinema": {
        "name": "磁性影视解说",
        "tag": "低沉磁性 / 影视旁白",
        "desc": "影视纪录片质感，适合悬疑故事、电影解说与人物传记。",
        "ref": rf"{REMOTE_BASE}\ref_audio\male_02_cinema.wav",
        "prompt": "夜幕降临，整座城市陷入了沉寂，而真正的故事才刚刚拉开序幕。",
    },
    "youth": {
        "name": "阳光清爽青年",
        "tag": "青春活力 / Vlog日常",
        "desc": "自然随性，适合个人生活分享、旅拍 Vlog 与亲切产品体验分享。",
        "ref": rf"{REMOTE_BASE}\ref_audio\male_03_youth.wav",
        "prompt": "今天天气真不错，趁着微风不燥，一起出门走走吹吹风吧！",
    },
    "story": {
        "name": "沧桑深度叙事",
        "tag": "深沉感人 / 历史岁月",
        "desc": "饱经风霜的叙事者音色，适合回忆录、深度历史专题与情感故事。",
        "ref": rf"{REMOTE_BASE}\ref_audio\male_05_deep.wav",
        "prompt": "时光流转，那些未曾说出口的往事，最终都在岁月里沉淀成了风景。",
    },
    "default": {
        "name": "通用标准播音 (云扬)",
        "tag": "平衡中立 / 通用合成",
        "desc": "中性标准男声，适合普通功能测试与中立文本播报。",
        "ref": rf"{REMOTE_BASE}\ref_audio\default.wav",
        "prompt": "你好，我是云扬。这是一段测试语音，我的声音主要用于新闻播报和科技解说。",
    }
}


# 内置音色的来源、性别与标签。标签依据角色设定与风格描述整理，不是逐条人工试听的结论。
_GI = "原神（米哈游）游戏角色语音"
_SR = "崩坏：星穹铁道（米哈游）游戏角色语音"
_LOCAL = "本地预置参考音频（来源未记录）"
BUILTIN_META = {
    "zhongli": {"source": _GI, "gender": "男", "tags": ["沉稳", "温润", "厚重", "偏沉"]},
    "neuvillette": {"source": _GI, "gender": "男", "tags": ["庄重", "清朗", "条理", "偏沉"]},
    "alhaitham": {"source": _GI, "gender": "男", "tags": ["冷静", "理性", "平稳"]},
    "tighnari": {"source": _GI, "gender": "男", "tags": ["清晰", "干脆", "专业", "自信"]},
    "welt": {"source": _SR, "gender": "男", "tags": ["儒雅", "沉静", "阅历", "偏闷"]},
    "dr_ratio": {"source": _SR, "gender": "男", "tags": ["锐利", "清晰", "批判", "自信"]},
    "ruan_mei": {"source": _SR, "gender": "女", "tags": ["空灵", "知性", "淡雅", "偏闷"]},
    "sunday": {"source": _SR, "gender": "男", "tags": ["清晰", "庄重", "规整", "有仪式感"]},
    "jingyuan": {"source": _SR, "gender": "男", "tags": ["闲适", "从容", "通透", "偏闷"]},
    "lohen": {"source": _GI, "gender": "女", "tags": ["清朗", "干净", "青年", "真实"]},
    "mitya": {"source": _GI, "gender": "男", "tags": ["明快", "少年", "活力", "⚠拖腔"]},
    "news": {"source": _LOCAL, "gender": "男", "tags": ["端庄", "播音", "匀速", "正式"]},
    "cinema": {"source": _LOCAL, "gender": "男", "tags": ["低沉", "磁性", "影视", "张力"]},
    "youth": {"source": _LOCAL, "gender": "男", "tags": ["清爽", "亲切", "口语", "活力"]},
    "story": {"source": _LOCAL, "gender": "男", "tags": ["沧桑", "深沉", "叙事", "颗粒感"]},
    "default": {"source": _LOCAL, "gender": "男", "tags": ["中性", "通用", "平衡"]},
}

# 内置 16 个音色的编号固定为 01–16。其余音色（用户追加的）存放在远端服务的音色库里，编号从 17 起；
# 客户端不保存也不安装任何音色文件，需要时向服务端要清单（--list-voices 或 /voices/ 试听页）。
BUILTIN = {}
for _n, (_key, _item) in enumerate(PRESET_VOICES.items(), 1):
    BUILTIN[_key] = {**_item, **BUILTIN_META.get(_key, {}), "number": _n}


def resolve_builtin(value):
    """-v 的值若是内置音色的别名或 1–16 的编号，返回别名；否则返回 None（交给服务端音色库解析）。"""
    value = str(value).strip()
    if value in BUILTIN:
        return value
    if value.isdigit():
        for key, item in BUILTIN.items():
            if item["number"] == int(value):
                return key
    return None


def get_endpoints(custom_url=None):
    """
    获取可用 TTS 服务端点列表。
    优先级：CLI 显式传入 > 环境变量 ZERO_TTS_API_URL > 本地回退 http://127.0.0.1:9880/tts
    """
    if custom_url:
        return [custom_url.strip()]

    env_urls = os.environ.get("ZERO_TTS_API_URL", "").strip()
    if env_urls:
        return [u.strip() for u in env_urls.split(",") if u.strip()]

    # 默认回环兜底
    return ["http://127.0.0.1:9880/tts"]


def is_endpoint_reachable(url, timeout=1.2):
    """快速探测端点 TCP 连通性，防止死等长超时"""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def ensure_service(endpoints, no_autostart=False):
    """所有端点都连不上时，按需通过 SSH 拉起远端服务（不依赖开机自启）。

    需设置 ZERO_TTS_SSH_HOST（~/.ssh/config 里的主机别名，可逗号分隔多个，按序尝试）。
    远端以计划任务 ZERO_TTS_START_TASK（默认 tts_qwen）启动服务；端口开始监听即视为就绪
    （服务在预热完成后才监听）。未配置 SSH 主机时直接跳过，保持原有行为。
    """
    if no_autostart or any(is_endpoint_reachable(ep) for ep in endpoints):
        return
    hosts = [h.strip() for h in os.environ.get("ZERO_TTS_SSH_HOST", "").split(",") if h.strip()]
    if not hosts:
        return
    task = os.environ.get("ZERO_TTS_START_TASK", "tts_qwen")
    wait = int(os.environ.get("ZERO_TTS_START_WAIT", "150"))
    for host in hosts:
        print(f"TTS 服务未运行，正在通过 SSH（{host}）启动任务 {task} ……", file=sys.stderr)
        try:
            r = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, f"schtasks /run /tn {task}"],
                capture_output=True, timeout=30)
        except Exception as e:
            print(f"  SSH 失败：{e}", file=sys.stderr)
            continue
        if r.returncode != 0:
            print(f"  启动命令返回 {r.returncode}，换下一台", file=sys.stderr)
            continue
        deadline = time.time() + wait
        while time.time() < deadline:
            if any(is_endpoint_reachable(ep) for ep in endpoints):
                print("TTS 服务已就绪。", file=sys.stderr)
                return
            time.sleep(3)
        print(f"  等待 {wait} 秒仍未就绪。", file=sys.stderr)


# ---------------------------------------------------------------------------
# 排队与插队
# 服务端（Qwen3-TTS 加速版）提供任务队列：/status 查状态，/jobs 排队并轮询。
# 同一时刻只合成一个任务，其余按先后顺序排队；只有 --force 才中断当前任务并插队。
# 不支持队列的引擎（GPT-SoVITS 备用）退化为本机文件锁排队。
# ---------------------------------------------------------------------------
EXIT_BUSY = 75          # --no-wait 且服务忙：未排队直接退出
EXIT_INTERRUPTED = 3    # 本任务被别人强制插队中断


class JobInterrupted(Exception):
    pass


class BusyExit(Exception):
    pass


def client_label():
    return os.environ.get("ZERO_TTS_CLIENT") or f"{getpass.getuser()}@{socket.gethostname()}:{os.getpid()}"


def base_url(ep):
    ep = ep.rstrip("/")
    return ep[:-4] if ep.endswith("/tts") else ep


def http_json(method, url, payload=None, headers=None, timeout=5):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    h = {"Content-Type": "application/json; charset=utf-8"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def http_json_retry(method, url, tries=5, timeout=15, **kw):
    """幂等请求（GET/DELETE）的重试：EasyTier 链路偶发卡顿超过 10 秒时，不应让已在服务端排队或完成的任务白白丢掉。"""
    last = None
    for i in range(tries):
        try:
            return http_json(method, url, timeout=timeout, **kw)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            time.sleep(min(2 * (i + 1), 8))
    raise RuntimeError(f"与服务连续 {tries} 次通信失败：{last}")


def get_status(ep):
    """查询服务队列状态；服务不支持队列（如 GPT-SoVITS）返回 None。"""
    try:
        st = http_json("GET", base_url(ep) + "/status", timeout=3)
        return st if "queue" in st else None
    except Exception:
        return None


def describe_status(st):
    if not st.get("busy"):
        return "空闲，没有任务在跑。"
    cur, q = st.get("current"), st.get("queue", [])
    lines = []
    if cur:
        lines.append(f"正在合成：{cur['client']}，{cur['chars']} 字，已运行 {cur['elapsed']:.0f} 秒（开头：{cur.get('preview', '')}…）")
    if q:
        lines.append(f"排队中 {len(q)} 个：" + "；".join(f"{x['client']}（{x['chars']}字，已等 {x['waited']:.0f}s）" for x in q))
    return "\n".join(lines)


def fetch_via_queue(ep, payload, args, st):
    base = base_url(ep)
    if st.get("busy"):
        if args.no_wait and not args.force:
            print("服务忙，未排队（--no-wait）。\n" + describe_status(st), file=sys.stderr)
            raise BusyExit()
        if not args.force:
            print("有任务在跑，进入排队等待。\n" + describe_status(st), file=sys.stderr)
        else:
            print("有任务在跑，--force：中断当前任务并插队。\n" + describe_status(st), file=sys.stderr)
    headers = {"X-Client": urllib.parse.quote(client_label(), safe="")}
    if args.force:
        headers["X-Priority"] = "force"
    job = http_json("POST", base + "/jobs", payload, headers, timeout=20)
    jid, last_pos = job["id"], None
    queue_wait = int(os.environ.get("ZERO_TTS_QUEUE_WAIT", "1800"))
    run_cap = max(args.timeout, 600)
    t_queue = time.time()
    t_run = None
    try:
        while True:
            v = http_json_retry("GET", f"{base}/jobs/{jid}")
            state = v["state"]
            if state == "done":
                last_dl = None
                for _ in range(4):  # 音频已在服务端，下载失败就重下，别重新合成
                    try:
                        with urllib.request.urlopen(f"{base}/jobs/{jid}/audio", timeout=60) as resp:
                            return resp.read()
                    except Exception as e:
                        last_dl = e
                        time.sleep(2)
                raise RuntimeError(f"音频已合成但下载失败：{last_dl}（任务号 {jid}，10 分钟内可重新下载）")
            if state == "cancelled":
                reason = v.get("reason") or ""
                if reason.startswith("interrupted_by:"):
                    print(f"本任务被 {reason.split(':', 1)[1]} 强制插队中断（已丢弃）。如仍需要请重新提交。", file=sys.stderr)
                else:
                    print(f"任务已取消：{reason}", file=sys.stderr)
                raise JobInterrupted()
            if state == "failed":
                raise RuntimeError(f"合成失败：{v.get('error')}")
            if state == "queued":
                if v["position"] != last_pos:
                    print(f"排队中：前面还有 {v['position'] - 1} 个任务。", file=sys.stderr)
                    last_pos = v["position"]
                if time.time() - t_queue > queue_wait:
                    http_json("DELETE", f"{base}/jobs/{jid}", timeout=5)
                    raise RuntimeError(f"排队超过 {queue_wait} 秒，已放弃（ZERO_TTS_QUEUE_WAIT 可调）")
            else:  # running
                if t_run is None:
                    t_run = time.time()
                    if last_pos is not None:
                        print("轮到本任务，开始合成。", file=sys.stderr)
                if time.time() - t_run > run_cap:
                    http_json("DELETE", f"{base}/jobs/{jid}", timeout=5)
                    raise RuntimeError(f"合成超过 {run_cap} 秒，已取消")
            time.sleep(2)
    except KeyboardInterrupt:
        try:
            http_json("DELETE", f"{base}/jobs/{jid}", timeout=5)
        except Exception:
            pass
        raise


def fetch_legacy(ep, req_data, args):
    """不支持队列的引擎：本机文件锁串行化，服务端自身处理同步请求。"""
    lock_f = None
    try:
        import fcntl
        lock_f = open(os.path.join(tempfile.gettempdir(), "zero_tts.lock"), "w")
        try:
            fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if args.no_wait:
                print("本机已有 zero_tts 在运行，未排队（--no-wait）。", file=sys.stderr)
                raise BusyExit()
            print("本机已有 zero_tts 在运行，排队等待……", file=sys.stderr)
            fcntl.flock(lock_f, fcntl.LOCK_EX)
    except ImportError:
        pass
    if args.force:
        print("该引擎不支持强制插队，已按排队处理。", file=sys.stderr)
    try:
        req = urllib.request.Request(ep, data=req_data, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            content = resp.read()
            if resp.status == 200 and len(content) > 1000:
                return content
            raise RuntimeError(f"HTTP {resp.status}: {content[:200].decode('utf-8', errors='ignore')}")
    finally:
        if lock_f:
            lock_f.close()


def play_audio(audio_path):
    """跨平台音频播放"""
    if sys.platform == "darwin":
        subprocess.run(["afplay", audio_path], check=False)
    elif sys.platform.startswith("linux"):
        for player in ["aplay", "paplay", "ffplay", "mpv"]:
            try:
                subprocess.run([player, audio_path], check=False)
                break
            except FileNotFoundError:
                continue
    elif sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(audio_path, winsound.SND_FILENAME)
        except Exception:
            pass


def pick_endpoint(args):
    """确保服务在运行（必要时自动拉起），返回第一个可连通端点的根地址；都连不上返回 None。"""
    eps = get_endpoints(args.api_url)
    ensure_service(eps, args.no_autostart)
    for ep in eps:
        if is_endpoint_reachable(ep, timeout=1.2):
            return base_url(ep).rstrip("/")
    return None


def server_call(args, method, path, body=None, timeout=60):
    """调用服务端音色库接口；失败时打印原因并退出。"""
    base = pick_endpoint(args)
    if base is None:
        print("错误：服务连不上。", file=sys.stderr)
        sys.exit(1)
    try:
        return http_json(method, base + path, payload=body, timeout=timeout)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or e.reason
        except Exception:
            msg = e.reason
        print(f"错误：{msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误：请求失败：{e}", file=sys.stderr)
        sys.exit(1)


def print_voices(args):
    """输出全部音色（编号、别名、性别、标签、来源）。优先取服务端音色库；连不上时只列内置 16 个。"""
    base = pick_endpoint(args)
    rows, offline = None, False
    if base:
        try:
            rows = http_json_retry("GET", base + "/voices/catalog.json", tries=3, timeout=10)
        except Exception:
            rows = None
    if rows is None:
        offline = True
        rows = [{"number": i["number"], "key": k, "name": i["name"], "gender": i.get("gender", ""),
                 "tags": i.get("tags", []), "source": i.get("source", ""), "note": ""} for k, i in BUILTIN.items()]
    print("=" * 78)
    print(f"weicoz-zero-tts 音色清单（共 {len(rows)} 个{'，服务连不上，仅内置' if offline else ''}）")
    print("=" * 78)
    for v in rows:
        print(f"{v['number']:02d}  {v['key']:<14} {v.get('gender', ''):<2} {' '.join(v.get('tags') or [])}"
              + (f"  ⚠{v['note']}" if v.get("note") else ""))
        print(f"    {v['name']}  |  来源：{v.get('source') or '未记录'}")
    print("=" * 78)
    print("提示：-v <别名或编号> 选音色；--voices-page 打开可试听、可筛选的页面。")


def find_voices_page(args):
    """找试听页地址。页面由常驻的轻量服务提供（默认端口 ZERO_TTS_PAGE_PORT=9881，不占显存、不随合成服务空闲退出）；
    它没运行时通过 SSH 拉起计划任务 ZERO_TTS_PAGE_TASK（默认 tts_voices_page）；仍不行再退回合成服务自带的页面。"""
    eps = get_endpoints(args.api_url)
    port = int(os.environ.get("ZERO_TTS_PAGE_PORT", "9881"))
    pages = []
    for ep in eps:
        u = urllib.parse.urlparse(ep)
        pages.append(f"{u.scheme}://{u.hostname}:{port}")

    def alive():
        return next((p for p in pages if is_endpoint_reachable(p, timeout=1.5)), None)

    hit = alive()
    hosts = [h.strip() for h in os.environ.get("ZERO_TTS_SSH_HOST", "").split(",") if h.strip()]
    if hit is None and hosts and not args.no_autostart:
        task = os.environ.get("ZERO_TTS_PAGE_TASK", "tts_voices_page")
        for host in hosts:
            print(f"试听页服务未运行，正在通过 SSH（{host}）启动任务 {task} ……", file=sys.stderr)
            try:
                r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
                                    f"schtasks /run /tn {task}"], capture_output=True, timeout=30)
            except Exception:
                continue
            if r.returncode != 0:
                continue
            for _ in range(10):
                hit = alive()
                if hit:
                    break
                time.sleep(2)
            if hit:
                break
    if hit:
        return hit + "/voices/"
    base = pick_endpoint(args)  # 退路：用合成服务自带的页面（会按需拉起合成服务）
    return base + "/voices/" if base else None


def run_admin(args):
    """音色库管理：新增、改标签、重建样板声。全部在远端服务完成，本机只上传参考音频。"""
    def tags_of(v):
        return [t.strip() for t in v.split(",") if t.strip()]

    if args.add_voice:
        if not (args.ref_file and args.prompt and args.name):
            print("错误：--add-voice 需要 --ref-file（本机 3–10 秒参考音频）、--prompt（音频逐字文本）、--name。", file=sys.stderr)
            sys.exit(2)
        import base64
        body = {"key": args.add_voice, "name": args.name, "prompt": args.prompt, "gender": args.gender or "",
                "tags": tags_of(args.tags or ""), "source": args.source or "", "note": args.note or "",
                "ref_wav_b64": base64.b64encode(Path(args.ref_file).read_bytes()).decode("ascii")}
        r = server_call(args, "POST", "/voices/admin/add", body)
        print(f"已新增音色 {r['key']}，编号 {r['number']:02d}，参考音频 {r['ref_seconds']} 秒。运行 --rebuild-voices 生成样板声。")
    elif args.update_voice:
        body = {"key": args.update_voice}
        for f, v in (("name", args.name), ("gender", args.gender), ("source", args.source), ("note", args.note),
                     ("prompt", args.prompt)):
            if v is not None:
                body[f] = v
        if args.tags is not None:
            body["tags"] = tags_of(args.tags)
        if len(body) == 1:
            print("错误：--update-voice 至少要给一个要改的字段（--name/--gender/--tags/--source/--note/--prompt）。", file=sys.stderr)
            sys.exit(2)
        r = server_call(args, "POST", "/voices/admin/update", body)
        print(f"已更新音色 {r['key']}。" + ("参考文本变了，需 --rebuild-voices 更新样板声。" if r.get("stale") else ""))
    elif args.rebuild_voices:
        body = {"force": args.force, "keys": tags_of(args.rebuild_keys or "")}
        r = server_call(args, "POST", "/voices/admin/rebuild", body)
        print(f"已开始重建样板声：待做 {r['total']} 个（走合成队列，不影响其他任务）。用 --rebuild-status 看进度。")
    elif args.rebuild_status:
        r = server_call(args, "GET", "/voices/admin/rebuild")
        state = "进行中" if r["running"] else "空闲"
        print(f"样板声重建：{state}，完成 {r['done']}/{r['total']}，当前 {r['current'] or '-'}，失败 {r['failed'] or '无'}")


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt()


def main():
    # 脚本或 Agent 超时通常发 SIGTERM：与 Ctrl-C 一样，主动把任务从服务端队列撤销
    signal.signal(signal.SIGTERM, _raise_interrupt)
    parser = argparse.ArgumentParser(
        description="weicoz-zero-tts: 基于 GPT-SoVITS api_v2 的语音合成客户端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 zero_tts.py "你好，世界！" -v zhongli
  python3 zero_tts.py "长篇技术讲解文本..." -v neuvillette -o explanation.wav
  cat article.txt | python3 zero_tts.py -v ruan_mei --no-play -o reading.wav
  python3 zero_tts.py --list-voices
        """
    )
    parser.add_argument("text", nargs="?", help="待合成文本（不传则尝试从标准输入 stdin 读取）")
    parser.add_argument("-o", "--output", help="输出音频路径 (.wav)；未指定时写入临时文件并自动播放")
    parser.add_argument("-v", "--voice", default=os.environ.get("ZERO_TTS_DEFAULT_VOICE", "sunday"),
                        help="音色别名或编号 (默认 sunday；用 --list-voices 查看)")
    parser.add_argument("--ref", help="自定义远端参考音频绝对路径 (覆盖预设)")
    parser.add_argument("--prompt", help="参考音频对齐文本 (覆盖预设)")
    parser.add_argument("--prompt-lang", default="zh", help="参考音频语言 (默认 zh)")
    parser.add_argument("--text-lang", default="zh", help="输入文本语言 (默认 zh)")
    parser.add_argument("--speed", type=float, default=1.0, help="语速倍率 0.5–2.0（默认 1.0；建议 0.8–1.25）。由服务端处理（Qwen 在服务端用 ffmpeg 变速，SoVITS 原生）")
    parser.add_argument("--split", default="cut5", choices=["cut0", "cut1", "cut2", "cut3", "cut4", "cut5"],
                        help="文本分句策略 (默认 cut5 按中英文标点拆分)")
    parser.add_argument("--clarity", action="store_true",
                        default=os.environ.get("ZERO_TTS_CLARITY", "") == "1",
                        help="服务端合成后做清晰化 EQ（可选，默认关闭；也可设环境变量 ZERO_TTS_CLARITY=1；SoVITS 备用引擎不支持）")
    parser.add_argument("--no-autostart", action="store_true",
                        help="服务未运行时不通过 SSH 自动启动（默认在设置了 ZERO_TTS_SSH_HOST 时自动启动）")
    parser.add_argument("--force", action="store_true",
                        help="强制中断当前正在合成的任务并插队（会丢弃别人的任务，仅在用户明确同意时使用）")
    parser.add_argument("--no-wait", action="store_true",
                        help="服务忙时不排队，直接以退出码 75 退出")
    parser.add_argument("--status", action="store_true", help="只查看服务当前是否有任务在跑、队列情况，然后退出")
    parser.add_argument("--no-play", action="store_true", help="不自动播放音频")
    parser.add_argument("--list-voices", action="store_true", help="列出全部预设音色清单")
    parser.add_argument("--add-voice", metavar="别名", help="新增音色（配合 --ref-file --prompt --name，可选 --gender --tags --source --note）")
    parser.add_argument("--update-voice", metavar="别名", help="修改音色的名称、标签、来源、备注或参考文本")
    parser.add_argument("--rebuild-voices", action="store_true", help="让服务端补合成缺少或过期的样板声（--force 全部重做）")
    parser.add_argument("--rebuild-keys", help="只重建这些别名的样板声，逗号分隔")
    parser.add_argument("--rebuild-status", action="store_true", help="查看样板声重建进度")
    parser.add_argument("--ref-file", help="本机参考音频文件，--add-voice 时上传到服务端（3–10 秒）")
    parser.add_argument("--name", help="音色显示名称")
    parser.add_argument("--gender", help="性别：男 / 女")
    parser.add_argument("--tags", help="标签，逗号分隔，如 冷静,清晰,清透")
    parser.add_argument("--source", help="音色来源说明")
    parser.add_argument("--note", help="备注或警示（页面上显示）")
    parser.add_argument("--voices-page", action="store_true",
                        help="打开远端服务托管的音色试听页（服务没运行会自动拉起），可试听与筛选")
    parser.add_argument("--api-url", help="显式指定服务端点 URL (覆盖环境变量 ZERO_TTS_API_URL)")
    parser.add_argument("--timeout", type=int, default=90, help="HTTP 请求超时秒数 (默认 90)")

    args = parser.parse_args()

    if args.list_voices:
        print_voices(args)
        sys.exit(0)

    if args.add_voice or args.update_voice or args.rebuild_voices or args.rebuild_status:
        run_admin(args)
        sys.exit(0)

    if args.voices_page:
        url = find_voices_page(args)
        if url is None:
            print("错误：试听页打不开（页面服务和合成服务都连不上）。", file=sys.stderr)
            sys.exit(1)
        print(url)
        if not os.environ.get("ZERO_TTS_NO_BROWSER"):
            import webbrowser
            webbrowser.open(url)
        sys.exit(0)

    if args.status:
        eps = get_endpoints(args.api_url)
        for ep in eps:
            if is_endpoint_reachable(ep, timeout=1.2):
                st = get_status(ep)
                print(f"端点 {ep}\n" + (describe_status(st) if st else "该引擎不提供队列状态（GPT-SoVITS 备用）。"))
                sys.exit(0)
        print("服务未运行（空闲 10 分钟会自动关闭，下次调用时自动启动）。")
        sys.exit(0)

    # 读取输入文本
    text = args.text
    if not text:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            parser.print_help()
            sys.exit(1)

    if not text.strip():
        print("错误：待合成文本不能为空。", file=sys.stderr)
        sys.exit(1)

    if not 0.5 <= args.speed <= 2.0:
        print(f"警告：语速 {args.speed} 超出 0.5–2.0，服务端会按边界值处理。", file=sys.stderr)

    # 解析音色：内置音色由客户端带参考音频；其余只带别名或编号，由服务端音色库解析
    bkey = resolve_builtin(args.voice)
    ref_audio, prompt_text = args.ref, args.prompt
    if not ref_audio and bkey:
        ref_audio = BUILTIN[bkey]["ref"]
        prompt_text = prompt_text or BUILTIN[bkey]["prompt"]

    payload = {
        "text": text,
        "text_lang": args.text_lang,
        "prompt_lang": args.prompt_lang,
        "speed_factor": args.speed,
        "text_split_method": args.split,
    }
    if ref_audio:
        payload["ref_audio_path"] = ref_audio
        payload["prompt_text"] = prompt_text or ""
    else:
        payload["voice"] = args.voice
    if args.clarity:
        payload["clarity"] = True

    req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoints = get_endpoints(args.api_url)
    ensure_service(endpoints, args.no_autostart)

    audio_bytes = None
    last_error = None

    # 链路偶发抖动（EasyTier 等）时 1.2 秒探测会误判；全部探不到就用更长超时再试几轮，再认定连不上
    alive = [ep for ep in endpoints if is_endpoint_reachable(ep, timeout=1.2)]
    for _ in range(3):
        if alive:
            break
        time.sleep(2)
        alive = [ep for ep in endpoints if is_endpoint_reachable(ep, timeout=4)]

    for ep in alive:
        try:
            st = get_status(ep)
            if st is None and not payload.get("ref_audio_path"):
                last_error = f"备用引擎（GPT-SoVITS）只支持内置音色 01–16，{args.voice!r} 需要主力 Qwen 服务"
                continue
            audio_bytes = fetch_via_queue(ep, payload, args, st) if st is not None else fetch_legacy(ep, req_data, args)
            if audio_bytes:
                break
        except BusyExit:
            sys.exit(EXIT_BUSY)
        except JobInterrupted:
            sys.exit(EXIT_INTERRUPTED)
        except KeyboardInterrupt:
            print("已中断，任务已从队列移除。", file=sys.stderr)
            sys.exit(130)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                body = json.loads(e.read().decode("utf-8"))
                detail = body.get("message") or body.get("error") or ""
            except Exception:
                pass
            if e.code == 400 and detail:  # 请求本身有问题（如音色不存在），换端点也一样，直接说明原因
                print(f"错误：服务拒绝了请求：{detail}。用 --list-voices 查看可用音色。", file=sys.stderr)
                sys.exit(2)
            last_error = f"HTTP {e.code} {detail}".strip()
            continue
        except Exception as e:
            last_error = str(e)
            continue

    if not audio_bytes:
        print("错误：无法连接 TTS 语音合成服务端点。", file=sys.stderr)
        print(f"尝试过的端点：{', '.join(endpoints)}", file=sys.stderr)
        if last_error:
            print(f"末次错误信息：{last_error}", file=sys.stderr)
        print("\n请检查：", file=sys.stderr)
        print("1. 远端 GPU 主机是否开机且已启动 api_v2 服务。", file=sys.stderr)
        print("2. 环境变量 ZERO_TTS_API_URL 是否正确配置：", file=sys.stderr)
        print("   export ZERO_TTS_API_URL=\"http://<远端IP>:9880/tts\"", file=sys.stderr)
        sys.exit(1)

    out_file = args.output
    is_temp = False
    if not out_file:
        fd, out_file = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        is_temp = True

    try:
        with open(out_file, "wb") as f:
            f.write(audio_bytes)

        if not args.no_play:
            play_audio(out_file)

        if not is_temp:
            print(f"音频合成成功，已保存至: {out_file}")
    finally:
        if is_temp:
            try:
                os.remove(out_file)
            except OSError:
                pass


if __name__ == "__main__":
    main()
