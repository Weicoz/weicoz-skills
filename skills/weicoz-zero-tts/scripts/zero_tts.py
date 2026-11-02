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


def apply_speed(path, speed):
    """用 ffmpeg atempo 做保持音高的变速（atempo 单级范围 0.5–2.0，超出会拆成多级）。
    Qwen3-TTS 没有语速参数，所以由客户端后处理；GPT-SoVITS 用服务端原生 speed_factor，不走这里。"""
    if abs(speed - 1.0) < 0.01:
        return
    sp = min(max(speed, 0.5), 2.0)
    if sp != speed:
        print(f"警告：语速 {speed} 超出 0.5–2.0，已按 {sp} 处理。", file=sys.stderr)
    tmp = path + ".speed.wav"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-af", f"atempo={sp}", tmp], check=True)
        os.replace(tmp, path)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"警告：变速失败，保留原语速（需要 ffmpeg）：{e}", file=sys.stderr)
        if os.path.exists(tmp):
            os.remove(tmp)


# 清晰化后处理：低切 90Hz、削 220/400Hz 闷音、提 3.2k/5.5k 咬字频段、轻压缩、响度归一、升到 48k。
# 实测同一句话，2–8kHz 能量占比由 ~10% 升到 ~35%，听感明显更清楚。
CLARITY_FILTER = (
    "highpass=f=90,"
    "equalizer=f=220:t=q:w=1.0:g=-4,equalizer=f=400:t=q:w=1.2:g=-2,"
    "equalizer=f=3200:t=q:w=0.9:g=5,equalizer=f=5500:t=q:w=0.9:g=3,"
    "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,"
    "loudnorm=I=-16:TP=-1.5:LRA=9"
)


def apply_clarity(path):
    """用 ffmpeg 原地做清晰化 EQ；缺 ffmpeg 时给出提示并保留原音频。"""
    tmp = path + ".clarity.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", path, "-af", CLARITY_FILTER, "-ar", "48000", tmp],
            check=True,
        )
        os.replace(tmp, path)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"警告：清晰化后处理失败，保留原音频（需要 ffmpeg）：{e}", file=sys.stderr)
        if os.path.exists(tmp):
            os.remove(tmp)


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


def print_voices():
    """输出所有可用音色预设"""
    print("=" * 72)
    print("weicoz-zero-tts 预设音色库清单")
    print("=" * 72)
    print(f"{'别名':<14} | {'角色名称':<24} | {'风格定位'}")
    print("-" * 72)
    for key, item in PRESET_VOICES.items():
        print(f"{key:<14} | {item['name']:<24} | {item['tag']}")
    print("=" * 72)
    print("提示：使用 -v <别名> 即可选用指定角色音色。")


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
                        choices=list(PRESET_VOICES.keys()), help="预设音色名称 (默认 sunday)")
    parser.add_argument("--ref", help="自定义远端参考音频绝对路径 (覆盖预设)")
    parser.add_argument("--prompt", help="参考音频对齐文本 (覆盖预设)")
    parser.add_argument("--prompt-lang", default="zh", help="参考音频语言 (默认 zh)")
    parser.add_argument("--text-lang", default="zh", help="输入文本语言 (默认 zh)")
    parser.add_argument("--speed", type=float, default=1.0, help="语速倍率 0.5–2.0（默认 1.0；建议 0.8–1.25）。SoVITS 由服务端原生处理；Qwen 由本机 ffmpeg 变速")
    parser.add_argument("--split", default="cut5", choices=["cut0", "cut1", "cut2", "cut3", "cut4", "cut5"],
                        help="文本分句策略 (默认 cut5 按中英文标点拆分)")
    parser.add_argument("--clarity", action="store_true",
                        default=os.environ.get("ZERO_TTS_CLARITY", "") == "1",
                        help="合成后用 ffmpeg 做清晰化 EQ（可选，默认关闭；也可设环境变量 ZERO_TTS_CLARITY=1）")
    parser.add_argument("--no-autostart", action="store_true",
                        help="服务未运行时不通过 SSH 自动启动（默认在设置了 ZERO_TTS_SSH_HOST 时自动启动）")
    parser.add_argument("--force", action="store_true",
                        help="强制中断当前正在合成的任务并插队（会丢弃别人的任务，仅在用户明确同意时使用）")
    parser.add_argument("--no-wait", action="store_true",
                        help="服务忙时不排队，直接以退出码 75 退出")
    parser.add_argument("--status", action="store_true", help="只查看服务当前是否有任务在跑、队列情况，然后退出")
    parser.add_argument("--no-play", action="store_true", help="不自动播放音频")
    parser.add_argument("--list-voices", action="store_true", help="列出全部预设音色清单")
    parser.add_argument("--api-url", help="显式指定服务端点 URL (覆盖环境变量 ZERO_TTS_API_URL)")
    parser.add_argument("--timeout", type=int, default=90, help="HTTP 请求超时秒数 (默认 90)")

    args = parser.parse_args()

    if args.list_voices:
        print_voices()
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

    # 解析音色与参考信息
    voice_cfg = PRESET_VOICES.get(args.voice, PRESET_VOICES["default"])
    ref_audio = args.ref or voice_cfg["ref"]
    prompt_text = args.prompt or voice_cfg["prompt"]

    payload = {
        "text": text,
        "text_lang": args.text_lang,
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": args.prompt_lang,
        "speed_factor": args.speed,
        "text_split_method": args.split,
    }

    req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoints = get_endpoints(args.api_url)
    ensure_service(endpoints, args.no_autostart)

    audio_bytes = None
    last_error = None
    need_client_speed = False

    for ep in endpoints:
        if not is_endpoint_reachable(ep, timeout=1.2):
            continue
        try:
            st = get_status(ep)
            need_client_speed = st is not None
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

        if need_client_speed:
            apply_speed(out_file, args.speed)

        if args.clarity:
            apply_clarity(out_file)

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
