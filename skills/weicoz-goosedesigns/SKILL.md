---
name: weicoz-goosedesigns
version: 1.0.0
description: Use when creating websites, web pages, web apps, dashboards, portfolios, posters, decks, interfaces, or other visual artifacts where design variety matters. Search the local GooseDesigns visual-reference catalog before deciding layout, color, motion, typography, or imagery.
---

# Weicoz GooseDesigns

本地优先设计灵感 skill。无远端服务、无 API key、无网络依赖。

## 本地检索

从 skill 根目录执行：

```bash
python3 scripts/goose_search.py "editorial changelog"
```

查询使用英文关键词；可组合页面类型、信息密度、层级、交互和视觉材料。脚本从 `references/goosedesigns/CATALOG.md` 与 `DESIGN.md` 返回匹配案例和设计约束。

## 工作流

1. 先读用户需求，不先决定颜色、字体、布局或动效。
2. 用本地目录广搜 2–4 组关键词。
3. 选择少量强案例，提取布局、配色、字体、材质、动效和微交互。
4. 将约束综合到用户场景；不要复制案例文案或假装有未检索到的参考。
5. 若本地目录无匹配，明确说明，并基于用户约束设计；不得声称完成了外部检索。

## 反模板规则

- 禁止默认蓝紫渐变、玻璃拟态、彩虹装饰。
- 禁止无意义 hover 缩放、滚动淡入、跑马灯和 loading 旋转。
- 避免卡片套卡片；优先间距、层级和分隔线。
- 不用 emoji 或彩色圆角图标容器替代真实图标/图形。
- 不用模板化文案和三等分功能卡公式。
- 中文页面必须使用显式中文字体栈，例如 `-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`。
- 中文不用伪斜体；用字重、颜色、背景或字号表达强调。
- 外部图片须验证 URL；不合适时用排版、留白或代码绘制替代。

## GooseDesigns 约束

优先参考其设计规范：克制装饰、真实模块字号、WCAG AA 对比度、只为状态/空间连续性使用动效、真实文案、避免通用 AI 渐变。可用风格族包括 terminal-dark、editorial、hud、blueprint，以及 brutalist、swiss、warm-minimal、neon-noir 等目录样本。

## 输出纪律

只输出综合后的设计决策，不粘贴原始目录内容，不暴露内部检索分数或实现细节。参考不足时标注待确认项。
