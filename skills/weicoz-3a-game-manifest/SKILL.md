---
name: weicoz-3a-game-manifest
description: |
  专门用于从 3a.lol 游戏社区搜索、筛选、提取 Steam 游戏入库清单（.lua / manifest）及对应游戏本体资源，自动下载入库清单并规范归档至 steam-manifests 仓库。集成用户电脑硬件配置前置记忆与 doesitrun.com 画质/帧率预测流程，初次询问后永久免问，自动生成针对性画质调优指南并推送到 GitHub。
allowed-tools: Bash(ego-browser:*), Bash(node:*), Bash(curl:*), Bash(unzip:*), Bash(mkdir:*), Bash(cp:*), Bash(mv:*), Bash(ls:*), Bash(git:*)
---

# Weicoz 3A Game Manifest

专门用于从 `https://3a.lol` 游戏社区检索资源，**自动下载 Steam 入库清单（.lua/manifest）并规范归档**；若发现完整游戏本体，则将其下载链接整理至 `README.md` 中**供用户按需手动下载**；同时结合用户硬件配置（基于 doesitrun.com 跑分模型），自动生成专属画质与帧率指南，并同步至 GitHub 远端仓库。

---

## 硬件配置前置检查与匹配校验机制 (字段校验，缺失提示补充，匹配免问)

在执行任何游戏检索与归档前，必须先获取用户的电脑硬件配置并校验其是否匹配规范：

1. **优先级与读取机制**：
   - **第一优先级（仓库本地配置文件，最高优先级）**：
     优先读取当前仓库根目录下的配置文件：
     - `.user_specs.json` 或 `user_specs.json`
   - **第二优先级（环境变量）**：
     检查是否配置了以下环境变量（例如在 `~/.zshrc` 中导出）：
     - `STEAM_SPECS_CPU`（例如：`"Intel Core i5-9600K"`）
     - `STEAM_SPECS_GPU`（例如：`"NVIDIA GeForce RTX 2060 6GB"`）
     - `STEAM_SPECS_RAM`（例如：`"16GB"`）
     - `STEAM_SPECS_VRAM`（例如：`"6GB"`）
     - `STEAM_SPECS_RESOLUTION`（例如：`"1080p"`）
     - 或复合 JSON 变量：`STEAM_HARDWARE_SPECS`
   - **第三优先级（用户全局配置文件）**：
     - `~/.config/steam-manifests/user_specs.json`

2. **字段匹配校验清单**：
   - **必填项**（必须非空字符串）：
     - `cpu`：CPU 处理器型号
     - `gpu`：独立显卡型号及显存容量
     - `ram`：系统运行内存
   - **建议项**：
     - `vram`：显卡独立显存（用于虚幻5及大作防爆显存）
     - `resolution`：目标基准分辨率（默认 1080p）

3. **判定与行为机制**：
   - **完全匹配合格**：直接静默读取并继续执行游戏检索与性能预测，**绝不向用户重复提问**。
   - **完全无配置**：明确向用户发出提示：“未检测到硬件配置，请补充电脑配置 (CPU / 显卡及显存 / 内存)”，引导用户补充或在仓库根目录生成 `.user_specs.json`。
   - **配置存在但未匹配（字段缺失）**：明确指出具体缺失的必填项并提示用户补充：“检测到硬件配置缺少必填项 `[缺失字段]`，请补充完整”，补齐后继续。
3. **当前用户硬件基准配置**：
   ```json
   {
     "cpu": "Intel Core i5-9600K",
     "gpu": "NVIDIA GeForce RTX 2060 6GB",
     "ram": "16GB",
     "vram": "6GB",
     "resolution": "1080p",
     "notes": "6核6线程无超线程，Turing架构6G显存，支持DLSS 2，大作建议关光追控制纹理"
   }
   ```

---

## 浏览器控制渠道分级策略 (主备机制)

在与 `3a.lol` 交互时，严格按照以下双渠道优先级调度浏览器：

1. **第一优先级：`ego-browser`（首选）**：
   - **适用**：已安装 `ego-browser` 且能够正常启动，复用当前用户已登录态。
   - **规范**：在任务开始时使用 `useOrCreateTaskSpace`，任务完成后**必须在独立的最终代码块中调用 `completeTaskSpace(taskId, { keep: false })` 清理**。
2. **第二优先级：`CDP (Chrome DevTools Protocol)`（兜底降级）**：
   - **触发条件**：
     - 系统中未安装或找不到 `ego-browser` 命令；
     - `ego-browser` 进程卡死、启动报错、超时或无法读取页面数据。
   - **执行手段**：
     - 检查 Chrome 远程调试端口（默认 `http://127.0.0.1:9222`）；
     - 若未启动，唤起带调试参数的 Chrome 实例：
       ```bash
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 &
       ```
     - 通过 HTTP API 与 WebSocket CDP 发送指令提取搜索结果与帖子数据。

---

## 核心原则与自动化边界 (必须遵守)

1. **自动下载范围：仅限清单（默认行为）**：
   - **特征**：文件名为纯数字 AppID（如 `2825860`、`2825860.zip`、`2825860.lua`）或 `.lua` 文件，体积 **≤ 10 MB**（通常 < 1 MB）。
   - **行为**：**Skill 必须自动执行转存与下载**（使用夸克 CLI），拉取到本地对应游戏目录中解压归档。
2. **本体资源处理：仅收录链接，严禁自动下载**：
   - **特征**：几个 G 到几十 G 的完整游戏安装包/分卷压缩包（解压即玩等）。
   - **行为**：**Skill 绝对不自动下载本体**；必须将本体的网盘链接、提取码、文件体积与版本特色整理记录在该游戏目录的 `README.md` 中，**由用户在需要时按需手动下载**。
3. **归档仓库与目录规范**：
   - **归档根仓库**：`steam-manifests` 根目录（独立公开仓库）
   - **清单子目录**：`manifests/{AppID} - {英文名} - {中文名}[ - {版本号}]`
   - **目录内文件配置**：
     - `{AppID} - {英文名} - {中文名}.lua`：可辨识清单文件（已自动下载就绪）
     - `{AppID}.lua`：纯数字 AppID 原名兼容文件（供入库工具自动扫描匹配）
     - `{AppID} - {英文名} - {中文名}.zip`：原始压缩包备份（若有配套 .manifest depot 清单亦一并放入）
     - `README.md`：记录清单代码、原帖来源、本体手动下载专区，以及**专属硬件流畅运行指南**
4. **硬件画质与帧率预测标准 (参考 doesitrun.com)**：
   - 抓取后根据游戏引擎（UE5 / Northlight / RE Engine / 经典复刻等）与保存的电脑配置（如 i5-9600K / RTX 2060 6G），给出：
     - **推荐分辨率与画质档位**（低/中/高/极高）
     - **超分辨率缩放设置**（DLSS/FSR 档位）
     - **预估 FPS**
     - **避坑与微调建议**（光追关闭、显存防溢出、阴影/体积雾设中等）
5. **索引维护与 GitHub 自动推送**：
   - 归档后调用 `node scripts/index_updater.js` 自动更新根目录及子目录的 `INDEX.md` 与 `README.md`。
   - 执行 `git add .`、中文 commit message、并自动推送至 GitHub 远端仓库。

---

## 标准操作流程

### 第一步：硬件配置前置检查与匹配校验 (检查是否匹配，缺失提示补充)
```bash
REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# 1. 查找配置（仓库本地 -> 环境变量 -> 全局配置）
# 2. 校验配置是否匹配必填规范 (cpu, gpu, ram 必须非空且有效)：
if [ -f "$REPO_DIR/.user_specs.json" ] || [ -f "$REPO_DIR/user_specs.json" ] || [ -n "$STEAM_SPECS_CPU" ] || [ -f "$HOME/.config/steam-manifests/user_specs.json" ]; then
  # 校验字段是否齐全，若缺失 cpu / gpu / ram 则提示补充
  node "$REPO_DIR/scripts/index_updater.js" --check
else
  # 完全无配置时，主动提示用户补充
  echo "⚠️ 未检测到硬件配置！请补充您的电脑配置信息 (CPU / 显卡及显存 / 内存容量)："
  # 接收用户输入并写入 $REPO_DIR/.user_specs.json
fi
```

### 第二步：社区检索目标游戏
使用 `ego-browser` 检索目标游戏：
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace("游戏检索");
const enc = encodeURIComponent("游戏名或AppID");
await openOrReuseTab(`https://3a.lol/search?q=${enc}`, { wait: true, timeout: 15 });
await wait(2);
// 提取搜索结果...
await completeTaskSpace(task.id, { keep: false });
EOF
```

### 第三步：分析帖子与网盘分类判定
- **清单链接（≤ 10 MB）**：提取 URL、提取码、确切体积，进入下一步自动下载。
- **本体链接（> 10 MB，通常几G~几十G）**：提取 URL、提取码、本体总大小、版本特性，仅记录备用，**不执行下载**。

### 第四步：自动转存并下载清单文件 (夸克 CLI)
```bash
QUARK_DIR="${QUARK_DRIVE_DIR:-$HOME/.agents/skills/quarkclouddrive}"
cd "$QUARK_DIR"

# 1. 自动转存
env CODEX_SHELL=1 node scripts/quark-drive.cjs saveas \
  --url "<夸克清单分享URL>" \
  --session-input "下载游戏清单" \
  --session-id "$(date +%s)-fetch"

# 从输出 JSON 中提取 save_as.save_as_top_fids[0] 作为 fid

# 2. 自动下载到游戏目录
env CODEX_SHELL=1 node scripts/quark-drive.cjs download \
  --fid "<文件FID>" \
  --output-dir "$REPO_DIR/manifests/{AppID} - {英文名} - {中文名}" \
  --session-input "下载游戏清单" \
  --session-id "$(date +%s)-fetch"
```

### 第五步：解压、重命名、生成硬件画质指南并编写 README
1. 解压压缩包获取 `.lua` 清单。
2. 双版本重命名：生成 `{AppID} - {英文名} - {中文名}.lua`，同时保留 `{AppID}.lua` 兼容原名。
3. 压缩包备份为 `{AppID} - {英文名} - {中文名}.zip`。
4. 结合当前用户的硬件规格与游戏引擎特性，编写包含 `## 🎮 硬件运行建议与预估表现` 章节的 `README.md`。

### 第六步：刷新总索引并推送到 GitHub
```bash
cd "$REPO_DIR"
node scripts/index_updater.js
git add .
git commit -m "feat: 归档《游戏名》(AppID) 入库清单与本体链接，更新硬件运行指南"
git push origin main
```
