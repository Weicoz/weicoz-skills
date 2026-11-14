---
name: weicoz-cocos-dev
version: 1.0.0
description: Cocos Creator 3.8 小游戏代码实现约定：规则核与视图分层、主控组件、触控输入、测试钩子、Cocos 坑点与离线类型检查。用于写或改 Cocos 玩法代码、搭单场景 demo、排查脚本在编辑器或预览里不生效。
---

# Cocos 玩法实现

编辑器内操作（建节点、挂组件、改 Prefab、导入资源、读回验证）按工程内的 `funplay-cocos-mcp-workflow` 与 `funplay-cocos-ui-composition` 执行。没装时先按 `weicoz-cocos-run` 第 1 节预检。本文件只管代码怎么写。

## 分层

| 层 | 位置 | 规则 |
| --- | --- | --- |
| 规则核 | `assets/scripts/core/` | 纯 TS，不 `import 'cc'`，不读时间和随机数全局（由调用方传入 seed、dt）。Node 直接跑测试。 |
| 关卡数据 | `assets/scripts/core/levels/` 或 `assets/resources/levels/*.json` | 生成器离线产出并写入；运行时只读。 |
| 视图 | `assets/scripts/view/` | 主控组件 + 渲染辅助。只调用规则核，不自己判胜负。 |
| 平台 | `assets/scripts/platform/` | 微信、抖音等 API 的唯一出口。其他层不直接碰 `wx`。 |

规则核放在 `assets/` 内，编辑器、构建和 Node 测试共用同一份源码，不需要软链或拷贝。Node 测试用 `tsc -p tsconfig.test.json` 编到 `temp/` 再 `node --test`，或用 vitest 直接跑。

## 主控组件

单场景 demo 用一个挂在 Canvas 上的主控组件：

1. `start()`：读关卡 → 创建规则核运行时 → 代码创建棋盘与 HUD 节点 → 挂测试钩子（约定见 `weicoz-cocos-run` 的 `references/playtest-hook.md`）。
2. 输入：`node.on(Node.EventType.TOUCH_END, …)`，用 `UITransform.convertToNodeSpaceAR(event.getUILocation())` 转成棋盘坐标，再交给规则核。
3. 规则核返回结果 → 播动画 → 动画期间 `locked = true`，丢弃新输入。
4. 计时放在 `update(dt)`，弹窗或暂停时停表；不用 `setInterval`。
5. 胜负、扣命只读规则核状态，视图层不重复计算。

需要人在编辑器里调布局的 UI（主菜单、商店、结算页）做成 Prefab，按 `funplay-cocos-ui-composition` 装配。棋盘这类数据驱动内容保持代码创建。

## 坑点

- `.meta`、`.scene`、`.prefab` 不手写、不复制。新增脚本后由编辑器导入（MCP 用 `refresh_assets`），或由 CLI 构建导入。复制资源时不复制 `.meta`，否则 UUID 冲突。
- 组件类名在构建产物里可能被改写。运行时查找用 `getComponent('MyComponent')` 字符串形式，或走测试钩子；web-mobile 中 `getComponent(cc.UITransform)` 曾失败，`cc.UITransformComponent` 才成功。
- 调试代码用 `import { DEBUG } from 'cc/env'` 包住，发布构建自动剔除。
- 竖屏手机游戏的设计分辨率写明（如 720×1280，适配宽度），在“项目设置 → 项目数据”里设，不留模板默认值。
- `Graphics` 画线：`lineCap`、`lineJoin` 设为 `ROUND` 才有圆头折线；百条以内的线每帧 `clear()` 重画可以接受，更多时改为只重画变化的节点。
- 编辑器预览不刷新新脚本：先看编辑器控制台是否有编译错误，再用 MCP `run_script_diagnostics`；不要靠重启试错。

## 自检

改完 `.ts` 必跑：

```bash
node <本目录>/scripts/cocos-typecheck.mjs --project <工程根>
```

它用本机 Creator 自带的 `cc.d.ts` 离线检查，不需要打开编辑器。找不到声明时按提示设 `COCOS_ENGINE_DTS` 或 `COCOS_CREATOR_BIN`。规则核改动另跑项目自己的单元测试。运行效果按 `weicoz-cocos-run` 验证。
