---
name: weicoz-3a-game-manifest
description: |
  专门用于从 3a.lol 游戏社区搜索、筛选、提取 Steam 游戏入库清单（.lua / manifest）及对应游戏本体资源，自动下载入库清单并规范归档。支持 ego-browser 优先控制，若不存在或异常则自动降级使用 CDP。当用户需要在 3a.lol 找游戏、抓取/保存游戏清单、下载 Steam 入库清单、整理游戏本体网盘链接时使用。
allowed-tools: Bash(ego-browser:*), Bash(node:*), Bash(curl:*), Bash(unzip:*), Bash(mkdir:*), Bash(cp:*), Bash(mv:*), Bash(ls:*)
---

# Weicoz 3A Game Manifest

专门用于从 `https://3a.lol` 游戏社区检索资源，**自动下载 Steam 入库清单（.lua/manifest）并规范归档**；若发现完整游戏本体，则将其下载链接整理至 `README.md` 中**供用户按需手动下载**。

---

## 浏览器控制渠道分级策略 (主备机制)

在与 `3a.lol` 交互时，严格按照以下双渠道优先级调度浏览器：

1. **第一优先级：`ego-browser`（首选）**：
   - **适用**：已安装 `ego-browser` 且能够正常启动，复用当前用户已登录态（`weicoz` 账号）。
   - **检查**：优先运行 `which ego-browser` 与测试 taskSpace。
2. **第二优先级：`CDP (Chrome DevTools Protocol)`（兜底降级）**：
   - **触发条件**：
     - 系统中未安装或找不到 `ego-browser` 命令；
     - `ego-browser` 进程卡死、启动报错、超时或无法读取页面数据。
   - **执行手段**：
     - 检查 Chrome 远程调试端口（默认 `http://127.0.0.1:9222`）；
     - 若未启动，可唤起带调试参数的 Chrome 实例：
       ```bash
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 &
       ```
     - 通过 HTTP API (`/json/new`, `/json/list`) 与 WebSocket CDP 协议发送 `Page.navigate` 与 `Runtime.evaluate` 指令，执行页面导航、元素提取与状态获取；
     - 或直接调用配套辅助脚本：
       ```bash
       node /Users/weicoz/File/git/weicoz-skills/skills/weicoz-3a-game-manifest/scripts/cdp_browser.js check
       ```

---

## 核心原则与自动化边界 (必须遵守)

1. **自动下载范围：仅限清单（默认行为）**：
   - **特征**：文件名为纯数字 AppID（如 `2825860`、`2825860.zip`、`2825860.lua`）或 `.lua` 文件，体积 **≤ 10 MB**（通常 < 1 MB）。
   - **行为**：**Skill 必须自动执行转存与下载**（使用夸克 CLI），拉取到本地对应游戏目录中解压归档。

2. **本体资源处理：仅收录链接，严禁自动下载**：
   - **特征**：几个 G 到几十 G 的完整游戏安装包/分卷压缩包（解压即玩等）。
   - **行为**：**Skill 绝对不自动下载本体**；必须将本体的网盘链接、提取码、文件体积与版本特色整理记录在该游戏目录的 `README.md` 中，**由用户自己在 README 中查找并按需手动下载**。

3. **失效插件隔离**：
   - 论坛页面中嵌入的“下载助手”等油猴插件已失效，严禁依赖。

4. **目录与文件规范**：
   - 归档根目录：`workspace/games/manifests/`
   - 单游戏目录命名规则：
     ```text
     {AppID} - {英文名} - {中文名}[ - {版本号}]
     ```
   - 目录内文件配置：
     - `{AppID} - {英文名} - {中文名}.lua`：可辨识清单文件（已自动下载就绪）
     - `{AppID}.lua`：纯数字 AppID 原名兼容文件（供入库工具自动扫描匹配）
     - `{AppID} - {英文名} - {中文名}.zip`：原始压缩包备份
     - `README.md`：记录清单代码、帖子源、以及**完整游戏本体手动下载链接专区**

5. **总索引维护 (INDEX.md)**：
   - 每次抓取并归档新游戏后，自动调用配套脚本更新总索引。

---

## 标准操作流程

### 第一步：社区检索目标游戏

#### 方案 A：使用 ego-browser 检索 (首选)
```bash
ego-browser nodejs <<'EOF'
const task = await taskSpace("游戏检索");
const page = task.page("p1");

const keyword = encodeURIComponent("游戏名或AppID");
await page.goto(`https://3a.lol/search?q=${keyword}`);
await page.waitForTimeout(2500);

const results = await page.evaluate(() => {
  return Array.from(document.querySelectorAll(".fps-result")).map(item => ({
    title: item.querySelector(".search-link")?.innerText?.trim(),
    url: item.querySelector(".search-link")?.href,
    snippet: item.querySelector(".blurb")?.innerText?.trim()
  }));
});

console.log(JSON.stringify(results, null, 2));
await task.finish({ keep: [] });
EOF
```

#### 方案 B：使用 CDP 降级检索 (ego-browser 异常或不存在时)
通过 CDP 接口直接操作 Chrome 调试会话：
```bash
# 1. 确认 CDP 端口存活
curl -s http://127.0.0.1:9222/json/version

# 2. 打开新标签页并导航
NEW_TAB=$(curl -s -X PUT "http://127.0.0.1:9222/json/new?https://3a.lol/search?q=游戏名")
# 使用 WebSocket 或 Node.js 脚本执行 Runtime.evaluate 提取搜索结果
```

### 第二步：分析帖子并探测网盘资源（分类判定）

遍历帖子详情中的网盘分享链接：
- **清单链接（≤ 10 MB）**：提取 URL、提取码、确切体积，进入下一步自动下载。
- **本体链接（> 10 MB，通常几G~几十G）**：提取 URL、提取码、本体总大小、版本特性，仅记录备用，**不执行下载**。

### 第三步：自动转存并下载清单文件 (夸克 CLI)

对筛选出的清单链接（≤10MB），调用 `quarkclouddrive` 自动拉取：

```bash
cd /Users/weicoz/.agents/skills/quarkclouddrive

# 1. 自动转存
env CODEX_SHELL=1 node scripts/quark-drive.cjs saveas \
  --url "<夸克清单分享URL>" \
  --session-input "下载游戏清单" \
  --session-id "$(date +%s)-fetch"

# 从输出 JSON 中提取 save_as.save_as_top_fids[0] 作为 fid

# 2. 自动下载到游戏目录
env CODEX_SHELL=1 node scripts/quark-drive.cjs download \
  --fid "<文件FID>" \
  --output-dir "workspace/games/manifests/{AppID} - {英文名} - {中文名}" \
  --session-input "下载游戏清单" \
  --session-id "$(date +%s)-fetch"
```

### 第四步：解压、重命名与生成 README

在游戏目录内：
1. 解压压缩包获取 `.lua` 清单。
2. 双版本重命名：生成 `{AppID} - {英文名} - {中文名}.lua`，同时保留 `{AppID}.lua` 兼容原名。
3. 压缩包备份为 `{AppID} - {英文名} - {中文名}.zip`。
4. 编写 `README.md`，包含已就绪的清单及**供用户手动下载的本体链接专区**。

### 第五步：刷新总索引 (INDEX.md)

运行配套脚本更新 `workspace/games/manifests/INDEX.md`：

```bash
node /Users/weicoz/File/git/weicoz-skills/skills/weicoz-3a-game-manifest/scripts/index_updater.js
```
EOF
