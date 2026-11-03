---
name: weicoz-zero-tts
version: 1.5.0
description: >
  远端 GPU (GPT-SoVITS) 语音合成：将中文或中英混合文本合成为自然流畅的语音音频（WAV），
  内置 16 套原神/星铁等知识讲解与角色音色预设，可经 voices.json 扩展并生成带编号标签的试听页（钟离/那维莱特/艾尔海森/提纳里/瓦尔特/
  真理医生/阮•梅/星期日/景元等）、远端参考音频与 Prompt 驱动、长文本切分与局域网/
  内网穿透多端点自适应回退。适用于"文本转语音""配音""朗读""生成解说音频""听听这段话""TTS"等场景。
---

# 远端 GPU 语音合成 (weicoz-zero-tts)

调用配置有 GPU（如 RTX 3050）的远端 Windows 工作站上运行的 GPT-SoVITS `api_v2` 服务，快速将文本合成高保真、低延迟的 WAV 语音。

本项目遵循开源合规标准，**严禁硬编码任何私有 IP、端口或系统用户名**，全部端点连接均由环境变量驱动。

---

## 1. 环境变量配置

在启动终端或系统 Profile（如 `~/.zshrc` 或 `~/.bashrc`）中配置：

```bash
# 语音合成服务端点列表（支持单个 URL 或逗号分隔的多个备用端点，优先使用首个可用端点）
export ZERO_TTS_API_URL="http://gpu-server.local:9880/tts,http://vpn-node.internal:9880/tts"

# 按需自动启动（可选）：~/.ssh/config 里的远端主机别名，可逗号分隔多个。
# 服务没运行时，客户端自动 SSH 触发远端计划任务 ZERO_TTS_START_TASK（默认 tts_qwen），等就绪再合成。
# 不设置则保持原行为（连不上直接报错）。
export ZERO_TTS_SSH_HOST="gpu-server-ssh-alias"

# 默认音色预设（可选，留空默认 sunday）
export ZERO_TTS_DEFAULT_VOICE="sunday"

# 远端工作站模型根路径（可选，未设置时默认 D:\TTS_GPT_SoVITS）
export ZERO_TTS_REMOTE_BASE="D:\\TTS_GPT_SoVITS"
```

> **未配置端点时的兜底机制**：
> 若未设置 `ZERO_TTS_API_URL`，脚本自动回退至本地回环地址 `http://127.0.0.1:9880/tts`；连接失败时会输出格式友好的配置指引，不会静默崩溃。

---

## 2. 预设音色库速查

内置 16 套精选音色，运行 `python3 scripts/zero_tts.py --list-voices` 随时查看：

| 预设别名 (`-v`) | 角色名称 | 风格定位 | 最优应用场景 |
| :--- | :--- | :--- | :--- |
| `zhongli` | 原神·钟离 (CV: 彭博) | 沉稳典雅 / 知识科普 | **深度知识讲解、历史人文、长文评测、沉稳解说** |
| `neuvillette` | 原神·那维莱特 (CV: 桑毓泽) | 端正严谨 / 规范解读 | **技术规范、标准制度、法律条例、条理化说明** |
| `alhaitham` | 原神·艾尔海森 (CV: 杨超然) | 理性冷静 / 逻辑推演 | **系统架构设计、算法推演、冷峻研判、逻辑分析** |
| `tighnari` | 原神·提纳里 (CV: 莫然) | 敏锐清晰 / 自然科普 | **自然生态科普、科学实验、学术问答、技术教程** |
| `welt` | 星铁·瓦尔特 (CV: 彭博) | 成熟儒雅 / 宏大叙事 | **宏大世界观、前沿科学纵览、行业导师视角** |
| `dr_ratio` | 星铁·真理医生 (CV: 桑毓泽) | 锐利严苛 / 学术批判 | **学术辨析、硬核打假、代码审阅批判、观点交锋** |
| `ruan_mei` | 星铁·阮•梅 (CV: 张文钰) | 空灵淡雅 / 生命科学 | **生命科学、美学散文、知性娓娓道来、前沿探索** |
| `sunday` | 星铁·星期日 (CV: 徐翔) | 优美庄严 / 愿景阐述 | **哲学思辨、愿景阐述、宏伟蓝图、庄重演讲 (推荐默认)** |
| `jingyuan` | 星铁·景元 (CV: 孙晔) | 闲适从容 / 战略漫谈 | **宏观战略、商业模式漫谈、通透解构、闲话复盘** |
| `lohen` | 原神·洛恩 (CV: 林婧南) | 清朗自洽 / 青年独白 | **角色短剧、旁白独白、青年自白、纯净干声** |
| `mitya` | 原神·米提亚 (CV: 苏尚卿) | 灵动朝气 / 少年冒险 | **轻快科技开箱、游戏解说、冒险日常、趣味科普** |
| `news` | 标准新闻播报 | 端庄正式 / 资讯快报 | **每日快报、简讯、官方播报** |
| `cinema` | 磁性影视解说 | 低沉磁性 / 影视旁白 | **电影解说、悬疑案件、传记旁白** |
| `youth` | 阳光清爽青年 | 青春活力 / Vlog日常 | **Vlog、生活日常、产品上手体验** |
| `story` | 沧桑深度叙事 | 深沉感人 / 历史岁月 | **情感独白、往事回忆、怀旧专题** |
| `default` | 通用标准播音 (云扬) | 平衡中立 / 通用合成 | **中性标准男声、功能测试** |

详细音色特质与参考文本见 `references/voices.md`。

---

### 2.1 音色编号、试听页与扩展音色

- 每个音色有**编号**（内置 01–16，用户音色接在后面）和别名。`-v` 两种写法都行：`-v sunday` 或 `-v 8`。`--list-voices` 输出编号、别名、性别、标签、来源。
- **试听页由远端服务托管**：`python3 scripts/zero_tts.py --voices-page` 打开 `http://<服务>/voices/`（服务没运行会自动拉起）。页面给每个音色一条同一句话的样板声，带编号、标签（冷静、清晰、清透……）、来源、高频占比（2–8kHz，反映明亮程度，低不等于听不清）、搜索与按性别/来源/标签筛选，页内按钮可复制 `-v 别名`。
- **新增或改过音色后重新发布**：`python3 scripts/build_voice_page.py --publish`（只补缺少的样板声，`--force` 全部重做，`--html-only` 只重排页面，`--open` 打开本机副本）。`--publish` 用 scp 传到远端 `ZERO_TTS_REMOTE_VOICES_DIR`（默认 `D:/TTS_Services/voices/site`，须与服务端 `QWEN_TTS_VOICES_SITE` 一致）。装了 numpy 时清晰度数值与历史数字同口径；没有则用 ffmpeg 估算，每项约偏高 0.2–0.7。只有 Qwen 主力服务托管页面，GPT-SoVITS 备用引擎没有这个路由。
- **扩展音色**写在 `$ZERO_TTS_HOME/voices.json`，格式 `{"别名": {"name", "ref"(远端参考音频绝对路径), "prompt"(参考音频逐字文本), "tags", "gender", "source"}}`。只在文件末尾追加，已有编号才不会变。参考音频须 3–10 秒，`prompt` 必须与音频内容逐字一致（见 4.1）。
- **标签依据来源方的描述和风格整理，不是逐条人工试听的结论**；觉得不准直接改 `voices.json` 里的 `tags` 再重跑 `--html-only`。
- 第三方平台声音库（ElevenLabs、MiniMax）的音色只作个人使用，来源写在 `source` 字段；它们的参考音频和样板声不得提交进仓库。

---

## 3. 命令行调用方式

脚本位于 `scripts/zero_tts.py`。

### 3.1 基础调用（合成并自动播放）
```bash
python3 scripts/zero_tts.py "在这个快节奏的时代，或许我们都需要这样一份难得的松弛感。" -v zhongli
```

### 3.2 保存音频到指定文件（不自动播放）
```bash
python3 scripts/zero_tts.py "本次系统升级共包含三项重大改动..." -v neuvillette -o output/briefing.wav --no-play
```

### 3.3 管道流式输入长文本
```bash
cat article.txt | python3 scripts/zero_tts.py -v ruan_mei -o output/reading.wav
```

### 3.4 调整语速
```bash
python3 scripts/zero_tts.py "快速播报一段要闻..." --speed 1.15
```
- 范围 0.5–2.0，建议 0.8–1.25（超出会警告并钳制）。
- **Qwen3-TTS 没有原生语速参数**，由客户端用本机 `ffmpeg atempo` 做保持音高的变速（需本机装有 ffmpeg）；GPT-SoVITS 备用引擎由服务端原生处理。
- 变速本身精确（时长误差 <1%），但模型每次采样的自然时长有约 ±10% 的波动，所以成片时长不能只靠倍率预测。需要精确时长时，用 `weicoz-video-shotcraft-patch` 的 `calibrate-voice.py` 实测校准。

### 3.4b 排队与插队（执行前必看）
服务同一时刻只合成一个任务，**其余自动排队（先进先出）**。多个会话、多个 Agent 共用同一台 GPU 时尤其重要。

```bash
python3 scripts/zero_tts.py --status                 # 先看：有没有任务在跑、谁在排队
python3 scripts/zero_tts.py "..." -v sunday           # 默认：忙就排队，显示"前面还有 N 个"，轮到再合成
python3 scripts/zero_tts.py "..." --no-wait           # 忙就直接退出（退出码 75），不排队
python3 scripts/zero_tts.py "..." --force             # 中断当前任务并插队（别人的任务会被丢弃）
```

给 Agent 的规则：
1. **执行前先 `--status`**。有任务在跑，就按默认排队等待，不要绕开。
2. **不得自行使用 `--force`**。它会丢弃别人正在合成的任务；只在用户明确说"插队 / 强制 / 打断当前任务"时才用。
3. 退出码：`75` 服务忙且指定了 `--no-wait`；`3` 本任务被别人 `--force` 中断（告知用户，不要自动再 `--force` 抢回来）；`130` 被 Ctrl-C/SIGTERM 取消。
4. 中断粒度是"一个句段"（几秒）。排队中的客户端被取消或掉线，服务端会自动移出队列；合成中的客户端掉线，服务端会中途取消，不白跑。
5. 环境变量：`ZERO_TTS_QUEUE_WAIT`（最长排队秒数，默认 1800）、`ZERO_TTS_CLIENT`（队列里显示的客户端名，默认 `用户@主机:进程号`）。
6. 备用的 GPT-SoVITS 没有队列接口，退化为**本机**文件锁排队，不支持 `--force`。

### 3.5 清晰化后处理（可选，默认关闭）
```bash
python3 scripts/zero_tts.py "讲解稿..." -v sunday --clarity -o out.wav --no-play
# 或 export ZERO_TTS_CLARITY=1 全局开启
```
`--clarity` 用 ffmpeg 低切 90Hz、削 220/400Hz 闷音、提 3.2k/5.5k 咬字频段、轻压缩并归一到 -16 LUFS，输出 48kHz。
频谱指标上，2–8kHz（咬字频段）能量占比从约 10% 升到约 35%，但指标不等于听感：**实际试听选定的是不加 EQ 的版本**（Qwen3-TTS 加速版 + `sunday`），EQ 后偏亮。仅在需要时手动加 `--clarity`。需要本机装有 `ffmpeg`。

---

## 4. 核心工程原则与避坑守则

### 4.1 参考音频与 Prompt 文本必须严格对齐
> [!CAUTION]
> **切忌 Prompt 文本字符多于参考音频发音！**
> 若参考音频仅录制了前半句（如 4.8 秒约 14 字），而 Prompt 文本填写了完整台词（如 33 字），GPT-SoVITS 会学到错误的单音素时长基准，导致合成时产生**极度拉长尾音、拖腔或复读**（例如原本 40 秒的文本被拉伸至 101 秒）。
> **规则**：
> 1. 参考音频时长控制在 **3 ~ 6 秒**。
> 2. Prompt 文本只保留参考音频中**实际发音的字词**，未发音的后半句必须全部删掉。

### 4.1b 服务引擎与选音色（2026-11 实测）
- 远端 9880 端口有两个可互换的引擎，**同一时刻只能运行一个**（4GB 显存放不下两个）：
  - **Qwen3-TTS 0.6B 加速版（主力）**：CUDA Graph，3050 上约 4–6 秒合成 8–10 秒音频（1.1–1.8× 实时），首次启动预热约 45 秒；输出 24kHz。接口兼容 GPT-SoVITS `api_v2`，`zero_tts.py` 不用改。
  - **GPT-SoVITS v2ProPlus（备用）**：更快更省显存，输出 32kHz；官方称 v2Pro 系列音质超过 V4。
- **不常驻，用时自动启动、空闲自动关闭。** 服务占约 2.7GB 显存（整卡 4GB 的 2/3），空闲也不释放，所以：客户端发现服务没运行就按需通过 SSH 拉起（`ZERO_TTS_SSH_HOST`，冷启动约 30 秒）；服务空闲超过 10 分钟自动退出并释放显存（Qwen 由服务自身判断，环境变量 `QWEN_TTS_IDLE_MIN` 可调，`0` 为常驻；SoVITS 由切换脚本顺带启动的看门狗按日志写入时间判断）。`--no-autostart` 可禁用自动启动。
- 服务端源码在本技能的 `server/` 目录（`qwen_server.py` 队列与推理、`tts-switch.ps1` 切换引擎、`idle-watch.ps1` 空闲看门狗、`start_qwen.bat` 启动）；部署到远端 `D:\\TTS_Services\\` 对应子目录。
- 切换（在远端执行）：`pwsh -File D:\TTS_Services\tools\tts-switch.ps1 -Engine qwen|sovits`。服务文件统一放在 `D:\TTS_Services\`（说明见该目录 `README.md`）。
- 零样本下**音色完全跟随参考音频**。游戏角色参考音频本身低沉（音高中位 95–115Hz），500Hz 以下能量占 80% 以上，所以 SoVITS 下偏沉；Qwen3-TTS 加速版 + `sunday` 实际试听效果最好（用户选定）。偏沉时可试 `--clarity`，或换更干净、音高适中的参考音频。
- 实测清晰度（SoVITS v2ProPlus，2–8kHz 占比，未加 EQ）：news、sunday、default、neuvillette、tighnari 较好；welt、ruan_mei、jingyuan 偏闷；`mitya` 合成会吞字，暂不可用。讲解视频首选 `sunday` 或 `tighnari` 并加 `--clarity`。
- 参考音频必须 3–10 秒。`neuvillette` 预设的参考音频 12.7 秒，超限。
- Windows 防火墙若给 uv 的 `python.exe` 生成了 Block 规则，会静默丢弃 9880 的入站连接（SSH 22 仍正常）。排查：临时开启防火墙丢包日志，看是否有 `DROP ... 9880`。

### 4.2 长文本切分策略 (`cut5`)
> [!TIP]
> 超过 50 字的文本必须开启 `cut5`（按中英文标点拆分句子进行分段推理）。脚本已将 `--split cut5` 设为默认值，可确保显存安全与极佳的发音停顿感。

### 4.3 客户端网络超时保持 ≥ 90 秒
> [!NOTE]
> 远端 GPU 处理 200 字长文本约需 20~40 秒推理。客户端必须将 HTTP 超时时间设为 90 秒，避免被本地 socket 过早截断。

---

## 5. 依赖环境与项目背景（按需读取）

底层服务部署要求、上游开源项目架构及技术背景已独立整理为参考文件：
👉 **[`references/environment-and-background.md`](references/environment-and-background.md)**

> [!TIP]
> **日常使用本 Skill 合成语音时，无需将该参考文件载入上下文**（以节约模型上下文与 Token 开销）。仅在初次搭建远端 GPU 推理节点、迁移工作站或深度排查底层服务端异常时才按需读取。

- **依赖项目**：GPT-SoVITS (V2) 核心推理引擎、`api_v2.py` 服务、V2 官方底模（`s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt` 与 `s2G2333k.pth`）、ACGN 纯净角色干声数据集。
- **环境要求**：
  - **服务端**：Windows 11 / Linux、NVIDIA GPU（推荐显存 ≥ 4GB，如 RTX 3050+）、CUDA 11.8/12.1+、Python 3.9+ 虚拟环境；严格禁止向 C 盘写入数据，统一存放在数据盘（如 `D:\TTS_GPT_SoVITS\`）。
  - **网络**：局域网 LAN（`9880` 端口）优先，搭配 EasyTier / FRP 虚拟组网异地热备。
  - **客户端**：macOS / Linux / Windows 跨平台兼容，纯 Python 3.8+ 标准库实现，零第三方 pip 依赖。

