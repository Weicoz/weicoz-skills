# 小游戏项目 AGENTS.md 模板

复制到项目根目录，替换尖括号内容。只写代码和配置里查不到的东西。

```markdown
# <游戏名>

开工、接手或问下一步时，先读 `weicoz-game-flow`。当前阶段：<阶段 1 找乐趣 / 阶段 2 锁定 / 阶段 3 生产>。

## 目标

- 平台：<微信小游戏 / web-mobile>，竖屏，设计分辨率 <720×1280>。
- 参考：`reference/`（原视频与抽帧）；对标表 `docs/benchmark.md`。

## 已确认规则（不得自行改动）

1. <规则>
2. <规则>

## 待定项

见 `docs/PENDING.md`。待定项不自行拍板，先记录再继续。

## 约定

- 规则核在 `assets/scripts/core/`，不 import 'cc'；规则改动必须补测试（`npm test`）。
- 改完 `.ts` 跑 `weicoz-cocos-dev` 的类型检查；每轮结束用 `weicoz-cocos-run` 给出预览 URL。
- 平台 API（`wx` 等）只在 `assets/scripts/platform/` 里调用。
- funplay MCP 工具档为 custom（含预览工具），一次只开本工程的编辑器。
```
