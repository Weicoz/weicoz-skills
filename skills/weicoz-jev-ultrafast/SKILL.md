---
name: weicoz-jev-ultrafast
description: 用本机部署的 jev-ultrafast（Browser Use 的"选择而非生成"浏览器 agent）真实驱动浏览器完成任务、开 inspector 演示、做环境体检与端到端冒烟验证，并排查 chrome-not-running、ego 没有 CDP、模型 401、文本层无输出等链路故障。默认驱动 ego lite 并复用它现有的 profile，**因此能用用户已登录的站点**。当用户说"用浏览器帮我做完这件事""跑一下那个浏览器 agent""看看 jev 还能不能用"时使用。不适用于 shadow DOM / iframe / canvas / 文件上传类页面，也不适用于云端或 CI（必须连本机浏览器）。
whenToUse: 用户要求用浏览器真实完成一个操作（尤其是需要已登录态的站点），或要确认 / 排查本机 jev-ultrafast 的可用性与链路故障。
---

# jev-ultrafast 本机驱动器（weicoz-jev-ultrafast）

本机已部署 [jev-ultrafast](https://github.com/browser-use/jev-ultrafast)：一个**不让模型生成动作、只从页面元素表里选**的浏览器 agent。动作空间固定为 `CLICK / TYPE_TEXT / SELECT / SCROLL_UP / SCROLL_DOWN / WAIT / DONE / BLOCKED`；只有 `TYPE_TEXT` 才另调一个小模型生成文本。执行层只认已观察到的 DOM 节点，模型输出永远不会变成 selector、坐标或脚本。

项目在 `~/File/git/jev-ultrafast`（可被 `JEV_PROJ` 覆盖）。**本 skill 的命令都从该目录跑**，因为它带 `run-local.sh`、`.env` 与 `.venv`。

## 先做体检

不要凭进程列表判断"能不能用"——先跑体检，再跑冒烟。两者都在本 skill 的 `bin/` 下：

```bash
SKILL=$(cd ~/.agents/skills/weicoz-jev-ultrafast && pwd -P)

bash "$SKILL/bin/doctor.sh"           # 只读体检：ego CDP / Chrome 兜底 / daemon / 密钥 / inspector
bash "$SKILL/bin/doctor.sh" --fix     # 缺什么起什么（浏览器 → daemon → inspector）
bash "$SKILL/bin/doctor.sh" --fix-ego # 给 ego lite 打开"用户级远程调试"（会重启一次 ego，登录态保留）
bash "$SKILL/bin/doctor.sh" --net     # 额外打一次真实网络，验证两个 key 活着
bash "$SKILL/bin/smoke.sh"            # 端到端冒烟：真跑一个任务，用服务端日志判定成功
```

`smoke.sh` 是**唯一能说"能用"的证据**：它起一个会回调记录端点的本地表单页，让 agent 填字并点提交，再检查服务端是否真的收到提交。退出码 0 才算通过。

## 三条调用路径

```bash
cd ~/File/git/jev-ultrafast

# 1) inspector 演示（http://127.0.0.1:8766，浏览器里点 Start demo → Run automatically）
./run-local.sh

# 2) 直接跑一次任务（最常用；--url 之后透传给 examples/run.py）
./run-local.sh --url http://127.0.0.1:8899/form.html --goal "Fill the Full name field with the text Wei, then click Submit"

# 3) Python 库（要自行读回页面、录屏、逐轮观察时用）
env OPENROUTER_API_KEY="$(sed -n 's/^export OPENROUTER_API_KEY="\(.*\)"$/\1/p' ~/.zsh_secrets | head -1)" \
    TYPESAFE_BASE_URL=https://openrouter.ai/api TYPESAFE_MODEL=jev-latest \
    TEXT_MODEL_API_KEY="$(sed -n 's/^TEXT_MODEL_API_KEY=//p' .env)" \
    TEXT_MODEL_BASE_URL=http://43.167.206.51:3000/v1 TEXT_MODEL=deepseek-flash TEXT_MODEL_REASONING=none \
    ./.venv/bin/python - <<'PY'
from jev_ultrafast import Agent
agent = Agent("http://127.0.0.1:8899/submit.html", "Fill the Full name field with Wei, then click Submit",
              record_dir=".local-test/run")
for _ in agent.run():
    pass
print("status:", agent.state.get("status"))
print("DOM:", agent.browser.evaluate('JSON.stringify({v:document.querySelector("#fullname")?.value})'))
PY
```

**为什么路径 3 要显式写这么多环境变量**：`run-local.sh` 帮 1、2 两条路径做了三件事——`source ~/.zsh_secrets` 拿 `OPENROUTER_API_KEY`、自动挑浏览器（**ego lite 优先**，读它的 `DevToolsActivePort` 并导出 `BU_CDP_WS`；ego 不可用才退回 9222 上的自动化 Chrome）、用 `uv run --env-file .env` 把文本层配置喂进去。**别用 `source` 后再跑**：`source ~/.zsh_secrets` 里的变量不 export 到子进程，会直接撞 401。

## 三件必须同时对的事

| 环节 | 要求 | 现状取值 |
| --- | --- | --- |
| 决策层 | OpenRouter 的 Jev，只改 base URL + key | `TYPESAFE_BASE_URL=https://openrouter.ai/api`、`TYPESAFE_MODEL=jev-latest`、key 取 `OPENROUTER_API_KEY` |
| 文本层 | OpenAI 兼容的 `{"text": "..."}` 严格 JSON | NewAPI 网关 `http://43.167.206.51:3000/v1`、`TEXT_MODEL=deepseek-flash`、`TEXT_MODEL_REASONING=none` |
| 执行层 | **默认 ego lite**（真实 profile，带登录态），Chrome 克隆 profile 兜底 | daemon 用官方开关 `BU_CDP_WS` 接管端点；`run-local.sh` 自动挑 |

### 执行层：为什么默认用 ego，以及它怎么被接管

需求是"**默认用 ego 浏览器、并且复用现有 profile 保住登录态**"。ego lite 自己不给外部 CDP（正常启动时进程**没有任何 TCP 监听**，只有 Chromium 单例 unix socket；它给 agent 的通道是 `ego-browser nodejs` 里的 IPC 版 `ego.sendCDPMessage`）。可行路线是 Chrome 的**用户级远程调试开关**：

```bash
# 一次性打开（skill 已封装成 doctor.sh --fix-ego，做的是同一件事）
# 1) 先退出 ego（Chrome 退出时会重写 Local State，不退出写进去会被覆盖）
# 2) 往 ~/Library/Application Support/Citro Labs/ego lite/Local State 写：
#    devtools.remote_debugging = {"user-enabled": true, "allowed": true}
# 3) open -a "ego lite"
```

打开之后**正常启动的 ego 就自带 CDP**，不需要加任何启动参数，profile 也是它自己的——登录态、cookie、扩展全在。三个必须知道的特性：

1. 端点只写在 `<profile>/DevToolsActivePort` 里（两行：端口 + `/devtools/browser/<uuid>`）；该模式下 `/json/version`、`/json/list` 都是 **HTTP 404**，所以不能像 Chrome 那样用 curl 发现，只能读文件 + TCP 探活。
2. **第一次连接（每次 ego 启动后的第一条）ego 会弹 "Allow remote debugging?"**，必须点一次 Allow；点过之后**同一次 ego 启动内后续连接全部秒过**（实测连开 3 条都不用再点）。授权等待没有超时上限，所以脚本会挂在那儿等你点——别以为是卡死。
3. ego 重启后端口会变，这时绑在旧端点上的 daemon 必须重启（`doctor.sh` 会对比 daemon 环境里的 `BU_CDP_WS` 并报出来，`--fix` 会修）。

兜底是 Chrome 克隆 profile（无登录态）：**Chrome 145+ 对默认 profile 拒绝远程调试**，所以自动化 Chrome 必须用非默认的 `--user-data-dir`；而 `browser_harness/daemon.py` 的 `PROFILES = profile_dirs()` 只扫默认 profile 目录，认不出自定义目录，于是 daemon 会直接报

```
fatal: chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry
```

两种浏览器的共同正解都是官方开关 `BU_CDP_WS`（`daemon.py:265` 优先读）显式指定 CDP 端点：

```bash
BU_CDP_WS="ws://127.0.0.1:<port>/devtools/browser/<uuid>" \
  nohup ./.venv/bin/python -m browser_harness.daemon > /tmp/bh-daemon.log 2>&1 &
# 成功日志：connecting to ws://… → attached … → listening on ~/.config/browser-harness/runtime/bu-default.sock
```

好消息是**不用手工起 daemon**：`browser_harness/admin.py:525 ensure_daemon()` 用 `env={**os.environ, **({...})}` spawn daemon，`BU_CDP_WS` 会被自动继承。所以 `run-local.sh` 只需要在调用前把这个变量导出去。

## 验收纪律（最容易骗自己的地方）

`DONE` 只是**模型声明自己完事了**，不是任务成功。给出"做完了"之前至少要有一项硬证据：

1. **服务端日志**（最强）：让目标页把关键动作回调到一个记录端点，看它有没有真的打进来。
2. **DOM 回读**：`agent.browser.evaluate('JSON.stringify({…})')`（`jev_ultrafast/browser.py:38`，内部是 `Runtime.evaluate` + `returnByValue=True`）。
3. **录屏帧**：`record_dir=` 落盘 jpg，看末帧页面状态——但这只是旁证，镜头里"看起来点了"不等于提交真的发生。

读回 DOM 时注意：`browser-harness` 客户端**没有** `evaluate()`，只有 `cdp()` / `current_tab()` / `activate_tab()` / `close_tab()` / `new_tab()` / `capture_screenshot` / `click_at_xy`。要读页面就用上面第 2 条。

## 坑表

| 症状 | 根因 | 处置 |
| --- | --- | --- |
| ego 打开着但拿不到 CDP | ego 正常启动**不监听任何 TCP 端口**，agent 通道是 IPC 版 `sendCDPMessage` | 先 `doctor.sh`：若 `devtools.remote_debugging.user-enabled` 为假 → `doctor.sh --fix-ego`（会重启一次 ego） |
| 连接 ego 时脚本一直挂着不动 | 用户级调试模式下第一条连接要**在 ego 窗口点一次 "Allow remote debugging?"**（`DevTools.RemoteDebugging.ConnectionPermission`，无超时上限） | 让用户点 Allow；同一次 ego 启动内后续连接不再问。别当成卡死 |
| `curl .../json/version` 对 ego 返回 404 | 用户级调试模式没有 HTTP 发现接口 | 读 `<ego profile>/DevToolsActivePort`（第 1 行端口、第 2 行 ws 路径）拼 `BU_CDP_WS` |
| ego 重启后 agent 连不上 / 报连接失败 | ego 端口每次启动都变，daemon 还绑在旧 `BU_CDP_WS` 上 | `pkill -f browser_harness.daemon`，再跑 `doctor.sh --fix`（它会比对 daemon 环境里的 `BU_CDP_WS`） |
| `--fix-ego` 写进去的开关又没了 | ego 正在运行时写 `Local State`，退出时会被 Chromium 重写覆盖 | 必须先退出 ego 再写（脚本已按此顺序做） |
| `fatal: chrome-not-running` | daemon 只扫 Chrome 默认 profile 目录 | 用 `BU_CDP_WS` 接管；或直接 `bash "$SKILL/bin/doctor.sh" --fix` |
| `DevTools remote debugging requires a non-default data directory` | Chrome 145+ 拒绝默认 profile 远程调试 | 必须带 `--user-data-dir=`（用 `~/.cache/jev-chrome-profile`） |
| `Model provider returned HTTP 401` | `.env` 里 `TYPESAFE_API_KEY=${OPENROUTER_API_KEY}` 是**字面量**，`demo.py` 的 `load_environment()` 只做 `os.environ.setdefault`、**不展开** `${VAR}` | 用 `run-local.sh`（它会 source `~/.zsh_secrets` 再跑） |
| `OpenRouter provider returned HTTP 401` | `.env` 能被读到了，但 key 位置是占位符 | 同上；或显式 `env OPENROUTER_API_KEY=… uv run --env-file .env …` |
| `Text helper returned no valid field value; nothing typed.` | 文本层没返回严格的 `{"text": "..."}` | 查 `TEXT_MODEL` / `TEXT_MODEL_BASE_URL` / `TEXT_MODEL_API_KEY`；该字段要求值 ≤2000 字符 |
| `RuntimeError: Start a demo first` | inspector 必须先 reset 才能 tick | 先 `POST /api/reset`，再 `/api/tick` |
| `This run has stopped. Start a fresh demo.` | tick 已经跑到终态，重复 tick | 重新 reset |
| `StalePage: Page changed since this decision. Observe again.` | 决策用的页面快照已过期（这是设计如此，不是 bug） | 下一次 observe 即可；不要在它外面加循环重试补丁 |
| `[stderr] Terminated: 15` | 后台进程挂在了短命子 shell 上，整条命令结束时被清理 | `nohup … &` 要写在独立语句里，起完再探测端口确认真活着；测试脚本里对探针服务 `disown` |
| 冒烟"服务端没收到"但一切看着正常 | 探针端口被上一轮的遗留服务占着，**就绪检查打到了别人的 200**，agent 去的是旧页面 | 就绪判定必须验到自家服务（smoke.sh 用 `/__ping` 回 nonce 校验），端口被占就换下一个 |
| bash 报 `xxx；: unbound variable` | 中文/全角标点紧跟 `$var` 时被当成变量名的一部分 | 一律写 `${var}` |
| `pkill -f "remote-debugging-port=9222"` 之后端口不回来 | Chrome 重启不会自恢复调试端口 | 重新启动 Chrome；别用这种模糊 pkill，按 `--user-data-dir` 精确匹配；**也别用 `lsof -ti :port` 收尾，它连"连到这个端口的客户端"一起列出来**（踩过：误杀 ego 一个渲染进程） |

## inspector 的 curl 驱动法（不点 UI）

inspector 的 POST 校验 `Host`、`X-Demo-Token`（43 字符，页面里注入）、`Origin`；只认 `reset` / `tick` / `predict` / `act` 四个命令，场景只有 `flights`（真实 Google Flights）、`travel`、`research`（后两个指向本地 `fixture.html`）。

```bash
TOKEN=$(curl -q -s http://127.0.0.1:8766/ | grep -oE 'name="demo-token" content="[A-Za-z0-9_-]+"' | sed -E 's/.*content="([^"]+)".*/\1/')
H=(-H "Host: 127.0.0.1:8766" -H "X-Demo-Token: $TOKEN" -H 'Content-Type: application/json')
curl -q -s -X POST http://127.0.0.1:8766/api/reset "${H[@]}" -d '{"scenario":"travel","goal":"Set the destination to London and submit the search."}'
curl -q -s -X POST http://127.0.0.1:8766/api/tick  "${H[@]}" -d '{}'   # 反复 tick 到 status=done
```

`GET /api/state` 只是 inspector 的内存态，重启即丢；它不是权威状态。

## 能力边界（要主动向用户说明）

- 只支持常见 HTML + ARIA 控件；**不支持** shadow root、iframe、canvas、文件上传、新标签页、嵌套滚动、任意键盘组件。
- 走 ego 时用的是**用户真实 profile**：登录态、cookie、扩展都在，能做需要登录的站点——但动作会发生在用户自己的浏览器窗口里（新开后台标签页，`Emulation.setDeviceMetricsOverride(1120×780)`），别在用户正忙时抢焦点；Chrome 兜底路线则是克隆 profile、没有登录态。
- 页面上有遮挡检测（`elementFromPoint`）与稳定性等待，慢站点会拖长时间；单步一次 TypeSafe 往返，通常 2–8 秒。
- 云端 / CI 不可用（必须连本机浏览器）。

## 关键路径速查

| 用途 | 路径 |
| --- | --- |
| 项目本体 | `~/File/git/jev-ultrafast`（`run-local.sh` / `.env` / `.venv` 都在这） |
| ego 应用 | `/Applications/ego lite.app`（0.5.1.13，内置 Chromium 152） |
| ego profile（真实登录态） | `~/Library/Application Support/Citro Labs/ego lite/`，端点文件 `DevToolsActivePort`，pref 在 `Local State` |
| Chrome 兜底 profile | `~/.cache/jev-chrome-profile`（克隆 profile，无登录态） |
| daemon socket | `~/.config/browser-harness/runtime/bu-default.sock`，日志 `~/.config/browser-harness/tmp/bu-default.log` |
| 密钥 | `~/.zsh_secrets`（`OPENROUTER_API_KEY`）；文本层 key 在项目 `.env` |

## 维护

- 项目仓库：`~/File/git/jev-ultrafast`（上游 HEAD `1231850`）。本机改动 = `jev_ultrafast/model.py`（新增 `systemone()` 支持 base URL 覆盖、`post_json(url, key, body)` 保持 3 参数、错误文案按 URL 推导 provider、`field_text()` 的 reasoning 分支）+ `.gitignore` + 新增 `run-local.sh`（ego 优先的浏览器自动接管）。
- 改完项目代码跑：`uv run ruff check .` 与 `uv run pytest -q`（应为 31 passed）；改完 `run-local.sh` 至少跑一次 `bash "$SKILL/bin/smoke.sh"`。
- 改本 skill：本体在 `~/.skills-manager/skills/weicoz-jev-ultrafast/`（weicoz-skills 仓库），三处软链 `~/.agents/skills/`、`~/.codex/skills/`、`~/.claude/skills/` 指向它；提交只能 `git add <指定目录>`（该仓库工作区长期有数千项 skills-manager 自身产生的脏改动，**不得 `git add -A`**）。
- `bin/doctor.sh`：只读体检 + `--fix` / `--fix-ego` / `--net`，退出码 0=全绿；`bin/smoke.sh`：端到端冒烟，判定只看服务端日志，退出码 0=通过。
- 不要把 key 写进 skill、Wiki 或任何入库文件；需要凭据时从 `~/.zsh_secrets` 读。
