# weicoz-jev-ultrafast

本机部署 [jev-ultrafast](https://github.com/browser-use/jev-ultrafast) 的**安装 + 配置 + 使用手册**，给人看；给 agent 看的操作说明在同目录 [`SKILL.md`](./SKILL.md)。

jev-ultrafast 是 Browser Use 的浏览器 agent：**不让模型生成动作，只从页面元素表里选**。动作空间固定为 `CLICK / TYPE_TEXT / SELECT / SCROLL_UP / SCROLL_DOWN / WAIT / DONE / BLOCKED`；只有 `TYPE_TEXT` 才另调一个小模型生成要输入的文字。执行层只认已观察到的 DOM 节点，模型输出永远不会变成 selector、坐标或脚本。

本 skill 把它包装成三件事：

1. **浏览器执行层解析链**（`bin/lib/browser.sh`）——默认驱动 **ego lite**，没有就依次退到 Chrome → Edge → Brave → Chromium 等 Chromium 内核浏览器，**一律使用用户自己的 profile**（登录态、cookie、扩展都在），需要时会自动打开浏览器的"用户级远程调试"开关。
2. **两个入口脚本**（`bin/doctor.sh` 体检、`bin/smoke.sh` 端到端冒烟）——用真实证据回答"现在还能不能用"。
3. **项目侧的启动器**（`~/File/git/jev-ultrafast/run-local.sh`）——把密钥、模型端点、浏览器端点三件事一次配好。

---

## 1. 它由三层组成

| 层 | 干什么 | 配什么 | 走不通时的症状 |
| --- | --- | --- | --- |
| **决策层** Jev（TypeSafe System One） | 每步从元素表里"选"一个操作 + 一次投机出 `click_target` / `type_text_target` / `select_target` | `TYPESAFE_BASE_URL` + `TYPESAFE_API_KEY`（或 `OPENROUTER_API_KEY`）+ `TYPESAFE_MODEL` | `Model provider returned HTTP 401` / `OpenRouter provider returned HTTP 401` |
| **文本层** 小 LLM | 只在动作为 `TYPE_TEXT` 时生成要输入的文字 | `TEXT_MODEL_API_KEY` + `TEXT_MODEL_BASE_URL` + `TEXT_MODEL` + `TEXT_MODEL_REASONING` | `TYPE_TEXT needs TEXT_MODEL_API_KEY…` / `Text helper returned no valid field value; nothing typed.` |
| **执行层** 浏览器 | 真正点击/输入；通过 CDP 连接的 Chrome 内核浏览器 | 浏览器解析链 + `BU_CDP_WS` + browser-harness daemon | `chrome-not-running` / `DevTools remote debugging requires a non-default data directory` / agent 一动不动 |

三层是独立的：**换决策层的供应商不用动文本层配置，反之亦然**。

---

## 2. 先决条件

| 需要什么 | 检查命令 | 说明 |
| --- | --- | --- |
| 项目本体 | `ls ~/File/git/jev-ultrafast` | 没有就 `git clone https://github.com/browser-use/jev-ultrafast ~/File/git/jev-ultrafast` |
| Python 3.12+ 与 `uv` | `uv --version` | 依赖只有 `browser-harness==0.1.13` 和 `httpx[http2]`；`uv sync` 会建 `.venv` |
| 一个 Chromium 内核浏览器 | `/Applications/ego lite.app`（默认） | ego lite / Chrome / Edge / Brave / Chromium / Vivaldi / Arc / Opera / Comet / Dia 都认 |
| 决策层凭据 | `echo ${#OPENROUTER_API_KEY}` | 放 `~/.zsh_secrets`（权限 600） |
| 文本层凭据 | 见 §4 | 放项目 `.env`，**不要提交** |

浏览器必须是**本机图形会话里能起来的**：云端 / CI / 纯 headless 容器跑不通（Chrome 145+ 之后连"默认 profile 开远程调试"都被拒）。

---

## 3. 决策层（jev key）怎么配

`jev_ultrafast/model.py` 的 `systemone()` 决定请求打哪里：

```python
base = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
openrouter = "openrouter.ai" in base
key = os.environ.get("OPENROUTER_API_KEY") if openrouter else None
return base + "/v1/systemone", key or os.environ.get("TYPESAFE_API_KEY")
```

也就是**两条路，二选一**：

| 路线 | `TYPESAFE_BASE_URL` | key 变量 | `TYPESAFE_MODEL` | 特点 |
| --- | --- | --- | --- | --- |
| 官方 TypeSafe | `https://api.typesafe.ai`（默认） | `TYPESAFE_API_KEY` | `jev-latest` | 官方直连；需要 TypeSafe 账号（Cloud 曾有等待名单） |
| **OpenRouter（本机在用）** | `https://openrouter.ai/api` | `OPENROUTER_API_KEY` | `jev-latest` | 无需 TypeSafe 账号，只需 OpenRouter key；模型 `typesafe/jev-1.13`（别名 `~typesafe/jev-latest`），按输入 token 计费、输出免费，上游仍是 TypeSafe |

切到 OpenRouter 只需要改 **base URL + key** 两处，请求/响应形状不变（"Change the base URL and the API key. Everything else stays the same."）。model.py 里 `post_json(url, key, body)` 的 provider 标签按 URL 推导，所以报错会显示 `OpenRouter provider …` 或 `Model provider …`，一眼能看出打的是哪条路。

**key 放哪**（本机约定）：

```bash
# ~/.zsh_secrets（chmod 600），run-local.sh 会 source 它
export OPENROUTER_API_KEY="sk-or-v1-…"     # 73 字符左右
```

> ⚠️ **`.env` 里的 `${VAR}` 不会被展开。** 项目的 `.env` 写着 `TYPESAFE_API_KEY=${OPENROUTER_API_KEY}`（字面量）：`jev_ultrafast/demo.py` 的 `load_environment()` 只做 `os.environ.setdefault(key, value)`，`examples/run.py` 根本不读 `.env`。所以：
> - 走 `./run-local.sh` → 它会先 `source ~/.zsh_secrets`，真环境变量注入成功，**没问题**；
> - 手工跑 `examples/run.py` → 必须自己带上 `OPENROUTER_API_KEY=…`（见 §6 路径 3），否则就是 401。

---

## 4. 文本层（llm key）怎么配

只在 `TYPE_TEXT` 时需要，任何 **OpenAI 兼容**的 `/chat/completions` 都行。项目 `.env` 里四个键：

| 键 | 本机值 | 说明 |
| --- | --- | --- |
| `TEXT_MODEL_BASE_URL` | `http://43.167.206.51:3000/v1` | OpenAI 兼容 base；**缺省**是 `https://api.deepseek.com/v1` |
| `TEXT_MODEL_API_KEY` | 网关令牌（`sk-…`，51 字符） | 缺了会在 `TYPE_TEXT` 时报 `TYPE_TEXT needs TEXT_MODEL_API_KEY; no text is hardcoded or guessed by the executor.` |
| `TEXT_MODEL` | `deepseek-flash` | 缺省是 `deepseek-chat` |
| `TEXT_MODEL_REASONING` | `none` | 见下 |

`TEXT_MODEL_REASONING` 的分支（model.py 里按值 + base 推断）：

| 值 | 发出去的参数 |
| --- | --- |
| `none` | `{"reasoning": {"enabled": false}}` |
| 其它非空（如 `low`/`high`/`max`） | `{"reasoning": {"effort": "<值>"}}` |
| 空，且 base 含 `api.deepseek.com/` | `{"thinking": {"type": "disabled"}}` |
| 空，其它 base | `{"reasoning": {"effort": "low"}}` |

文本层的硬约束：请求发 `max_tokens: 1024` + `response_format={"type": "json_object"}`，**返回必须恰好是** `{"text": "<非空字符串，≤2000 字符>"}`；多一个键、少一个键、不是 JSON、超长，都会 `ValueError("Text helper returned no valid field value; nothing typed.")`——那是文本层不兼容，不是浏览器坏了。

**配置读起来是谁优先？** 真实环境变量 > `.env`（`setdefault` 语义）。所以临时换模型不用改文件：

```bash
TEXT_MODEL=gpt-5.5 TEXT_MODEL_API_KEY=… ./run-local.sh --url … --goal …
```

---

## 5. 装好之后先体检

别用 `ps` 判断"能不能用"——进程活着不等于链路通。两个脚本都在本 skill 的 `bin/` 下：

```bash
SKILL=$(cd ~/.agents/skills/weicoz-jev-ultrafast && pwd -P)

bash "$SKILL/bin/doctor.sh"                       # 只读体检：执行层 / daemon / 两个 key / inspector
bash "$SKILL/bin/doctor.sh" --fix                 # 缺什么起什么（挑浏览器 → daemon → inspector）
bash "$SKILL/bin/doctor.sh" --fix-browser chrome  # 给指定浏览器打开远程调试开关（会重启它一次，登录态保留）
bash "$SKILL/bin/doctor.sh" --fix-browser edge    # ego 和 Chrome 都不顺手时的下一站
bash "$SKILL/bin/doctor.sh" --net                 # 额外真打一次网络，验证两个 key 活着
bash "$SKILL/bin/smoke.sh"                        # 端到端冒烟：真跑一个任务，用服务端日志判定
env JEV_BROWSER=edge bash "$SKILL/bin/smoke.sh"   # 强制某个浏览器跑同一套冒烟
```

`doctor.sh` 打印 6 段体检，退出码 0 才是全绿。`[2/6]` 段那张表就是执行层解析链的现状：

```
品牌      安装    调试开关   当前档位                 端点
ego       yes     已开       real（在跑）             ✅ 活着（端口 60740）
chrome    yes     已开       toggle（可启动）         ⚠️ 端点文件过期
edge      yes     未开       enable（能自动开开关）   —
```

**`smoke.sh` 才是"能用"的证据**：它起一个本地表单页 + 探针服务，让 agent 填字并点提交，然后检查**服务端是否真的收到提交**（`submit value='Wei'`）。agent 自己说 `DONE` 不算数——`DONE` 只代表它认为做完了。

---

## 6. 三条调用路径

```bash
cd ~/File/git/jev-ultrafast

# 1) inspector 演示（http://127.0.0.1:8766，点 Start demo → Run automatically）
./run-local.sh

# 2) 直接跑一次任务（最常用；--url 之后透传给 examples/run.py）
./run-local.sh --url http://127.0.0.1:8899/form.html \
  --goal "Fill the Full name field with the text Wei, then click Submit"

# 3) Python 库（要读回页面 DOM、录屏、逐轮观察时用）
env OPENROUTER_API_KEY="$(sed -n 's/^export OPENROUTER_API_KEY="\(.*\)"$/\1/p' ~/.zsh_secrets | head -1)" \
    TYPESAFE_BASE_URL=https://openrouter.ai/api TYPESAFE_MODEL=jev-latest \
    TEXT_MODEL_API_KEY="$(sed -n 's/^TEXT_MODEL_API_KEY=//p' .env)" \
    TEXT_MODEL_BASE_URL=http://43.167.206.51:3000/v1 TEXT_MODEL=deepseek-flash TEXT_MODEL_REASONING=none \
    ./.venv/bin/python - <<'PY'
from jev_ultrafast import Agent
agent = Agent("http://127.0.0.1:8899/form.html",
              "Fill the Full name field with the text Wei, then click Submit",
              record_dir=".local-test/run")
for _ in agent.run():
    pass
print("status:", agent.state.get("status"))
print("DOM:", agent.browser.evaluate('JSON.stringify({v:document.querySelector("#fullname")?.value})'))
PY
```

**路径 1、2 靠 `run-local.sh` 帮你做三件事**：`source ~/.zsh_secrets` 拿 `OPENROUTER_API_KEY` → 按解析链挑浏览器并把端点用 `BU_CDP_WS` 交给 browser-harness daemon → 用 `uv run --env-file .env` 喂文本层配置。

> ⚠️ **别 `source ~/.zsh_secrets` 之后再跑**：`source` 进来的变量不 export 到子进程，会直接撞 401。要用就照路径 3 那样显式写在命令前面。
>
> 读页面 DOM 用 `agent.browser.evaluate(js)`（内部走 `Runtime.evaluate` + `returnByValue=True`）；daemon 的客户端**没有** `evaluate()`，别去找它。

---

## 7. 浏览器执行层：一律用你的 profile

### 7.1 为什么不能随便起一个浏览器

Chromium 只在**启动时**读"允许远程调试"这个用户级开关，而且退出时会拿内存里的旧设置回写配置文件。所以：

- 往正在运行的浏览器写开关 → 它退出时覆盖掉，白写；
- 用 `--user-data-dir=…` 起一个全新的 profile → 有 CDP，但**没有你的登录态**；
- Chrome 145+ 之后，对**默认 profile** 开远程调试会被直接拒绝（`DevTools remote debugging requires a non-default data directory`）。

本 skill 的结论：**默认永远用真实 profile**，"无登录态的临时 profile"降级为显式 opt-in。

### 7.2 五档解析链

每个品牌内部按 `real → toggle → enable` 试（三者都是真实 profile），`fresh` 只在你允许时才试：

| 档位 | 什么情况 | 登录态 |
| --- | --- | --- |
| `real` | 该品牌**已经在跑**且带端点，直接用 | ✅ 在 |
| `toggle` | 没在跑，但调试开关已开 → 把它正常启动起来 | ✅ 在 |
| `enable` | 开关没开且它没在跑 → 自动写 `Local State` 打开开关再启动（原文件先备份到 `$TMPDIR`） | ✅ 在 |
| `restart` | 它**正在普通模式下跑**（开关没开，或开关是它启动后才打开的）→ 得先退出它；**默认不打断你的窗口**，只能 `doctor.sh --fix-browser <品牌>`，或 `JEV_ALLOW_RESTART=1` 授权自动重启 | ✅ 在（要重启它一次） |
| `fresh` | 独立 profile `~/.cache/jev-browser/<品牌>-profile`（默认**禁用**） | ❌ 无（仅 `JEV_ALLOW_FRESH=1`） |
| `env` | 调用方已给 `BU_CDP_WS`（最高优先级） | 取决于它 |

浏览器优先级：`ego → chrome → edge → brave → chromium → vivaldi → arc → opera → comet → dia`，最后才会试老式 `127.0.0.1:9222`。

### 7.3 旋钮

| 变量 | 默认 | 作用 |
| --- | --- | --- |
| `JEV_BROWSER=<品牌>` | 空 | **强制**只试这个品牌，各档都失败就报错退出（不会静默退到别的浏览器） |
| `JEV_PROJ` | `~/File/git/jev-ultrafast` | 项目位置 |
| `JEV_BROWSER_LIB` | 自动查找 | 指定 `bin/lib/browser.sh` 路径 |
| `JEV_PROFILE_ROOT` | `~/.cache/jev-browser` | `fresh` 档的 profile 根目录 |
| `JEV_BACKUP_DIR` | `$TMPDIR` | `Local State` 备份位置 |
| `JEV_AUTO_ENABLE` | `1` | 允许 `enable` 档自动写浏览器设置；设 `0` 禁止 |
| `JEV_ALLOW_RESTART` | `0` | 允许为开开关而退出正在运行的浏览器 |
| `JEV_ALLOW_FRESH` | `0` | 才允许无登录态的 `fresh` 档 |
| `JEV_LAUNCH_TIMEOUT` | `25`（秒） | 等浏览器写出 `DevToolsActivePort` 的上限 |
| `JEV_DRY_RUN` | `0` | `1` = 只报告会选谁，不启动、不写文件（`doctor.sh` 无参数时默认走这个） |

> `enable` 档会**改你的浏览器设置**并启动它一次——这是"要登录态就必须付出的代价"，脚本每次都会打印备份路径，想撤销就把备份覆盖回 `<真实 profile>/Local State`。

---

## 8. 常见故障速查

| 症状 | 原因 | 怎么办 |
| --- | --- | --- |
| `fatal: chrome-not-running` | daemon 只扫浏览器**默认** profile 目录，认不出自定义 `--user-data-dir` | 用 `BU_CDP_WS` 把端点显式交给 daemon（`run-local.sh` / `doctor.sh` 已自动做） |
| `DevTools remote debugging requires a non-default data directory` | 对默认 profile 开远程调试，Chrome 145+ 拒绝 | 走本 skill 的解析链：真实 profile 必须先开用户级开关再启动 |
| `Model provider returned HTTP 401` / `OpenRouter provider returned HTTP 401` | key 没进环境（`.env` 里 `${OPENROUTER_API_KEY}` 只是字面量） | 用 `./run-local.sh`，或照 §6 路径 3 显式注入真 key |
| `Text helper returned no valid field value; nothing typed.` | 文本层网关不返回**恰好** `{"text": "…"}` | 换 `TEXT_MODEL` / 换 base；这是文本层问题，不是浏览器 |
| `Start a demo first` | inspector 的 `/api/tick` 之前没 `/api/reset` | 先 reset（场景只有 `flights` / `travel` / `research`） |
| `This run has stopped. Start a fresh demo.` | run 已 `done`，再 tick 就会报这个 | 重新 reset |
| `StalePage: Page changed since this decision. Observe again.` | 决策与执行之间页面变了 | 重跑；反复出现就是把页面想简单了 |
| 自动开开关那步被跳过 / 退到别的浏览器 | 该浏览器**正在普通模式下运行** | `doctor.sh --fix-browser <品牌>`，或 `JEV_ALLOW_RESTART=1` |
| smoke 静默失败、agent 一步没跑 | 曾经是 `set -e` + `grep` 无匹配把脚本带走（已修） | 直接跑 `doctor.sh` 看是哪一层红 |

---

## 9. 能力边界

- 只支持常见 HTML + ARIA 控件。**不支持** shadow root、iframe、canvas、文件上传、新标签页、嵌套滚动、任意键盘组件。
- `DONE` ≠ 任务成功，必须外部校验（服务端日志 > DOM 回读 > 录屏帧）。
- 必须连本机浏览器；云端 / CI 不可用。
- 走 `real` / `toggle` / `enable` 档时动作发生在**你自己的浏览器窗口**里（新开后台标签页，视口 1120×780），别在正忙时抢焦点。

---

## 10. 这个 skill 怎么维护

- 真源在 **`~/File/git/weicoz-skills/skills/weicoz-jev-ultrafast/`**（远端 codeberg）。`~/.skills-manager/skills/`、`~/.agents/skills/`、`~/.codex/skills/`、`~/.claude/skills/` 下都是**软链**指向它，三个 harness 读同一份。
- 提交只能 `git add skills/weicoz-jev-ultrafast`（skills-manager-backup 那个仓库工作区长期有数千项脏改动，**别 `git add -A`**），提交前跑 `./scripts/validate-skills.sh`。
- **凭据只从环境变量读，永远不进仓库。** `~/.zsh_secrets` 里放 key，项目 `.env` 已被 `~/File/git/jev-ultrafast/.gitignore` 忽略；README / SKILL.md 里只写变量名和长度，不写值。
- 改档位、环境变量、密钥位置时，**`README.md` 与 `SKILL.md` 要同步改**；改 `bin/lib/browser.sh` 必须把 `run-local.sh` 与 `doctor.sh` 两个入口都回归一遍。

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 给 agent 看的操作说明（路径、验收纪律、坑表） |
| `README.md` | 本文：给人看的安装 / 配置 / 使用手册 |
| `agents/openai.yaml` | skill 在 Skills Manager 里的显示信息 |
| `bin/lib/browser.sh` | 浏览器解析链真源（档位判定、开关写入、daemon 重绑） |
| `bin/doctor.sh` | 六段体检 + `--fix` / `--fix-browser <品牌>` / `--net` |
| `bin/smoke.sh` | 端到端冒烟，用服务端日志判定成功 |

## 用完关标签页

每次任务都会在你的浏览器里新开一个后台标签页，结束后不会自动关。验证完要关掉：Python 里调 `agent.browser.close()`；漏关的按视口 1120×780 识别后用 CDP 的 `Target.closeTarget` 关掉，尺寸不符的是你自己的标签页，不要动。细节见 `SKILL.md` 的“用完关标签页”一节。
