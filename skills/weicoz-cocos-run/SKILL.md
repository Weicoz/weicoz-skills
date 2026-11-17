---
name: weicoz-cocos-run
version: 1.11.0
description: Cocos Creator 3.8 工程的运行闭环：开工预检、命令行构建（web-mobile / wechatgame）、给用户可点开的预览、自动试玩验收与分级证据。用于“跑起来看看”“我怎么测试”“在 Cocos 里预览给我看”“构建微信小游戏”“验收 demo”。
---

# Cocos 运行闭环

把“代码写完”变成“用户能玩、证据可查”。脚本在本 skill 的 `scripts/`，用 `node <本目录>/scripts/<脚本> --project <工程根>` 调用。

## 速查：要做什么 → 跑哪条命令 → 看哪一行

脚本都在本 skill 的 `scripts/`，`--project` 指向含 `assets/` 的 Cocos 工程目录。通用约定（结论行、两档、修复上限、四级状态）在 `weicoz-verify`，本文件只写 Cocos 游戏特有部分。

| 要做什么 | 命令 | 看哪一行 |
| --- | --- | --- |
| 会话开始 | `node cocos-preflight.mjs --project <工程>` | 有 ❌ 先处理；⚠️ 决定走 MCP 还是 CLI |
| 改完代码（日常） | `node cocos-verify.mjs --project <工程> --quick` | 最后一行“结论：通过 / 不通过（失败：…）/ 未验证（缺：…）” |
| 阶段门、合并前 | `node cocos-verify.mjs --project <工程>` | 同上，并看“视觉巡检”行给的联系图 |
| 给用户手机试玩 | 后台运行 `node cocos-preview.mjs --project <工程> --no-build --lan` | 只发带 ✅ 的地址 |
| 只跑某个试玩脚本 | `node cocos-playtest.mjs --project <工程> --script tests/e2e/<名>.mjs` | ✅/❌ 行与“失败步骤” |
| 查包体 | `node cocos-build.mjs --project <工程> --platform wechatgame --release` | “主包 x MB” |

`cocos-verify.mjs` 是 `weicoz-verify` 第 2 节的适配器：最后一行为唯一结论，退出码 0 通过、1 不通过、3 未验证（缺 CocosCreator 等无法构建的环境，设 `COCOS_CREATOR_BIN` 后重跑）。不通过时的修复规则见 `weicoz-verify` 第 4 节（同一项连续 2 次修不好即停下报告）。多个代理可以同时运行它：试玩端口和浏览器会话按空闲端口自动分配。脚本可以直接执行，不需要先读它依赖的其他 skill。

## 1. 预检（每个会话第一次碰 Cocos 前）

运行 `cocos-preflight.mjs`。它检查 Creator 版本、编辑器打开的是哪个工程、[funplay-cocos-mcp](https://github.com/FunplayAI/funplay-cocos-mcp) 扩展与项目 skill（工程目录和 Git 根都查）、MCP 端口与实际可用工具、预览端口。脚本按 macOS 标准安装位置找 Creator；其他系统设 `COCOS_CREATOR_BIN`。

- ❌ 必须先处理。
- “funplay 项目 skill 未安装”：两个 skill 是 `funplay-cocos-mcp-workflow`、`funplay-cocos-ui-composition`，编辑器内的场景、Prefab、资源操作按它们执行。装法二选一：
  - 直连客户端：让用户在编辑器 Funplay > MCP Server 选当前客户端，点 **Configure + Skills**。它同时写本工程的 MCP 连接（Claude Code 写入 `~/.claude.json` 的 `projects[<Git 根>].mcpServers`）并装 skill。
  - 经聚合器（已有 MCP 连接，只缺 skill）：编辑器开着时由你经 `execute_editor_script`（带 `expected_context`）只装 skill，不改客户端配置。`clientId` 取 `claude_code`、`codex`、`kimi`、`deepseek_harness` 等：

    ```js
    const ps = require(path.join(os.homedir(), '.CocosCreator/builtin-extensions/<Creator 版本>/funplay-cocos-mcp/lib/project-skills.js'))
    return ['funplay-cocos-mcp-workflow', 'funplay-cocos-ui-composition'].map((skillName) =>
      ps.updateBuiltInProjectSkill(context.projectPath, { clientId: 'claude_code', skillName, onlyIfMissing: true, extensionVersion: '<扩展版本>' }).installed)
    ```

  装完把 skill 目录提交进项目仓库。
- “另有工程占用编辑器”：MCP 固定端口会连到那个工程。让用户关掉它，或说明本次只走 CLI 路径。
- “MCP 工具档缺 …”：预检按扩展 `docs/TOOLS.md` 复现 funplay 的暴露规则，列出预览/试玩、搭场景/UI 两组缺的工具。`enabledToolCategories` 与 `enabledTools` 在 `core` 档下同样生效。在工程根的 `funplay-cocos-mcp.config.json` 加分类（保留原有 `host`、`port`、`autostart` 等字段）：

  ```json
  { "enabledToolCategories": ["build", "input", "screenshots", "scene", "components", "prefabs", "ui"] }
  ```

  改后在编辑器 Funplay > MCP Server 点 Restart，再跑预检确认无缺口。`"toolProfile": "full"` 也可以，但会暴露全部 106 个工具，含破坏性工具。`COCOS_MCP_PROFILE` 环境变量以编辑器进程的启动环境为准，预检只能读到当前 shell 的值。

MCP 连接方式决定写操作怎么调用：

| 接入方式 | 地址 | 写操作 |
| --- | --- | --- |
| 直连（Configure + Skills 生成） | `http://127.0.0.1:<port>/mcp/project/<project-id>/` | 直接调用 |
| 经 MCP 聚合器，或旧的 `/mcp` 地址 | 固定端口（各工程配置 `"portMode": "fixed"`，一次只开一个工程） | 必须带 `expected_context` |

- 旧地址的取值方法：先调一个只读工具（如 `get_project_info`）。结果的 `projectContext` 里有 `project_path` 和 `expected_context`。`project_path` 与本工程一致后，才把 `expected_context` 加到之后每个变更类调用的参数里；不一致就停下，不拿别的工程的 token 绕过拒绝。只读调用不需要。
- 报 `PROJECT_CONTEXT_REQUIRED`：缺 `expected_context`，按上面补上。
- 报 `PROJECT_CONTEXT_MISMATCH` / `EDITOR_INSTANCE_CHANGED`：编辑器换了工程或重启过，重新核对并取值。
- 报 `connection refused`：编辑器没开或 MCP 没启动，重跑预检，改走 CLI 路径。不反复重试同一调用。

查某个工具属于哪一档、哪个分类：读扩展目录的 `docs/TOOLS.md`（位置见预检输出的“funplay 扩展”行）。`get_tool_catalog` 返回内容很大，只在 TOOLS.md 与实际暴露不一致时调用，并用 `jq` 过滤结果文件。

完成标准：预检无 ❌；已写明本次走 **MCP 路径** 还是 **CLI 路径** 及原因（例如“编辑器未开，走 CLI”）。MCP 路径还要求预检无工具缺口。

## 2. 构建

`cocos-build.mjs --platform web-mobile|wechatgame [--release] [--game <前缀>] [--config <json>]`。`--help` 只打印用法，不启动构建。

- Creator CLI 成功也返回退出码 **36**；32 = 参数无效，34 = 构建异常。脚本以“本次构建生成的产物文件”为成功判据。
- 编辑器正开着同一工程时不跑命令行构建，避免两个进程争用 `library/`。funplay 没有“执行构建”的工具，代理无法替用户点编辑器内构建：编辑器是你打开的且场景已保存，就关掉它再构建；是用户开的，请用户关闭或在编辑器内构建。
- wechatgame：主包 ≤ 4 MB，主包加全部分包 ≤ 30 MB，独立分包 ≤ 4 MB，普通分包不限（微信官方文档 2026-04 版）。脚本按 `game.json` 的 `subpackages` 算出主包，`remote/` 远程包不计入上传。包体以 `--release` 构建为准；debug 构建不压缩，日常预览用。
- 插画、关卡这类随内容增长的资源，从设为 Asset Bundle 起就配成“小游戏分包”，不要等主包超限再改。实测：10 张占位插画进主包后主包从 1.86 MB 涨到 3.05 MB。
- 主包超限：把后续关卡、皮肤等放进 Asset Bundle，压缩类型选“小游戏分包”（输出到 `subpackages/`，只能本地）或配成远程包（`remote/` 上传到资源服务器）；可勾选“初始场景分包”。微信不允许下载远程脚本。
- 构建脚本会调用 `cocos-modules.mjs`，列出已启用但工程里找不到使用痕迹的重型模块（Spine、DragonBones、TiledMap、2D 物理、Video、WebView 等）。在“项目设置 → 功能裁剪”关闭后重建；不开编辑器时按脚本提示改 `engine.json` 的 `cache` 分组键（只删 `includeModules` 会在构建时被还原）。实测一个只用 Graphics 的解谜 demo：debug 5.92 MB → 裁掉 7 个模块 4.21 MB → 再加 `--release` 1.86 MB。
- AppID：Cocos 构建产物的 `project.config.json` 默认是 Cocos 的 appid，开发者工具与上传都不认。`--game <前缀>`（或 `GAME_ENV_PREFIX`）让脚本按 `<前缀>_WECHAT_APPID` 写入；`--release` 构建遇到默认 appid 直接失败。
- 纯玩法用测试号；测试 API（登录、分享、广告、支付）才要真实 appid。
- 上传微信走 `miniprogram-ci`，密钥与白名单见 `weicoz-cocos-dev/references/wechat-platform.md` “代码上传”。

完成标准：脚本输出“构建已验证”，并记录产物大小与最大文件。

## 3. 交给用户预览

用户问“怎么测试”“预览给我看”时，直接给可点开的入口，不让用户自己摸索：

| 用户要的 | 做法 |
| --- | --- |
| 编辑器里看 | MCP 路径：`open_scene(target="db://assets/<启动场景>.scene")`（编辑器常打开空的 Untitled 场景，预览“当前场景”就是黑屏）→ `set_preview_mode(mode="gameView")` → `run_project_preview` → `capture_game_screenshot`。该截图区域可能偏移、裁掉画面底部，只作“已启动”证据；完整画面以浏览器截图为准。CLI 路径：告诉用户点编辑器顶部 ▶，并说明尚未由你确认画面。 |
| 浏览器里玩 | 后台运行 `cocos-preview.mjs --open`：构建 web-mobile、起本地服务并打开浏览器。不需要编辑器。编辑器开着时也可直接给 `http://127.0.0.1:7456/`。 |
| 手机浏览器里玩 | `cocos-preview.mjs --lan`，只给标“默认网卡”的那个地址，并先在本机 `curl` 一次确认返回 200。用户说打不开：重跑取新地址（网络切换后地址会变）。该地址对同一网络可见，用户玩完后停掉进程。 |
| 微信里玩 | debug wechatgame 构建后，`wechat-devtools` MCP `launch(projectPath=<工程>/build/wechatgame)`。需要开发者工具已登录并开“设置 → 安全设置 → 服务端口”：未开时报“服务端口已关闭”，命令行 `cli auto` 同样受阻。还需要有效 AppID：Cocos 默认的 `wx6ac3f5090a6b99c5` 和 `touristappid` 都会报“不存在此 AppID”；设 `<GAME>_WECHAT_APPID`（小游戏测试号即可，构建加 `--game <前缀>`）后构建脚本自动写入产物。这几项都属于 `weicoz-game-flow` 的 H0，由预检一次列出。这一步请用户开，或请用户授权 Computer Use 操作开发者工具后由你打开。 |

截图确认：`playwright-cli open <url>` → `resize 390 844` → 等 3–4 秒 → `screenshot`；`eval "cc.director.getScene().name"` 返回场景名即说明引擎已启动。

完成标准：你自己截图确认画面出来，并且用户拿到了 URL 或操作入口。

## 4. 自动试玩验收

1. **测试钩子**：新工程把 `references/TestHook.ts` 复制到 `assets/scripts/game/TestHook.ts`，在主控组件 `start()` 里调用 `installTestHook({...})`，逐个实现接口里的方法（`idle`、`panelOpen`、`residue` 不能省）。工程已有自己的钩子时不改名，另写一个适配器调用 `installTestHook`，把已有方法接上；在项目 `AGENTS.md` 记下钩子与脚本位置。
2. **试玩脚本**：
   - 逐关通关：复制 `references/levels-template.mjs` 到 `tests/e2e/levels.mjs`，只改开头两个按钮名。
   - 核心循环（被挡、失败、重开、存档等）：按 `references/playtest-hook.md` 的模板写 `tests/e2e/playtest.mjs`。
   - 脚本放 `tests/e2e/`，`cocos-verify.mjs` 会自动全部运行；以 `_` 开头的 `.mjs` 是辅助文件，不运行。一次性排查脚本不放 `tests/e2e/`。
3. **运行**：跑 `cocos-verify.mjs`。它构建、起预览、用手机尺寸跑全部脚本、采样帧率、输出每关点击数与耗时、拼出联系图 `temp/contact.png`（超过 12 张分页为 `contact-1.png`、`contact-2.png`…，全部路径都会打印，逐张看；桌面图固定在最后一张）。
4. **两档回归**：日常 `--quick`（只跑 `playtest.mjs`，并给脚本设 `PLAYTEST_FAST=1`；`levels-template.mjs` 读它开钩子快速模式，自写脚本要读它才会加速）；阶段门前不带 `--quick`（全部脚本、真实动画、release 包体，不设 `PLAYTEST_FAST`）。
5. **档位与未验证**：`npm test` 会收到 `VERIFY_TIER=quick|full`，项目测试据此调规模。`package.json` 没有 `test` 脚本、或用了 `--no-release` / `--script` 缩小范围时，结论为“未验证”（退出码 3），不得写成通过。只有环境高负载且失败全是超时类，单测才重跑 1 次，重跑通过标“不稳定：首轮超时”。

每条验收按 `weicoz-verify` 第 7 节写成一行。另查一遍浏览器控制台或编辑器日志，有报错就写进缺陷。

**视觉巡检**：脚本全部通过后，看联系图 `temp/contact.png`（按名字排序拼好的关键截图），通用清单见 `weicoz-verify` 的 `references/visual-checklist.md`。不能看图时用 `modlens` 转文字；仍无法判断的写“视觉巡检：未验证”，交制作人看验收包。实测例子：30 关脚本全过，但通关截图里插画上残留了无箭头格的遮盖块。游戏特有项：

- 残留：遮盖、旧棋盘、弹窗未消失。
- 遮挡：提示文字压在可点区域、换盘时新旧棋盘重叠、HUD 被刘海或胶囊按钮挡住。
- 字号：手机上低于约 24 设计像素。
- 尺寸极值：最小和最大棋盘各看一张。
- 风格：项目有 `docs/ui-style.md` 时按它核对；没有就在验收包写“界面尚无风格规范”。

每发现一类画面缺陷，同时给钩子的 `residue()` 加上对应计数，变成脚本断言。

联系图末尾带一张桌面横屏截图（1440×900），用来看竖屏游戏在宽窗口下是否按 9:16 居中、两侧留深色边。这张图在独立桌面上下文里截（viewport 1440×900、deviceScaleFactor 1、isMobile/hasTouch 为 false、桌面 Chrome UA），不是在手机上下文里 resize。所以图上两侧深色、中间完整竖条首页才算对；画面铺满宽度、被放大裁切就是适配没做。

**桌面横屏适配**：竖屏游戏在桌面浏览器横屏窗口下，用 `ResolutionPolicy.ContainerStrategy.PROPORTION_TO_FRAME` + `SHOW_ALL`。只在非移动端且窗口比设计比例宽时启用；手机尺寸下启用会改变试玩脚本的点击坐标。

**环境负载**：规则见 `weicoz-verify` 第 4 节第 4、6 条。`cocos-verify.mjs` 开跑前读 1 分钟负载，偏高时输出首行“⚠️ 负载高”。单元测试失败全是超时类时自动重跑一次，重跑通过记“✅（首轮负载超时，已重跑通过）”。浏览器自动化用完立即关闭标签页或任务空间。

体验类问题按 `weicoz-verify` 第 7 节处理：把 `cocos-verify.mjs` 输出的帧率、每关点击数和耗时抄进验收包，交给制作人判断。

缺陷分级与修复后重测规则见 `weicoz-verify` 第 7 节；游戏侧“阻塞”含启动不了、玩不了、崩溃、重开坏掉。

试玩只在 debug 构建上做：`--release` 会剔除 `DEBUG` 包住的测试钩子。release 包只验证启动与包体。

**发版回归清单**（竖切门与每次提审前全部跑一遍）：

1. 规则核单测（项目的 `npm test`）与生成器对标指标测试。
2. `cocos-typecheck.mjs` 通过。
3. `cocos-verify.mjs`（不带 `--quick`）结论为“通过”：其中逐关脚本通完全部关卡，`playtest.mjs` 覆盖失败与重开。
4. `--release` wechatgame 构建：主包与总包在限额内，`cocos-modules.mjs` 无可裁剪项或已说明原因。
5. 切后台再回来（`Game.EVENT_HIDE/SHOW`）：计时和音乐暂停与恢复。
6. 存档：通关后刷新页面，进度仍在。

### 需要用户或真机的步骤

- 平台后台（微信、抖音）的登录、扫码、人脸、验证码、付款、协议与最终提交由用户做。自动化遇到就停下，把页面停在可操作处，写清“做什么、在哪页、做完回什么”；二维码有时效，弹窗交给用户现场触发。
- 抖音图标上传页面刷新即丢，需真人选文件并立刻保存草稿。
- 长按、手势等有时间或压力的交互，自动化里可能触发不了：验收清单标“需真机”，截图图注如实写“待补”。
- 微信提审截图在微信真机里截（带胶囊与游戏名），要求见 `weicoz-cocos-dev/references/wechat-platform.md` “上线前检查”。
- 桌面宽屏截图用非移动上下文（`cocos-playtest.mjs` 已生成 `temp/playtest-zz-desktop.png`），桌面画面以它为准。

## 5. 汇报分级

四级状态的定义、证据要求与汇报格式见 `weicoz-verify` 第 5、10 节。游戏侧的具体含义：

- **核心流程**：首次操作、得分或进度变化、胜负与重开都有证据。
- **目标环境**：微信开发者工具或真机。

阶段要求的级别见 `weicoz-game-flow` 的阶段门。
