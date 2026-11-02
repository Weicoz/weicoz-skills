# oil cards · 组件探索

`gallery.html` 展示 19 种模板、25 个实例。页首可以按视觉意象、产品场景、数据关系、行动引导筛选，切换「创作团队 / 开发工具」两套示例内容，以及四种外层效果。材质可选原始 / 金属 / 玻璃 / 实体卡，各自带入配套阴影；阴影也可单独覆盖为无 / 轻贴合 / 微悬浮。选择会保留。配色可选单色 / 双色 / 三色，并用取色器或 HEX 输入；有效选择会在当前浏览器保留。默认关闭外层倾斜和流光；组件自身的曲面、数字、数据流等动画仍由动效模式控制。

这是框架无关的 HTML / CSS / ES module 探索库。内容接口已从绘制逻辑分离；图形构图、裁切、线密度、光场、阻尼保留在组件内部。这里的参数说明只描述当前实现，不是 Skill 规范。

## 使用

把对应 `card.html` 片段放进页面，依次加载 `shared/shell.css`、该模板的 `card.css` 和 `shared/finish.css`，通过本地服务器或项目开发服务器加载模块：

```js
import {mount} from './assets/cards/file-mosaic/card.js';

const instance = mount(document.querySelector('.file-mosaic'), {
  shadow: 'auto', // 'auto'（默认，跟随材质）| 'none' | 'contact' | 'lifted'
  material: 'metal', // 'plain'（默认）| 'metal' | 'glass' | 'solid'
  effects: 'none', // 'none'（默认）| 'tilt' | 'glow' | 'tilt glow'
  theme: 'dark', // 'light' | 'dark'，省略时继承宿主
  motion: 'auto', // 'auto' | 'hover' | 'off'
  variant: 'default', // 对应模板的形态，通证为 'token' | 'card'
  content: {
    title: '项目里的文件，\n在同一处管理',
    collection: '项目资源',
    status: '所有文件已同步',
    files: [
      {type: 'code', name: 'client.ts'},
      {type: 'doc', name: 'README.md'},
      {type: 'image', name: 'cover.webp'}
    ]
  }
});

// 移除或重新挂载前
instance.destroy();
```

内容在 `mount` 时写入。更换内容时先销毁实例、恢复原始 HTML 片段，再重新挂载；不在已挂载的画布上重复 mount。画廊的场景切换示范了这条生命周期。`destroy()` 清理监听器、观察器、帧循环、GPU 资源及组件生成的图形，不承担恢复全部原始内容的责任。

## 三类公共配置

| 类别 | 接口 | 行为 |
| --- | --- | --- |
| 内容 | `options.content` | 所有字段可省略，省略时保留模板内容；字符串作为纯文本写入，`\n` 保留换行，空字符串清空文本。文本字段的 `null` 同省略 |
| 外观 | `--card-accent` | 宿主提供一个主色；可选 `--card-accent-2 / -3`，否则从主色推导 |
| 外观 | 字体、`--card-radius` | 字体继承宿主，圆角默认 8px；内部字号、间距与比例由模板管理 |
| 外观 | `options.theme` 或 `data-theme="light / dark"` | 可设在卡片或祖先容器；options 优先，局部 light 也可覆盖深色宿主 |
| 形态 | `options.variant` 或卡片自身 `data-variant` | 通证支持 `token / card`；其余模板传递为组件级样式钩子，保持原有构图 |
| 外层阴影 | `options.shadow` 或卡片自身 `data-shadow` | `auto / none / contact / lifted`；默认跟随材质，显式选择可覆盖；只控制外层投影，内部产品窗口的阴影不变 |
| 表面材质 | `options.material` 或卡片自身 `data-material` | `plain / metal / glass / solid`；金属细腻漫反射、玻璃透光与背景模糊、实体卡轻薄边缘；每种带入配套投影 |
| 外层交互 | `options.effects` 或卡片自身 `data-effects` | `none / tilt / glow / tilt glow`，options 优先；挂载后可以直接修改属性。不从祖先继承 |
| 内部动画 | `options.motion` 或 `data-motion="auto / hover / off"` | 卡片或祖先容器设置。auto 在可见时播放；hover 离开后，持续动画减速、指针跟随回正后停止，已开始的短演示播放至完成；off 展示完成状态或静帧；外层交互也服从 off |
| 内部动画 | `options.speed` | 默认 1，非负有限数；0 静态。有限演示播放一次，支持 `replay()` 的模板可手动重播 |
| 排版 | `data-title="top / bottom"` | 可选；省略使用自然位置。推广卡固定左侧文案，不应用这个切换 |

`theme / motion / variant` 等 options 在测量与首次绘制前应用，destroy 会恢复挂载前被 options 覆盖的属性。动效模式使用最近的 `data-motion`。若要继承宿主模式，移除片段上自带的 `data-motion="auto"`；卡片自身的属性会覆盖祖先。

外层倾斜固定在小角度范围内，流光使用局部柔和亮边。离开后回正、淡出；触屏、减少动态偏好、关闭动效、后台或屏外时停止。showcase 案例预览期间停用外层交互。组件不暴露透视距离、倾斜角度、跟随阻尼、光场半径等微调参数。

标题与舞台使用真实布局行，标题增长会推开下方主体；文字过长时卡片允许增高，不依赖脚本测量后再避让。上方 / 下方标题共用这条规则。文件集合栏、加载状态栏按内容高度排布，后面的预览跟随其位置；指标卡仍按实测文案高度分配数字和图表位置。画廊按容器宽度减少列数，避免把标题挤进狭窄栏位。

为保持艺术构图，建议纵向卡片 1–3 行、工具卡 1–2 行标题，说明 1–2 行。英文长单词可换行；文件名超出格子宽度显示省略号。内部放大的产品窗口仍按设计保留局部裁切。

## 内容字段

大多数卡片都有 `title`，带说明的卡片有 `description`。所有右上角展开按钮已移除。结构化字段如下；数组下标对应模板中固定的展示位置，不代表完整业务列表。

| 模板 | 额外字段 / 数据 |
| --- | --- |
| particle-ring | `prompt`, `reply`, `action`, `items[0..1].name/detail/value`；两件服装的 SVG 仍是模板插图，要换品类需要替换插图 |
| flow-object | `brand`, `identifier`, `edition`, `status`, `hashLabel`, `hash`, `specs[0..2].label/value`；默认实体铭牌，另有无芯片流光卡片 |
| dot-globe | `label`；mesh 另支持 `nodes: Array<{id, label?, position: [x,y,z]}>`、`links: Array<{from,to}>`；地球标签文案不改变地图上的连线坐标 |
| line-ribbons | `description`；同一曲面可切换线束、薄绸、点阵、网格 |
| ui-slice | `board`, `columns[0..1]`, `backlog[0..3]`, `listTitle`, `tasks[0..2].title/owner`, `progressLabel`；固定三项任务演示 |
| terminal | `path`, `shell`, `lines: Array<string \| {text, detail?, tone?}>`；tone 为 `highlight / result / address`，默认普通行；空数组显示 `emptyText`（默认「等待运行」） |
| metric | `value: number \| string`, `delta`, `latest`, `series: number[]`；数值自动加英文千位分隔，最多两位小数；字符串可以自带单位或其他格式 |
| beam-graph | `nodes[0..4]`, `hub`；节点数与路由结构固定 |
| keycaps | `modifier`, `modifierName`, `key`, `keyName`, `placeholder` |
| promo-band | `title`, `description`, `action`, `href`；整个卡片是链接 |
| vector-space | `query`, `result`, `mode`；四个相关点是视觉示意，结果文案不触发真实检索 |
| file-mosaic | `collection`, `status`, `files: Array<{name, type}>`, `emptyText`；type 为 `doc / image / video / code / color / audio`，其他值用文档图标。空数组显示空态 |
| stream-window | `path`, `eyebrow`, `heading`, `summary`, `visualLabel`, `listTitle`, `items[0..2]`, `pendingStatus`, `completeStatus`；固定三个内容块的就绪演示 |
| portrait-story | `brand`, `quote`, `author`, `role`, `image: string \| {src, alt}`；影像引言独立排版，长文案会撑高卡片 |
| capture-notes | `collection`, `tab`, `scope`, `listLabel`, `tagLabel`, `records: Array<{title, team?, tone?, tags?, detail?, waveform?}>`, `emptyText`；点选记录更新前景条，空数组禁用波形播放 |
| answer-lens | `eyebrow`, `dashboard`, `status`, `question`, `sources: Array<{label, answer, citation?, chart?}>`, `emptyText`；最多三个来源，选中后对应答案与图表前移；保留微倾角和悬浮徽章；可分别注入环形数值、柱状序列与折线序列 |
| responsive-preview | `description`, `labels[0..2]`；三个窗口共享原创 SVG 插图，通过按钮展开 / 收起不同尺寸，支持 `replay()` |
| deploy-preview | `project`, `versions[0..1].title/branch/url`, `statuses[0..2]`, `steps[0..2]`, `versionLabels[0..1]`, `resultLabel`, `resultNote`；两个版本的构建预览演示，支持 `replay()` |
| showcase | `brand`, `description`, `action`, `href`, `image: string \| {src, alt}`；有图片槽的四张 editorial 卡片可以替换封面，另外两张为程序图形 |

`metric.series` 接受有限的非负数，过滤无效项后按最大值归一化柱高；推荐 12–32 项，空数组不显示柱条。`delta` 与 `latest` 是独立展示文案，不自动推算，也不代表已接入真实业务数据。

链接支持相对地址、站内锚点、HTTP(S)、mailto、tel 和本地文件；拒绝脚本协议。图片支持相对地址、HTTP(S)、本地文件、blob 和图片 data URL。缺省图片保留模板。showcase 不提供 `href` 时，默认 CTA 展开视觉预览；提供 `href` 后作为普通导航链接使用。展示图片的 `alt` 由内容提供，背景装饰可为空。

原始片段中的 `data-text="items.0.name"` 等标记定义文本槽，普通 DOM 内容继续可直接编辑。`shared/content.js` 只填入文本、链接和图片，不生成任意 HTML。

## 讨论、引文与拓扑的数据槽

讨论数据沿用同一记录结构，医疗、审核、法律或工程内容不需要更改组件：

```js
mount(element, {
  theme: 'light', motion: 'auto',
  content: {
    title: '让每一次评审，\n都可以回溯。',
    collection: '工程评审', listLabel: '讨论主题', tagLabel: '领域',
    records: [{
      title: '接口边界与验收范围', detail: '评审记录 · 第二轮',
      tags: [{label: '工程', tone: 'teal'}, {label: '待核对', tone: 'amber'}],
      waveform: [.2, .7, .4, .9, .3] // 可选 0–1 幅度；省略时使用原有合成声波
    }]
  }
});
```

`team / tone` 是单标签的简写；`tags` 可用字符串或 `{label, tone}`。tone 为 `indigo / teal / amber / rose / slate`，省略时自动轮换。`detail` 作为选中记录的悬停说明。内容与声波仅做展示，不读取麦克风。

知识透镜的三个来源对应环形、柱状、折线图，点击引文会同时更新选中图表、答案和引用说明：

```js
mount(element, {content: {sources: [
  {label: '验收进度', answer: '已完成 73% 的验收项。', citation: '验收清单 · 第 2 版', chart: {value: 73, max: 100}},
  {label: '运行记录', answer: '峰值集中在后半段。', citation: '运行日志 · 本周', chart: {series: [12, 18, 26, 41]}},
  {label: '性能趋势', answer: '响应时间逐步回落。', citation: '性能报告 · 第 3 页', chart: {series: [80, 62, 54, 31]}}
]}});
```

`chart` 省略时保留模板图形；序列过滤非有限数，最多 32 项，空数组清空对应图形；环形数值按 max 归一化并限制到 0–100%。引用和答案只作为纯文本，不从文案推算数值。

```js
mount(element, {mode: 'mesh', content: {
  title: '让系统之间，\n保持清楚的连接。', label: '推理节点 · 在线',
  nodes: [
    {id: 'gateway', label: '入口', position: [-.7, .4, .1]},
    {id: 'agent', label: '推理节点', position: [.1, 0, .3]},
    {id: 'store', label: '存储', position: [.7, -.4, -.2]}
  ],
  links: [{from: 'gateway', to: 'agent'}, {from: 'agent', to: 'store'}]
}});
```

拓扑 position 是空间坐标，建议每轴约 -1 到 1，限制到 ±1.5；最多展示 64 个节点、160 条有效链路。省略 links 时连接相邻节点，空数组表示无链路；空 nodes 保留环境星点。上述展示数量约束服务于卡片快照，不代表完整业务数据模型。

## 艺术变体

- 粒子环当前保留环形结构。showcase 的 `glow-shapes` 程序背景另支持 `options.shape / data-shape` 为 `circle / heart / star / petal`（默认 heart）；这不作用于四张 editorial 位图封面。
- 实体通证：`options.variant / data-variant` 为 `token`（默认）或 `card`。token 有激光刻蚀短码、规格与 LED 呼吸脉冲，card 保留无芯片流光与接触阴影；两者使用同一 WebGL 材质。直接修改 data-variant 即可切换。
- 空间拓扑：`options.mode / data-mode` 为 `globe`（默认）或 `mesh`，直接修改属性可切换。mesh 显示有空间纵深的星座点场、链路光点和节点脉冲；共享主题、配色与动效控制。
- 地球连线：`options.arcs / data-arcs` 选择 1–3，默认 2。
- 丝带：实例 `setRenderer('svg' | 'webgl' | 'dots' | 'grid')`；WebGL 不可用时返回 SVG。四个变体共享曲面结构，分别呈现线束、薄绸、点阵和网格。
- showcase：HTML 的 `data-background` 选择既有视觉方案，`editorial` 为原色位图，保留其自身配色。

这里的变体具有不同视觉用途，不需要在每个卡片上全部开启。示例中的裁切、出血、居中与留白按各自构图保留。

## 构建与验证入口

```sh
python3 scripts/build_cards.py
```

Python 3.10+，仅标准库。构建把片段、CSS、命名 ES 模块、地图掩码与本地封面内联到 `gallery.html`，可直接打开；构建不联网。复制模块到项目时仍需保留其相对导入关系。小打包器只服务当前命名 import/export，不是通用 JS 打包器。

```text
assets/cards/
  gallery.html                         单文件构建产物
  gallery.template.html
  gallery.css / gallery.js             画廊布局、控制和实例生命周期
  gallery-content.js                   两套示例内容，组件不依赖此文件
  gallery-palette.js / gallery-catalog.js 配色编辑和分类筛选，只服务画廊
  shared/content.js                    纯文本、链接、图片槽
  shared/shell.css / finish.css / runtime.js 外壳、材质、交互、时钟与绘制辅助
  shared/ne_110m_land.zip / land-mask.js 地图构建输入和输出
  <模板名>/card.html / card.css / card.js
```

配色查询 `colors=256b70,7dc0af,d4bb83` 接受 1–3 个 3/6 位 HEX（可省略 #），由数量确定单/双/三色；显式 URL 优先于保存的选择，不会仅因打开 URL 而覆盖保存值。`category=visual|product|data|action` 可直接进入对应分类，省略时展示全部。旧的 state/preset 色板 URL 为既有截图入口保留，界面已移除预设按钮。

共享外壳分别提供图形色和内部强调文字色。文字色仅限制明度、保留色相；图形使用原始色值，showcase 位图封面不染色；portrait-story 用所选主色作为单色摄影覆盖层。

画廊查询参数：`content=studio|developer`、`shadow=auto|none|contact|lifted`、`material=plain|metal|glass|solid`、`effects=none|tilt|glow|tilt%20glow`、`title=default|top|bottom`、`motion=auto|hover|off`、`speed=0`、`state=sage|mono|clay|dark`、`ribbons=svg|webgl|dots|grid`、`variant=token|card`（通证）、`mode=globe|mesh`（空间拓扑）。`focus=<模板名>` 、`focus=explorations` 或 `focus=peer-cards` 用于局部检查。

持续动画跟随屏幕刷新率，时间增量参与插值；有限演示完成后停止。屏外、后台、减少动态偏好都停止播放。画布尺寸按未变换的布局尺寸计算，外层倾斜不会反复改变绘制缓冲区。

使用现代浏览器的原生 CSS 嵌套、相对 OKLCH、color-mix、overflow:clip、dialog、WebGL 1。地图来自 Natural Earth 110m land（数据来源和归档保存在 shared 中）；四张 editorial 封面为生成素材、搭配虚构品牌。场景文案、数值、任务与运行输出均为演示内容。

## 新增同类网站探索

页首「从视觉形态，到产品细节」包含五个中立模板：影像叙事、讨论记录、知识透镜、响应式展开与构建流水线。影像叙事归入「视觉意象」，其余归入「产品场景」。脚注按形态命名，组件不依赖商业平台名称或默认外链。

`portrait-story` 的默认人物为 AI 生成的虚构人物，文案是编辑式示例；图片提示词与使用说明保存在 `portrait-story/images/README.md`。其他四张新卡使用 DOM / SVG。讨论条仅演示波形，不访问麦克风；引用答案不调用 AI；尺寸窗口不运行图片优化；构建过程不创建真实部署，预览地址只是文本。

这五张卡复用公共配色、内容与动效接口，不再添加强度、散布角度、波形频率等艺术微调参数。用户的关闭动效、速度 0 和系统减少动态偏好会同时停止脚本动画与内部 CSS 过渡。

## 材质与内容的灵活度

阴影和材质作用于外层卡片；showcase 作用于封面窗口。摄影和封面只调整边缘及接触阴影，不叠加金属亮带或颗粒；实体卡保留轻薄边缘，选择「无阴影」仍有边缘厚度。材质静态渲染，不增加帧循环。玻璃支持真实 backdrop-filter，在不支持的环境中退回更不透明的表面；摄影与不透明画布依然遮住其后方背景，表面呈覆膜效果。画廊选择玻璃时增加淡色宿主背景，便于看清透光。

`options` 优先于卡片自身属性；这两组配置不从祖先继承，挂载后可直接修改 `data-shadow` / `data-material`。画廊选择保存在 `oil.cards.finish.v2`。切换材质会将阴影控制设为「跟随材质」，之后可单独覆盖；URL 显式材质也默认带入配套阴影，显式 shadow 参数优先。访问预览链接不会自动写入保存值。

内容通过 `mount(element, {content})` 传入，大部分业务标题、说明、标签、记录、引用、文件和数值可替换，完整字段见上表。挂载后更换内容采用前述销毁、恢复片段、重新挂载流程；当前没有通用的原地 `update()`，也没有画廊内点字编辑器。HTML 文字槽可直接编辑，数据由 JS 生成的列表和数值需修改对应 content。

图片替换仅适用于现有图片槽：portrait-story 和 showcase 的 editorial / image 类型；程序绘制的曲面与粒子保留艺术结构；知识透镜图表及空间拓扑节点可用上述数据接口替换。构图比例、裁切、图形结构与动画路径保留为模板的设计部分。示意图表和检索文案并不等于已接入真实服务。
