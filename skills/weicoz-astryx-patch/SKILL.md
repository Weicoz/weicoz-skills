---
name: weicoz-astryx-patch
version: 0.1.0
description: oil-ui-pro 的 Astryx 补丁：项目已安装 @astryxdesign/core（Meta 开源 React 19 设计系统）时，做界面设计、改版、评审或后台页面，先加载本 skill。补 oil-ui-pro 缺的环节：用 astryx CLI 实时查组件与模板、主题只改 CSS 变量、DESIGN.md 记录 token 与主题名、新建 React 后台时把 Astryx 列为可选组件库（须用户确认）。项目没装 Astryx 且用户没提时不用。Add-on for oil-ui-pro when the project uses Astryx.
---

# oil-ui-pro 的 Astryx 补丁

主流程以 `oil-ui-pro` 为准，本 skill 只追加下面几步，不复制它的流程。调用被拒或找不到时，读对应 `SKILL.md` 执行。

## 适用判断

- 项目 `package.json` 含 `@astryxdesign/core`：走第 1–3 节。
- 项目没装、要新建 React 后台或工作区：走第 4 节。
- 其他情况不启用。Astryx 只支持 React 19+；Vue、Svelte、静态 HTML、小程序不适用。

## 1. 沿用现行实现，不另造组件

对应 oil-ui-pro `existing-project.md` 的“核对已安装组件库”。

- 先用项目自己的 CLI：`pnpm exec astryx …` 或 `npx @astryxdesign/cli …`。未装 CLI 时不得运行不带 scope 的 `npx astryx`，它会解析到无关的 npm 包。
- 查组件与模板，不凭记忆写 API（Beta，版本几乎每天变）：
  - `astryx search <词>`：跨组件、hook、文档、模板检索
  - `astryx component <名>`：组件 API
  - `astryx template --list` / `astryx template <名>`：页面骨架
  - `astryx docs`：设计系统指南（tokens、theme、layout）
- 先看 `package.json` 里 Astryx 的实际版本，以该版本 CLI 的输出为准。
- 缺能力时，先组合现有组件；不够再 `swizzle` 弹出源码；仍不够才新写。不为一次页面另装同类库。
- 样式覆盖用 `className`（沿用项目已有的 Tailwind、CSS Modules 或纯 CSS）。
- 样式表导入顺序固定：`reset.css`、`astryx.css`、主题 `theme.css`，并包主题 Provider。顺序错会乱层级。

## 2. 主题只改变量

- 品牌色、圆角、密度、字体：覆盖主题的 CSS 变量，不改组件源码，不包一层壳组件。
- 内置主题：neutral、butter、chocolate、matcha、stone、gothic、y2k。先选最近的一套再微调，不从零写。
- 默认 neutral 偏中性企业后台。用户要辨识度时，必须改主题变量，并在交付说明写明改了哪些。
- 主题构建：`astryx theme build`。

## 3. DESIGN.md 记录

按 oil-ui-pro `design-spec.md` 的写法，追加以下条目，各标“用户确认”或“Agent 推断”：

- Astryx 版本（写 `package.json` 里的实际版本）
- 使用的主题包名，以及覆盖的变量清单
- 已 swizzle 的组件路径
- 样板页面所用的 template 名

## 4. 新建 React 后台时

仅在用户没指定组件库、技术栈是 React 19+、领域是工作区（后台、控制台、表格与详情页）时：

- 在方案确认点把 Astryx 列为一个可选项，附一句理由：现成的表格页、详情页、表单向导模板。
- 用户确认前不得安装依赖。
- 用户拒绝或栈不符时，回到 oil-ui-pro 原流程。

## 限制与诚实声明

- Astryx 为 Beta（0.7.x）。`@astryxdesign/charts`、`@astryxdesign/vega` 只有 `@canary` 标签；`@astryxdesign/lab` 不发布到 npm。需要图表时先向用户确认可接受 canary。
- 本 skill 依据 README、AGENTS.md 和 CLI 文档写成，作者尚未在实际项目里装过、跑过。首次使用时核对 `astryx --help` 与 `astryx manifest --json`，与本文不符以 CLI 输出为准，并回报修正。
- 不照搬 Astryx 仓库自带的 `AGENTS.md`、specs 流程，那是给贡献者用的。
