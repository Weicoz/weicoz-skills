---
name: weicoz-cocos-run
version: 1.0.0
description: Cocos Creator 3.8 工程的运行闭环：开工预检、命令行构建（web-mobile / wechatgame）、给用户可点开的预览、自动试玩验收与分级证据。用于“跑起来看看”“我怎么测试”“在 Cocos 里预览给我看”“构建微信小游戏”“验收 demo”。
---

# Cocos 运行闭环

把“代码写完”变成“用户能玩、证据可查”。脚本在本 skill 的 `scripts/`，用 `node <本目录>/scripts/<脚本> --project <工程根>` 调用。

## 1. 预检（每个会话第一次碰 Cocos 前）

运行 `cocos-preflight.mjs`。它检查 Creator 版本、编辑器打开的是哪个工程、[funplay-cocos-mcp](https://github.com/FunplayAI/funplay-cocos-mcp) 扩展与项目 skill、MCP 端口与工具档、预览端口。

- ❌ 必须先处理。
- “funplay 项目 skill 未安装”：让用户在编辑器 Funplay > MCP Server 选当前客户端，点 **Configure + Skills**。它同时写好本工程的 MCP 连接（Claude Code 写入 `~/.claude.json` 的 `projects[<Git 根>].mcpServers`）并装上 `funplay-cocos-mcp-workflow`、`funplay-cocos-ui-composition`。编辑器内的场景、Prefab、资源操作按这两个 skill 执行。
- “另有工程占用编辑器”：MCP 固定端口会连到那个工程。让用户关掉它，或说明本次只走 CLI 路径。
- “MCP 工具档缺少预览/试玩工具”：`core` 档没有 `run_project_preview`、`capture_game_screenshot`、`simulate_preview_input`、`invoke_component_method`。在工程根的 `funplay-cocos-mcp.config.json` 改为：

  ```json
  { "toolProfile": "custom", "enabledTools": ["run_project_preview", "set_preview_mode", "capture_game_screenshot", "simulate_preview_input", "invoke_component_method", "save_current_scene", "refresh_assets", "check_asset_ready", "find_nodes", "inspect_node", "add_component", "set_component_property"] }
  ```

  保留原有 `host`、`port`、`autostart` 字段。改后需在编辑器 Funplay > MCP Server 点 Restart。
- MCP 调用报 `connection refused` 或 `PROJECT_CONTEXT_REQUIRED`：重跑预检，按结果切换路径，不反复重试同一调用。
- 查工具是否存在、属于哪一档：读扩展目录的 `docs/TOOLS.md`（位置见预检输出的“funplay 扩展”行）。`get_tool_catalog` 返回约 18 万字符，只在 TOOLS.md 与实际暴露不一致时调用，并用 `jq` 过滤结果文件。

完成标准：预检无 ❌，并已确定本次走 **MCP 路径** 还是 **CLI 路径**。

## 2. 构建

`cocos-build.mjs --platform web-mobile|wechatgame [--release] [--config <json>]`。

- Creator CLI 成功也返回退出码 **36**；32 = 参数无效，34 = 构建异常。脚本以“本次构建生成的产物文件”为成功判据。
- 编辑器正开着同一工程时，先让用户关闭或改用编辑器内构建，避免两个进程争用 `library/`。
- wechatgame：主包 ≤ 4 MB、总包 ≤ 20 MB。超 4 MB 先查引擎模块：`cocos-js/_virtual_cc-*.js` 超过 3 MB 或出现 `spine-*.wasm`，说明没裁剪。在“项目设置 → 功能裁剪”关掉未用模块（3D、Spine、DragonBones、物理、粒子 3D 等），再 `--release` 对比。
- 真实 appid 只在测试微信 API（登录、分享、广告、支付）时需要。纯玩法用测试号即可。

完成标准：脚本输出“构建已验证”，并记录产物大小与最大文件。

## 3. 交给用户预览

用户问“怎么测试”“预览给我看”时，直接给可点开的入口，不让用户自己摸索：

| 用户要的 | 做法 |
| --- | --- |
| 编辑器里看 | MCP 路径：`set_preview_mode(mode="gameView")` → `run_project_preview` → `capture_game_screenshot` 回传截图。CLI 路径：告诉用户点编辑器顶部 ▶，并说明尚未由你确认画面。 |
| 浏览器里玩 | 编辑器预览 `http://127.0.0.1:7456/`；或构建 web-mobile 后 `python3 -m http.server 8123 -d build/web-mobile`，给 `http://127.0.0.1:8123/`。用 `open <url>` 帮用户打开。 |
| 手机 / 微信里玩 | wechatgame 构建后，用微信开发者工具导入 `build/wechatgame`。`wechat-devtools` MCP 需要用户先开“设置 → 安全设置 → 服务端口”。 |

完成标准：你自己截图确认画面出来，并且用户拿到了 URL 或操作入口。

## 4. 自动试玩验收

浏览器路径用 `playwright-cli`：`open <url>` → `resize 390 844` → `run-code --filename=<试玩脚本>`。读取状态和发起操作都通过游戏暴露的**测试钩子**，不靠反复 eval 探查节点树。钩子约定与试玩脚本模板见 `references/playtest-hook.md`。工程还没有钩子时，先让实现方按约定加上。

每条验收写成：步骤 → 期望 → 证据（状态 JSON 或截图路径）→ 通过 / 失败。

## 5. 汇报分级

验证状态只用以下级别，逐级累积，不得越级：

1. **构建已验证**：产物生成。
2. **已启动**：截图证明进入首屏。
3. **核心循环已验证**：首次操作、得分或进度变化、胜负与重开都有证据。
4. **目标平台已验证**：微信开发者工具或真机跑通第 3 级。

阶段要求的级别见 `weicoz-game-flow` 的阶段门。没跑的检查写“未验证”，并写明缺什么。
