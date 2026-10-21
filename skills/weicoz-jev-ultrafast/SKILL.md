---
name: weicoz-jev-ultrafast
version: 1.0.0
description: 用本机部署的 jev-ultrafast（Browser Use 的"选择而非生成"浏览器 agent）真实驱动浏览器完成任务、开 inspector 演示、做环境体检与端到端冒烟验证，并排查 chrome-not-running、浏览器没有 CDP、模型 401、文本层无输出等链路故障。执行层一律使用**用户自己的浏览器 profile**（登录态、cookie、扩展都在）：默认驱动 ego lite，没有 ego 就依次退到 Chrome → Edge → Brave → Chromium 等 Chromium 内核浏览器；选中品牌没开用户级远程调试开关时会**自动打开它**（会重启该浏览器一次）。无登录态的独立 profile 默认禁用，只在显式 JEV_ALLOW_FRESH=1 时使用。当用户说"用浏览器帮我做完这件事""跑一下那个浏览器 agent""看看 jev 还能不能用"时使用。不适用于 shadow DOM / iframe / canvas / 文件上传类页面，也不适用于云端或 CI（必须连本机浏览器）。
whenToUse: 用户要求用浏览器真实完成一个操作（尤其是需要已登录态的站点），或要确认 / 排查本机 jev-ultrafast 的可用性与链路故障。
---

# jev-ultrafast 本机驱动器（weicoz-jev-ultrafast）

本机已部署 [jev-ultrafast](https://github.com/browser-use/jev-ultrafast)：一个**不让模型生成动作、只从页面元素表里选**的浏览器 agent。动作空间固定为 `CLICK / TYPE_TEXT / SELECT / SCROLL_UP / SCROLL_DOWN / WAIT / DONE / BLOCKED`；只有 `TYPE_TEXT` 才另调一个小模型生成文本。执行层只认已观察到的 DOM 节点，模型输出永远不会变成 selector、坐标或脚本。

项目在 `~/File/git/jev-ultrafast`（可被 `JEV_PROJ` 覆盖）。**本 skill 的命令都从该目录跑**，因为它带 `run-local.sh`、`.env` 与 `.venv`。

## 先做体检

不要凭进程列表判断"能不能用"——先跑体检，再跑冒烟。两者都在本 skill 的 `bin/` 下：

```bash
SKILL=$(cd ~/.agents/skills/weicoz-jev-ultrafast && pwd -P)

bash "$SKILL/bin/doctor.sh"                      # 只读体检：执行层解析链 / daemon / 两个 key / inspector
bash "$SKILL/bin/doctor.sh" --fix                # 缺什么起什么（按解析链挑浏览器 → daemon → inspector）
bash "$SKILL/bin/doctor.sh" --fix-browser chrome # 给指定浏览器打开"用户级远程调试"（会重启它，登录态保留）
bash "$SKILL/bin/doctor.sh" --fix-ego            # = --fix-browser ego（兼容写法）
bash "$SKILL/bin/doctor.sh" --net                # 额外打一次真实网络，验证两个 key 活着
bash "$SKILL/bin/smoke.sh"                       # 端到端冒烟：真跑一个任务，用服务端日志判定成功
env JEV_BROWSER=edge bash "$SKILL/bin/smoke.sh"  # 强制某个浏览器（默认自动挑：ego → Chrome → Edge → …）
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
agent.browser.close()   # 读回完就关掉这次开的标签页，见“用完关标签页”
PY
```

**为什么路径 3 要显式写这么多环境变量**：`run-local.sh` 帮 1、2 两条路径做了三件事——`source ~/.zsh_secrets` 拿 `OPENROUTER_API_KEY`、**按兜底链自动挑浏览器**（`ego → chrome → edge → brave → chromium → vivaldi → arc → opera → comet → dia`，逐档看"在跑且带端点 / 开关已开可直接启动 / 开关没开但**能自动打开**且它没在跑"，解析逻辑集中在 skill 的 `bin/lib/browser.sh`，并用 `BU_CDP_WS` 把端点交给 daemon）、用 `uv run --env-file .env` 把文本层配置喂进去。**别用 `source` 后再跑**：`source ~/.zsh_secrets` 里的变量不 export 到子进程，会直接撞 401。装与配（包括 jev key / llm key / base URL 到底写在哪）见同目录 `README.md`。

## 三件必须同时对的事

| 环节 | 要求 | 现状取值 |
| --- | --- | --- |
| 决策层 | OpenRouter 的 Jev，只改 base URL + key | `TYPESAFE_BASE_URL=https://openrouter.ai/api`、`TYPESAFE_MODEL=jev-latest`、key 取 `OPENROUTER_API_KEY` |
| 文本层 | OpenAI 兼容的 `{"text": "..."}` 严格 JSON | NewAPI 网关 `http://43.167.206.51:3000/v1`、`TEXT_MODEL=deepseek-flash`、`TEXT_MODEL_REASONING=none` |
| 执行层 | **默认 ego lite**；没有 ego 就按 **Chrome → Edge → Brave → Chromium → Vivaldi → Arc → Opera → Comet → Dia** 兜底。**一律用它自己的真实 profile（登录态在）**：没在跑就正常启动它，调试开关没开就自动打开（会重启它一次）；无登录态的独立 profile 默认禁用 | daemon 用官方开关 `BU_CDP_WS` 接管端点；`run-local.sh` 自动挑，`bin/lib/browser.sh` 是唯一真源 |

### 执行层：兜底链（ego → Chrome → Edge → 其它 Chromium 系）

三条需求（用户原话）：m00791 **默认用 ego lite**、m00826 **复用它的现有 profile 以保住登录态**、m01045 **ego 不在就退 Chrome → Edge → 等 Chromium 内核浏览器**；m01203 再加一条硬要求：**所有浏览器都默认使用用户的 profile、继承登录态**——于是"无登录态的独立 profile"从默认兜底降级为显式 opt-in。详细的安装与 key 配置见同目录 `README.md`。

ego lite 自己不给外部 CDP（正常启动时进程**没有任何 TCP 监听**，只有 Chromium 单例 unix socket；它给自家 agent 的通道是 `ego-browser nodejs` 里的 IPC 版 `ego.sendCDPMessage`）。可行路线是 Chrome 的**用户级远程调试开关**：

```bash
# 一次性打开。手工 = doctor.sh --fix-browser <品牌>；自动 = lib/browser.sh 的 enable 档
# （JEV_AUTO_ENABLE 默认开；能不能为它重启浏览器由 JEV_ALLOW_RESTART 决定，默认不重启）
# 1) 先退出该浏览器（退出时会重写 Local State，不退出写进去会被覆盖；默认不打断用户，跳过并提示）
# 2) 往 <该浏览器真实 profile>/Local State 写：
#    devtools.remote_debugging = {"user-enabled": true, "allowed": true}
# 3) 再把它正常启动起来（直接起可执行文件 + --user-data-dir=<真实 profile>；别用 open -a，它只会激活已在跑的实例）
```

开关打开后**正常启动的浏览器就自带 CDP**，不用加任何启动参数，profile 也是它自己的——登录态、cookie、扩展全在。ego 上还有三条必须知道的特性：

1. 端点只写在 `<profile>/DevToolsActivePort` 里（两行：端口 + `/devtools/browser/<uuid>`）。**本 skill 对所有品牌都按"读这个文件 + TCP 探活端口"来发现端点**（ego 在该模式下 `/json/version`、`/json/list` 恒为 HTTP 404；toggle 模式下的 Chrome / Edge 虽保留 HTTP 发现接口，但没必要绕它）。
2. **第一次连接（每次 ego 启动后的第一条）ego 会弹 "Allow remote debugging?"**，必须点一次 Allow；点过之后**同一次 ego 启动内后续连接全部秒过**（实测连开 3 条都不用再点）。授权等待没有超时上限，脚本会挂在那儿等你点——别以为是卡死。
3. 端口每次启动都可能变，这时绑在旧端点上的 daemon 必须重启（`bin/lib/browser.sh` 的 `jev_daemon_rebind` 与 `doctor.sh --fix` 都会比对 daemon 环境里的 `BU_CDP_WS` 并处理）。

解析链的**五档**（每个品牌内部按 real → toggle → enable 试，三者都是真实 profile；fresh 只在你允许时才试）：

| 档位 | 什么情况 | 登录态 |
| --- | --- | --- |
| `real` | 该品牌**已经在跑**且带端点，直接用它 | ✅ 在（真实 profile） |
| `toggle` | 没在跑，但**调试开关已开** → 把它正常启动起来（它自己会写 `DevToolsActivePort`） | ✅ 在（真实 profile） |
| `enable` | 开关没开且**它没在跑** → 自动写 `Local State` 打开开关再启动（原文件先备份到 `$TMPDIR`） | ✅ 在（真实 profile） |
| `restart` | 它**正在普通模式下跑**（开关没开，或是开关打开之前启动的）→ 得先退出它才能写开关；**默认不打断用户**，只能 `doctor.sh --fix-browser <品牌>`，或设 `JEV_ALLOW_RESTART=1` 授权自动重启 | ✅ 在（要先重启它一次） |
| `fresh` | 独立 profile `~/.cache/jev-browser/<品牌>-profile` 起一个只给 agent 用的实例（默认**禁用**） | ❌ 无（仅 `JEV_ALLOW_FRESH=1`） |
| `env` | 调用方已给 `BU_CDP_WS`（最高优先级） | 取决于它 |

`JEV_BROWSER=<品牌>` 是**强制**定向：只试这个品牌，各档都失败就报错退出（比如 `JEV_BROWSER=brave` → `没装（/Applications/Brave Browser.app）`），不会静默退到别的浏览器。其它旋钮：`JEV_AUTO_ENABLE=0`（禁止 enable 档写 `Local State`）、`JEV_ALLOW_RESTART=1`（允许为开开关而退出正在跑的浏览器）、`JEV_ALLOW_FRESH=1`（才允许无登录态的 fresh 档）、`JEV_BACKUP_DIR`（`Local State` 备份目录）、`JEV_BROWSER_LIB`（指定 `browser.sh` 路径）、`JEV_PROFILE_ROOT`（fresh profile 根）、`JEV_LAUNCH_TIMEOUT`（默认 25 秒）、`JEV_DRY_RUN=1`（只报告不启动、不写文件；`doctor.sh` 无参数时默认走这个）。

为什么非要 `BU_CDP_WS`：`browser_harness/daemon.py` 的 `PROFILES = profile_dirs()` 只扫各家**默认** profile 目录，认不出 `~/.cache/jev-browser/…` 这类自定义目录，端点没被显式指定就会直接报

```
fatal: chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry
```

正解是官方开关 `BU_CDP_WS`（`daemon.py:265` 优先读）：

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

## 用完关标签页

每个 `Agent(...)` 都会在用户的浏览器里**新开一个后台标签页**，任务结束后它不会自己关。跑的是用户真实的浏览器，留着不管就是在用户那里越堆越多（实测一轮走查留下过 12 个）。

- **验证完（读回 DOM、取完证据之后）立刻关**：Python 库里调 `agent.browser.close()`；循环跑多个场景时放进 `try … finally`，出错也要关。
- `run-local.sh --url …` 这条路径不会替你关，跑完同样要清理。
- 漏关了怎么补：用 `browser_harness.helpers.cdp` 列出 `Target.getTargets` 里的 `page`，逐个 attach 后读 `innerWidth+'x'+innerHeight`。jev 开的标签页视口固定是 **1120×780**（`Emulation.setDeviceMetricsOverride`），只关这些；尺寸不符的是用户自己的标签页，**不要动**。不要按 URL 判断，用户很可能正开着同一个页面。
- 交付时说明关了几个、保留了几个。

## 坑表

| 症状 | 根因 | 处置 |
| --- | --- | --- |
| ego 打开着但拿不到 CDP | ego 正常启动**不监听任何 TCP 端口**，agent 通道是 IPC 版 `sendCDPMessage` | 先 `doctor.sh`：若 `devtools.remote_debugging.user-enabled` 为假 → `doctor.sh --fix-ego`（会重启一次 ego） |
| 连接 ego 时脚本一直挂着不动 | 用户级调试模式下第一条连接要**在 ego 窗口点一次 "Allow remote debugging?"**（`DevTools.RemoteDebugging.ConnectionPermission`，无超时上限） | 让用户点 Allow；同一次 ego 启动内后续连接不再问。别当成卡死 |
| `curl .../json/version` 对 ego 返回 404 | 用户级调试模式没有 HTTP 发现接口 | 读 `<ego profile>/DevToolsActivePort`（第 1 行端口、第 2 行 ws 路径）拼 `BU_CDP_WS` |
| ego 重启后 agent 连不上 / 报连接失败 | ego 端口每次启动都变，daemon 还绑在旧 `BU_CDP_WS` 上 | `pkill -f browser_harness.daemon`，再跑 `doctor.sh --fix`（它会比对 daemon 环境里的 `BU_CDP_WS`） |
| `--fix-ego` 写进去的开关又没了 | ego 正在运行时写 `Local State`，退出时会被 Chromium 重写覆盖 | 必须先退出 ego 再写（脚本已按此顺序做） |
| 自动打开开关那步被跳过，最后退到别的浏览器或直接报错 | 该浏览器**正在普通模式下运行**：Chromium 只在启动时读 `devtools.remote_debugging`，退出时还会用内存里的旧设置回写 `Local State`，所以"先写文件"没用，必须先退出它 | 默认**不打断用户窗口**（这就是 `restart` 档）；一步到位跑 `doctor.sh --fix-browser <品牌>`，或设 `JEV_ALLOW_RESTART=1` 授权它自己退出重开（只杀它自己真实 profile 的实例，不碰 bb-browser 之类的自动化实例） |
| agent 跑到一个"没有登录态"的浏览器上，白跑一趟 | 旧策略会默认退到独立 profile；现在默认不再这么做，只有显式 `JEV_ALLOW_FRESH=1` 才可能 | 看解析日志里的档位：`real` / `toggle` / `enable` 才是真实 profile；确认自己没开 `JEV_ALLOW_FRESH`，也别用旧的 `--user-data-dir=~/.cache/jev-browser/…` 手工起浏览器 |
| `fatal: chrome-not-running` | daemon 只扫 Chrome 默认 profile 目录 | 用 `BU_CDP_WS` 接管；或直接 `bash "$SKILL/bin/doctor.sh" --fix` |
| `DevTools remote debugging requires a non-default data directory` | Chrome 145+ 拒绝**默认 profile**的裸远程调试参数 | 两条路：用非默认 `--user-data-dir`（无登录态）；或给该浏览器打开用户级开关后正常启动（有登录态，推荐） |
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
| 判定"某浏览器正在跑"判错，于是跳过它、悄悄退到无登录态档 | **同一个二进制可能被别的自动化工具用另一个 `--user-data-dir` 拉起**（本机 bb-browser 就是：Chrome 二进制 + `--user-data-dir=~/.bb-browser/browser/user-data --remote-debugging-port=19825`） | 别只 pgrep 二进制路径：逐个候选 pid `ps -o command= -p` 看命令行，命中 `--user-data-dir=<该品牌真实 profile>` 或完全没带 `--user-data-dir` 才算"用户的浏览器在跑"（`jev_is_running` 已按此实现） |
| 想启动一个已有同二进制实例的浏览器，`open -a` 之后还是没端点 | `open -a` 只会**激活**已在跑的实例，起不了真实 profile 的新进程 | 直接起可执行文件：`"<app>/Contents/MacOS/<exe>" --user-data-dir="<真实 profile>" --no-first-run --no-default-browser-check about:blank`（`jev_launch_toggle` 已按此实现）；也**别先删 `DevToolsActivePort`**，新进程会重写它，删了只会多坑 |
| `doctor.sh` 说浏览器"端点文件过期" | 该浏览器上次是**开关打开之前**启动的，旧 `DevToolsActivePort` 留在磁盘上（端口早没了） | 正常一档：`--fix`（重启它并带 CDP）；判定依据必须是"文件里的端口 TCP 探活 + 能解析出 ws" |
| 默认链路 `smoke.sh`/`run-local.sh` 静默 exit 1，agent 一步都没跑 | 调用方是 `set -euo pipefail`，而 lib 里 `cur="$(ps … \| grep …)"` 在没有 daemon 时 grep 返回 1，**赋值语句的非零状态直接把脚本带走** | 这类"可能无匹配"的管道末尾一律 `|| true`，等待循环写成 `if ! …; then break; fi`（`jev_daemon_rebind` 已修） |
| 冒烟失败提示里出现 `bash /doctor.sh` | 脚本前面 `cd "$PROJ"` 之后，`$(dirname "$0")` 已不是脚本目录 | 顶部先取 `SELF_DIR="$(cd "$(dirname "$0")" && pwd)"` 再用 `${SELF_DIR}/doctor.sh`（`smoke.sh` 已修） |

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
- 走 `real` / `toggle` / `enable` 档时用的是**用户真实 profile**：登录态、cookie、扩展都在，能做需要登录的站点——但动作会发生在用户自己的浏览器窗口里（新开后台标签页，`Emulation.setDeviceMetricsOverride(1120×780)`），别在用户正忙时抢焦点。`enable` 档会**改用户的浏览器设置**（写 `Local State` 打开远程调试开关）并启动它一次，交付时要主动说明；`restart` 档需要先退出浏览器才有登录态，默认不做，等用户点头。唯一没有登录态的 `fresh` 档**默认禁用**，只在用户显式 `JEV_ALLOW_FRESH=1` 时才会用，用了必须声明"这次用的是无登录态的临时 profile"。
- 页面上有遮挡检测（`elementFromPoint`）与稳定性等待，慢站点会拖长时间；单步一次 TypeSafe 往返，通常 2–8 秒。
- 云端 / CI 不可用（必须连本机浏览器）。

## 关键路径速查

| 用途 | 路径 |
| --- | --- |
| 使用说明 / 配置手册（给人看） | `~/File/git/weicoz-skills/skills/weicoz-jev-ultrafast/README.md`（怎么装、怎么跑、jev key / llm key / base URL 配在哪） |
| 项目本体 | `~/File/git/jev-ultrafast`（`run-local.sh` / `.env` / `.venv` 都在这） |
| 执行层解析真源 | `~/File/git/weicoz-skills/skills/weicoz-jev-ultrafast/bin/lib/browser.sh`（`run-local.sh` 从四处软链里找到它；`JEV_BROWSER_LIB` 可覆盖） |
| ego 应用 | `/Applications/ego lite.app`（0.5.1.13，内置 Chromium 152） |
| ego profile（真实登录态） | `~/Library/Application Support/Citro Labs/ego lite/`，端点文件 `DevToolsActivePort`，pref 在 `Local State` |
| Chrome / Edge 真实 profile | `~/Library/Application Support/Google/Chrome`、`~/Library/Application Support/Microsoft Edge`（同样看 `DevToolsActivePort` + `Local State`） |
| 无登录态的独立 profile | `~/.cache/jev-browser/<品牌>-profile`（`fresh` 档；旧文档里的 `~/.cache/jev-chrome-profile` 已废弃） |
| daemon socket | `~/.config/browser-harness/runtime/bu-default.sock`，日志 `~/.config/browser-harness/tmp/bu-default.log` |
| 密钥 | `~/.zsh_secrets`（`OPENROUTER_API_KEY`）；文本层 key 在项目 `.env` |

## 维护

- 项目仓库：`~/File/git/jev-ultrafast`（上游 HEAD `1231850`）。本机改动 = `jev_ultrafast/model.py`（新增 `systemone()` 支持 base URL 覆盖、`post_json(url, key, body)` 保持 3 参数、错误文案按 URL 推导 provider、`field_text()` 的 reasoning 分支）+ `.gitignore` + 新增 `run-local.sh`（按兜底链自动接管浏览器；它 `source` skill 里的 `bin/lib/browser.sh`，找不到库时退回"ego → 9222"最小兜底）。
- 改完项目代码跑：`uv run ruff check .` 与 `uv run pytest -q`（应为 31 passed）；改完 `run-local.sh` 或 `lib/browser.sh` 至少跑一次 `bash "$SKILL/bin/smoke.sh"`（默认链路）与 `env JEV_BROWSER=<品牌> bash "$SKILL/bin/smoke.sh"`（强制定向链路），并确认 `doctor.sh` 无参数时能正确"只报告不启动"。
- 改本 skill 时 `README.md`（给人看的配置手册）与 `SKILL.md`（给 agent 看的操作说明）**要同步改**：档位、环境变量、密钥位置动了一边就得动另一边。
- 改本 skill：真源在 `~/File/git/weicoz-skills/skills/weicoz-jev-ultrafast/`（远端 codeberg），由 Skills Manager 挂载——`~/.skills-manager/skills/weicoz-jev-ultrafast` 与 `~/.agents/skills/`、`~/.codex/skills/`、`~/.claude/skills/` 都是**软链**指向仓库目录；提交只能 `git add skills/weicoz-jev-ultrafast`（skills-manager-backup 那个仓库工作区长期有数千项脏改动，**不得 `git add -A`**）。
- `bin/doctor.sh`：只读体检 + `--fix` / `--fix-browser <品牌>` / `--fix-ego`（= `--fix-browser ego`）/ `--net`，退出码 0=全绿；`bin/smoke.sh`：端到端冒烟（可用 `JEV_BROWSER=<品牌>` 强制定向），判定只看服务端日志，退出码 0=通过；`bin/lib/browser.sh`：浏览器解析链真源（档位判定集中在 `jev_tier_for_brand`，开关写入集中在 `jev_toggle_enable`），被 `run-local.sh` 与 `doctor.sh` 共用——改它必须两个入口都回归。
- 不要把 key 写进 skill、Wiki 或任何入库文件；需要凭据时从 `~/.zsh_secrets` 读。
