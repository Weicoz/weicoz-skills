# 小游戏项目 AGENTS.md 模板

复制到项目根目录，替换尖括号内容。只写代码和配置里查不到的东西。

```markdown
# <游戏名>

开工、接手或问下一步时，先读 `weicoz-game-flow`。当前阶段：<阶段 1 找乐趣 / 阶段 2 锁定 / 阶段 3 生产>。

项目阶段与检查点对应（项目有自己的 P0、P1… 编号时必填）：<例：P1 = 阶段 1，结束于 H2 灰盒门；P2、P3 = 阶段 3，各自结束时做一次 H3 式验收包；P4 起接平台>。

## 目标

- 平台：<微信小游戏 / web-mobile>，竖屏，设计分辨率 <720×1280>。
- 参考：`reference/`（原视频与抽帧）；对标表 `docs/benchmark.md`。

## 已确认规则（不得自行改动）

1. <规则>
2. <规则>

## 待定项

见 `docs/PENDING.md`。待定项不自行拍板，先记录再继续。

## 约定

- Cocos 工程目录：<`.` / `apps/cocos`>（各脚本的 `--project` 指向这里）。
- 规则核在 <`assets/scripts/core/` / `packages/<name>-core`（经软链导入 assets）>，不 import 'cc'；规则改动必须补测试（`npm test`）。
- 改完 `.ts` 跑 `weicoz-cocos-dev` 的类型检查；每轮结束用 `weicoz-cocos-run` 给出预览 URL。
- 平台 API（`wx` 等）只在 `assets/scripts/platform/` 里调用。
- funplay MCP 的 `funplay-cocos-mcp.config.json` 已开预览与搭场景工具（预检无工具缺口），一次只开本工程的编辑器。

## 验证约定

通用规则见 `weicoz-verify`；本项目的命令如下。

- 适配器：`cocos`（`weicoz-cocos-run`）。
- 功能地图：`tests/e2e/FEATURES.md`。
- 流程清单与档位：<每条流程一行：脚本名、所属档位（快检 / 全检）>；`tests/e2e/` 下 `_` 开头的是辅助文件，一次性排查脚本不放这里。
- 快检（改完一轮后）：`node <weicoz-cocos-run>/scripts/cocos-verify.mjs --project <Cocos 工程目录> --quick`
- 全检（阶段门、合并前、收尾）：`node <weicoz-cocos-run>/scripts/cocos-verify.mjs --project <Cocos 工程目录>`
- 结论行：最后一行；退出码 0 通过、1 不通过、3 未验证。
- 门禁项（并入全检，不另跑）：release 主包 ≤ 4 MB；发版回归清单见 `weicoz-cocos-run` 第 4 节，竖切门与每次提审前全部跑一遍。
- 目标环境：微信开发者工具或真机（需用户开服务端口或提供真机）。
- 高风险目录：<规则核、存档格式、平台接入；无则写“无”>
```
