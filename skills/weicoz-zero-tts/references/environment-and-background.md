# weicoz-zero-tts 依赖环境、项目背景与部署架构指南

> **说明**：本文件供初次搭建远端 GPU 推理节点、迁移服务或深度排查底层异常时查阅。**日常语音合成调用时无需加载本文件至上下文。**

---

## 1. 项目背景与架构设计初衷

### 1.1 算力卸载架构（Mac 轻量终端 + 远端 GPU 常驻）
- **痛点**：在 MacBook 等开发机或轻薄办公本上直接运行现代深度学习 TTS 模型（如 CosyVoice、F5-TTS、GPT-SoVITS 本地权重），需加载数 GB 的 PyTorch 权重与 Vocoder，极度挤占系统内存，导致风扇狂转、续航暴跌，且无法长时间后台待命。
- **解法**：采用**算力卸载（Compute Offloading）模式**。在配有独立显卡（如 NVIDIA RTX 3050 等）的常驻工作站上部署 GPT-SoVITS `api_v2` 服务，Mac 本机仅运行不到 200 行的标准库客户端，通过极简 HTTP POST 发送请求并在本地流式播放或保存，实现轻量终端与强劲算力的解耦。

### 1.2 GPT-SoVITS V2 技术原理背景
- **少样本声音克隆**：由开源社区开发，融合了 GPT 语义 token 建模与 VITS 变分自编码声学生成技术。
- **表现力突破**：相比传统机械固定的公有云 TTS，GPT-SoVITS 仅需 3~5 秒的高质量参考音频（Prompt Audio）及其对应发音文本，即可在零样本/少样本条件下克隆目标声线的音色、语气、语调起伏与呼吸停顿。

### 1.3 知识讲解与角色音色库定制背景
- **应用场景**：赋能自动化视频制作（如基于 Remotion 的产品演示、短视频解说）、技术文档语音播报、架构设计评审讲解、读书笔记分享等。
- **声线精选**：结合 ACGN 社区（`res.acgnai.top` / `pan.acgnai.top`）公开纯净干声音色数据集，精选原神与星穹铁道中极具文化厚度与辨识度的角色声线（如钟离的厚重博学、那维莱特的严谨条理、艾尔海森的冷静逻辑、真理医生的锐利批判、阮•梅的知性空灵），针对科技与知识解说场景做深度适配。

---

## 2. 依赖的上游开源项目

| 项目名称 | 开源协议 | 用途与定位 | 仓库 / 资源链接 |
| :--- | :--- | :--- | :--- |
| **GPT-SoVITS (V2)** | MIT | 核心 TTS 推理引擎，提供文本前端分词、G2P、GPT 预测与 SoVITS 声学生成 | [GitHub 官方仓库](https://github.com/RVC-Boss/GPT-SoVITS) |
| **GPT-SoVITS api_v2** | MIT | 官方提供的轻量级 HTTP API 服务，支持 Fast/Full 推理模式与标点自动切句 | 内置于 GPT-SoVITS 根目录 `api_v2.py` |
| **ACGN 声音资源库** | 社区共享 | 提供高质量角色预训练音色权重（pth / ckpt）与伴奏分离纯净干声切片 | [ACGN 声音模型站](https://res.acgnai.top/) |

---

## 3. 依赖的环境与部署拓扑

### 3.1 远端 GPU 推理工作站（服务端）
- **操作系统**：Windows 10/11 64-bit 或 Linux（Ubuntu 20.04/22.04 LTS）。
- **硬件要求**：
  - GPU：NVIDIA 显卡，CUDA Compute Capability ≥ 7.5（推荐 RTX 3050 / RTX 3060 / RTX 4060 或以上）。
  - 显存：推荐 4GB 及以上显存。
- **软件环境**：
  - Python 3.9 或 3.10 虚拟环境（`.venv`）。
  - PyTorch 2.1+ 带 CUDA 11.8 或 12.1 加速库。
  - 系统 PATH 中包含 `ffmpeg`。
- **磁盘存储规范（安全红线）**：
  - **严禁向系统盘（C 盘）写入模型数据或缓存**。
  - 必须将项目整包、虚拟环境、预训练权重及音色库统一部署在非系统数据盘（如 `D:\TTS_GPT_SoVITS\`）。
- **目录布局标准**：
  ```text
  D:\TTS_GPT_SoVITS\
  ├── .venv\                           # 专用 Python 虚拟环境
  ├── api_v2.py                        # 官方 API v2 服务入口
  ├── GPT_SoVITS\
  │   └── configs\tts_infer.yaml       # 推理配置文件
  ├── GPT_weights_v2\
  │   └── s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt # V2 基础底模
  ├── SoVITS_weights_v2\
  │   └── s2G2333k.pth                 # V2 基础底模
  ├── ref_audio\                       # 常用参考音频与干声切片 (.wav)
  └── models\voice_models\             # 精选多角色音色库 (zhongli, welt, etc.)
  ```
- **服务端启动命令**：
  ```cmd
  cd /d D:\TTS_GPT_SoVITS
  .venv\Scripts\python.exe api_v2.py -a 0.0.0.0 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
  ```

### 3.2 网络环境与连接拓扑
- **双通道容灾架构**：
  1. **首选通道（局域网直连 LAN）**：当客户端与工作站在同一局域网时，直连局域网 IP（如 `http://<lan-gpu-host>:9880/tts`），延迟低（< 5ms），传输速率高。
  2. **备用通道（虚拟组网 EasyTier / FRP）**：外出或远程时，自动无缝回退至点对点虚拟网 IP（如 `http://<easytier-virtual-ip>:9880/tts`），确保全天候可用。
- **端口放行**：Windows 高级防火墙需添加入站规则，放行 TCP 9880 端口。

### 3.3 客户端环境要求
- **系统支持**：macOS (Apple Silicon / Intel)、Linux、Windows。
- **运行时**：Python 3.8 及以上版本。
- **零额外依赖**：客户端使用 Python 原生内置标准库（`urllib`, `json`, `argparse`, `tempfile`, `subprocess`），**无需执行任何 `pip install`**。
- **音频播放支持**：macOS 自动调用 `afplay`，Linux 调用 `aplay` / `paplay` / `ffplay`，Windows 调用 `winsound`；支持通过 `--no-play` 开关禁用播放并仅保存文件。

---

## 4. 运行期维护与常见故障排除

### 4.1 服务端无法启动或端口占用
- 检查 9880 端口占用：`netstat -ano | findstr 9880`。
- 若端口被旧进程僵死占用，通过 PID 终止：`taskkill /F /PID <pid>`。

### 4.2 客户端连接超时 (HTTP Connection Timeout)
- 检查 GPU 工作站是否处于休眠状态；可通过局域网唤醒（Wake-on-LAN）或定期保活。
- 确认 Windows 防火墙已放行 9880 端口。
- 检查 `ZERO_TTS_API_URL` 环境变量配置是否包含当前网络可达的 IP 地址。

### 4.3 显存溢出 (CUDA Out of Memory)
- 若并发合成超长篇幅文本导致显存紧张，请确保客户端开启 `--split cut5`（按标点切分），该机制会自动将长文本划分为独立的小句依次推理并拼接，极大降低单次显存峰值。
