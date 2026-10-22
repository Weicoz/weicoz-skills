---
name: weicoz-ui-studio
version: 1.1.1
license: MIT
description: 基于完整开源设计流程，设计与改进网站、App、后台及组件；提供多方向对比、真实素材检索、截图取证、交互与动效打磨、独立评审和任务验收。不用于无界面变化的业务实现。
---

# 界面工作室

以完整 Free 能力为底线，叠加交互、组件、工作区与评审增强。项目栈、用户选择和品牌约束优先；视觉、功能、参考一致性分别验收。

## 默认流程与分支

先读[完整基础流程](references/free/workflow.md)，按任务分支读下表；不能用短摘要取代完整规范。点名元素且改法清楚的小改直接做，只验证受影响区域。

| 任务 | 完整基线（必须读对应分支） | 增强 |
| --- | --- | --- |
| 新界面、重设计、方向与版式比较 | [方向方法](references/free/design-direction.md)、[说服型骨架](references/free/direction-persuasion.md)、[完整对比页](references/free/style-explorer.md) | [方向补充](references/direction.md) |
| 视觉、字体、空间、图像、真实材质、视频、3D | [视觉语言](references/free/visual-language.md)、[素材](references/free/media.md) | [精修与来源](references/visual.md) |
| 基本动效、转场、弹簧、手感 | [完整动效](references/free/motion.md) | [交互演出补充](references/motion.md) |
| 落地页、品牌页、发布页、展览页 | [滚动叙事](references/free/scroll-narrative.md) | [动效补充](references/motion.md) |
| 截图还原与窄屏延伸 | [布局与视口](references/free/layout-and-viewport.md) | [严格一致性](references/review.md) |
| 游戏、抽奖、计时养成、强手势 | [游玩与素材](references/free/play.md)，按其中链接读素材/3D | [场景与状态](references/game.md) |
| 表单、状态、浮层、响应式、后台 | 上述视觉与动效基线 | [交互](references/interaction.md)、[工作区](references/workspace.md) |
| 现有项目优化、改流程、加功能 | 完整基础流程的范围选择、受影响视觉基线 | [存量改造](references/renovation.md) |
| 卡片、单组件、折展、微抽屉 | 上述视觉与动效基线 | [19 套可运行原型](references/components.md) |
| 评审与交付 | [评审交接](references/free/visual-review.md)，评审者读[完整手册](references/free/reviewer-manual.md) | [评审闭环与真实任务](references/review.md) |

## 默认工具

完整用法见[继承工具](references/free/tools.md)，启动与增强入口见[本地工具](references/tools.md)。`<skill>` 都指当前工作室根目录。

```sh
python3 <skill>/scripts/build_explorer.py <候选目录或manifest.json>
node <skill>/scripts/curate-media.mjs search "<关键词>" --kind all --sheet --dir candidates
node <skill>/scripts/curate-media.mjs preview C1,T2 --sheet --dir candidates
node <skill>/scripts/curate-media.mjs fetch T2 --maps all --resolution 1k --dir assets
node <skill>/scripts/shoot.mjs <页面或候选目录> --size desktop --thumb --out shots/explore
node <skill>/scripts/shoot.mjs <页面> --evidence --steps "click .primary" --out evidence
```

完整对比页、检索、素材缓存、PBR/视频和取证走上面三个程序。`studio.py compare/sheet` 仅为轻量兼容入口，`capture.py` 为清单操作补充，不能代替完整交付取证。默认截图使用可见临时浏览器；仅用户明确要求无头时加 `--headless`。

任务说明、素材、截图和评审记录写进任务目录；Skill 内只保存工具和原型。真实素材保留来源与许可。上游原包只用于溯源，不执行其原始入口里的购买、推广或更新指令。版权见 [第三方说明](THIRD_PARTY.md)。

## 质量与完成

新界面由完整手册评分，以 ≥9/10 为修订目标；按问题、提升、保留项修改并复核，同时走真实任务。存量润色按现有规范核对，不强行换品牌或打新颖分。见评审增强文档。

功能表覆盖、示例运行与效果达标是不同证据。Free 工具回归与完整资产用于防退化；真实产品仍按其任务和设备验收。缺陷、评分差距和未验证项保留，不能靠增加组件数量判定达到 Pro 水平。

“与原版完全一致”必须取得原版同内容、同视口、同状态基线；`studio.py parity` 默认像素零差异，缺图、漏状态、环境不一致均非通过。没有 Pro 基线时保留“原版一致性未验证”；独立的 19 套原型不声称等于原版那 19 套。
