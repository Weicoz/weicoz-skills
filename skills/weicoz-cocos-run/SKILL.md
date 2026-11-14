---
name: weicoz-cocos-run
version: 1.2.0
description: Cocos Creator 3.8 工程的运行闭环：开工预检、命令行构建（web-mobile / wechatgame）、给用户可点开的预览、自动试玩验收与分级证据。用于“跑起来看看”“我怎么测试”“在 Cocos 里预览给我看”“构建微信小游戏”“验收 demo”。
---

# Cocos 运行闭环

把“代码写完”变成“用户能玩、证据可查”。脚本在本 skill 的 `scripts/`，用 `node <本目录>/scripts/<脚本> --project <工程根>` 调用。

## 1. 预检（每个会话第一次碰 Cocos 前）

运行 `cocos-preflight.mjs`。它检查 Creator 版本、编辑器打开的是哪个工程、[funplay-cocos-mcp](https://github.com/FunplayAI/funplay-cocos-mcp) 扩展与项目 skill（工程目录和 Git 根都查）、MCP 端口与实际可用工具、预览端口。脚本按 macOS 标准安装位置找 Creator；其他系统设 `COCOS_CREATOR_BIN`。

- ❌ 必须先处理。
- “funplay 项目 skill 未安装”：让用户在编辑器 Funplay > MCP Server 选当前客户端，点 **Configure + Skills**。它同时写好本工程的 MCP 连接（Claude Code 写入 `~/.claude.json` 的 `projects[<Git 根>].mcpServers`）并装上 `funplay-cocos-mcp-workflow`、`funplay-cocos-ui-composition`。编辑器内的场景、Prefab、资源操作按这两个 skill 执行。
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

`cocos-build.mjs --platform web-mobile|wechatgame [--release] [--config <json>]`。

- Creator CLI 成功也返回退出码 **36**；32 = 参数无效，34 = 构建异常。脚本以“本次构建生成的产物文件”为成功判据。
- 编辑器正开着同一工程时，先让用户关闭或改用编辑器内构建，避免两个进程争用 `library/`。
- wechatgame：主包 ≤ 4 MB，主包加全部分包 ≤ 30 MB，独立分包 ≤ 4 MB，普通分包不限（微信官方文档 2026-04 版）。脚本按 `game.json` 的 `subpackages` 算出主包，`remote/` 远程包不计入上传。包体以 `--release` 构建为准；debug 构建不压缩，日常预览用。
- 主包超限：把后续关卡、皮肤等放进 Asset Bundle，压缩类型选“小游戏分包”（输出到 `subpackages/`，只能本地）或配成远程包（`remote/` 上传到资源服务器）；可勾选“初始场景分包”。微信不允许下载远程脚本。
- 构建脚本会调用 `cocos-modules.mjs`，列出已启用但工程里找不到使用痕迹的重型模块（Spine、DragonBones、TiledMap、2D 物理、Video、WebView 等）。让用户在“项目设置 → 功能裁剪”关闭后重建。实测一个只用 Graphics 的解谜 demo：debug 5.92 MB → 裁掉 7 个模块 4.21 MB → 再加 `--release` 1.86 MB。
- 真实 appid 只在测试微信 API（登录、分享、广告、支付）时需要。纯玩法用测试号即可。

完成标准：脚本输出“构建已验证”，并记录产物大小与最大文件。

## 3. 交给用户预览

用户问“怎么测试”“预览给我看”时，直接给可点开的入口，不让用户自己摸索：

| 用户要的 | 做法 |
| --- | --- |
| 编辑器里看 | MCP 路径：`set_preview_mode(mode="gameView")` → `run_project_preview` → `capture_game_screenshot` 回传截图。CLI 路径：告诉用户点编辑器顶部 ▶，并说明尚未由你确认画面。 |
| 浏览器里玩 | 后台运行 `cocos-preview.mjs --open`：构建 web-mobile、起本地服务并打开浏览器。不需要编辑器。编辑器开着时也可直接给 `http://127.0.0.1:7456/`。 |
| 手机浏览器里玩 | `cocos-preview.mjs --lan`，把输出的局域网地址给用户。该地址对同一网络可见，用户玩完后停掉进程。 |
| 微信里玩 | wechatgame 构建后，用微信开发者工具导入 `build/wechatgame`。`wechat-devtools` MCP 需要用户先开“设置 → 安全设置 → 服务端口”。 |

截图确认：`playwright-cli open <url>` → `resize 390 844` → 等 3–4 秒 → `screenshot`；`eval "cc.director.getScene().name"` 返回场景名即说明引擎已启动。

完成标准：你自己截图确认画面出来，并且用户拿到了 URL 或操作入口。

## 4. 自动试玩验收

浏览器路径用 `playwright-cli`：`open <url>` → `resize 390 844` → `run-code --filename=<试玩脚本>`。读取状态和发起操作都通过游戏暴露的**测试钩子**，不靠反复 eval 探查节点树。钩子约定与试玩脚本模板见 `references/playtest-hook.md`。工程还没有钩子时，先让实现方按约定加上。

每条验收写成：步骤 → 期望 → 证据（状态 JSON 或截图路径）→ 通过 / 失败。另查一遍浏览器控制台或编辑器日志，有报错就写进缺陷。

缺陷按影响分级，先修高级别：

| 级别 | 含义 |
| --- | --- |
| 阻塞 | 启动不了、玩不了、崩溃、重开坏掉 |
| 高 | 核心循环能跑，但玩家频繁遇到错误、严重看不懂、数值明显失衡 |
| 中 | 可见 bug、反馈不清、节奏问题 |
| 低 | 外观、文案、不影响玩的清理 |

修复后重跑原失败场景，再跑一个相邻场景，并写明哪些没重测。

试玩只在 debug 构建上做：`--release` 会剔除 `DEBUG` 包住的测试钩子。release 包只验证启动与包体。

**发版回归清单**（竖切门与每次提审前全部跑一遍）：

1. 规则核单测（项目的 `npm test`）与生成器对标指标测试。
2. `cocos-typecheck.mjs` 通过。
3. debug 构建上试玩脚本跑完全部关卡：每关用 `solution()` 通关，再验证失败与重开。
4. `--release` wechatgame 构建：主包与总包在限额内，`cocos-modules.mjs` 无可裁剪项或已说明原因。
5. 切后台再回来（`Game.EVENT_HIDE/SHOW`）：计时和音乐暂停与恢复。
6. 存档：通关后刷新页面，进度仍在。

## 5. 汇报分级

验证状态只用以下级别，逐级累积，不得越级：

1. **构建已验证**：产物生成。
2. **已启动**：截图证明进入首屏。
3. **核心循环已验证**：首次操作、得分或进度变化、胜负与重开都有证据。
4. **目标平台已验证**：微信开发者工具或真机跑通第 3 级。

阶段要求的级别见 `weicoz-game-flow` 的阶段门。没跑的检查写“未验证”，并写明缺什么。“代码看起来对”“构建通过但没打开”“窄范围日志里没报错”都不算证据。
