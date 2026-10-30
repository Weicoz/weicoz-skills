# 出片规范：把风格提示词变成能放的片子

本文件是硬约束。写代码前先读这里，产出物必须满足下面 11 条。

## 1. 输出契约（11 条）

1. **单文件**：一个 `index.html` 自包含。CSS、JS、素材全部内联；不引外部图片、字体文件、音频。
   - 例外：3D 风格允许用 CDN 引 `three.js`（见 §4 模式 B）。此时须在交付说明里写明「需联网」。
2. **画布固定 1920×1080**（竖屏 1080×1920），CSS 等比缩放并居中，多出来的是黑边。
3. **画面是时间的纯函数** `draw(t)`：同一个 `t` 画出来必须一模一样。
   - 禁止 `Math.random`，改用带种子生成器（§2 的 `mulberry32`），种子在启动时生成一次。
   - 禁止在 `draw` 里存上一帧状态。所有随机量在启动时算好，存成数组。
4. **`?t=` 定格**：网址带 `?t=5.7` 时只画第 5.7 秒那一帧并停住。这是核验与出片的入口，缺了它整条流水线就断——`shot.sh --probe` 的多点探测、以及 `render_mp4.sh` 出片前的探测都会拦住没实现它的页面。
5. **播放**：默认 `requestAnimationFrame` 循环，`t` 对总时长取余；空格暂停/继续。
6. **不省略代码**：交付完整可运行文件。不写「此处略」「其余同上」，不用省略号。
7. **中文字体只用系统栈**：`"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif`；衬线用 `"Noto Serif SC","Songti SC","SimSun",serif`。不引字体文件。
8. **文字可读**：1080p 下字号 ≥ 20px；关键文字停留 ≥ `字数÷4.5 + 1.5` 秒（中文），英文按 `字符数÷15 + 1.5`；有配音时 ≥ `max(1.8s, 语音时长+0.6s)`。
9. **性能**：单帧 16ms 内画完。Canvas 2D 粒子 ≤ 5000；每帧不要新建渐变/大对象/离屏画布，启动时建好复用。
10. **确定性可验**：同一 `t` 连截两次，PNG 哈希必须相同（§7）；两个不同 `t` 的画面必须不同（否则就是静态页）。前者用 `shot.sh --verify`，后者用 `shot.sh --probe`。
11. **帧间必须真的在变**：出片 fps ≥ 20。用增量式实现时重放步长 ≤ 0.05 秒，末尾补一次真实 `t`（§3），否则会出现重复帧。

## 2. 骨架 A：Canvas 2D（默认）

零依赖，直接可跑。把 `draw(t)` 换成你要的风格实现。

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>标题</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
  body { display: flex; align-items: center; justify-content: center; }
  canvas { width: 100vw; height: 56.25vw; max-height: 100vh; max-width: 177.78vh; display: block; }
</style>
</head>
<body>
<canvas id="c" width="1920" height="1080"></canvas>
<script>
(() => {
  const W = 1920, H = 1080, TOTAL = 8;                    // TOTAL = 总时长（秒）
  const cv = document.getElementById('c');
  const ctx = cv.getContext('2d');
  const SANS = '"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif';

  // 带种子随机：同一种子每次一样（契约第 3 条）
  const mulberry32 = a => () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

  // 启动时一次性生成所有随机量
  const rnd = mulberry32(7);
  const dots = Array.from({ length: 400 }, () => ({
    x: rnd() * W, y: rnd() * H, r: 1 + rnd() * 3, ph: rnd() * Math.PI * 2
  }));
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, '#0b0e15'); bg.addColorStop(1, '#050608');   // 渐变也建一次

  function draw(t) {
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
    const k = smooth(0, 1.2, t);                                 // 入场进度
    for (const d of dots) {
      const a = 0.25 + 0.5 * Math.sin(t * 1.4 + d.ph) ** 2;
      ctx.fillStyle = `rgba(214,224,242,${a * k})`;
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2); ctx.fill();
    }
  }

  window.__draw = draw;                                          // 便于调试与脚本调用
  const q = new URLSearchParams(location.search).get('t');
  if (q !== null && q !== '' && !isNaN(parseFloat(q))) { draw(parseFloat(q)); return; }   // 契约第 4 条

  let start = performance.now(), paused = false, pausedAt = 0;
  addEventListener('keydown', e => {
    if (e.code !== 'Space') return;
    e.preventDefault();
    if (paused) { start = performance.now() - pausedAt * 1000; paused = false; }
    else { pausedAt = (performance.now() - start) / 1000; paused = true; }
  });
  const loop = now => { if (!paused) draw((now - start) / 1000 % TOTAL); requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
})();
</script>
</body>
</html>
```

## 3. 复用库里的参考实现

库里 341 条中，**25 条**在正文写了可直接粘贴的 `S.XX = (c,w,h,t,s) => {…}`（A–G 的 25 条，B3 除外），另有 3 条只有片段（B3 粒子聚形、Z5 剪纸、L20 油画厚涂），L10 里是 JSON 配置不是代码。
先用检索确认：带 `[代码]` 的可粘贴，目录里标 `△` 的是片段。

### 依赖按类别不同，别一律找 `_公共函数.js`

| 类别 | 依赖 | 做法 |
| --- | --- | --- |
| A–G 代码样片 | 同目录 `_公共函数.js`（`rng`/`clamp`/`lerp`/`ss`/`eOut`/`eBack`/`nz`/`hex`/`mixHex`/`vgrad`/`glowDot`/`offscreen`/`paperTex`/`SANS`/`MONO`/`TAU`） | 全文粘进来即可 |
| Z / L | 没有 `_公共函数.js` | 只取思路与参数；要复用片段就自己补齐依赖 |
| L20 油画厚涂 | 正文示例 `import` 自 `./engine/impasto.js`，**库内没有该文件** | 只当伪代码读，自己实现 |

### 还缺外部常量

参考实现还会引用库外符号：`PARENT`（要展示的文案数组）、`SERIF`（衬线字体栈）、`KNIFE`、`DAB`。缺哪个补哪个，`PARENT` 填你的实际文案。
（`SANS`/`MONO` 已在 `_公共函数.js` 里定义，不用你补。）

### 分两类接进 `draw(t)`

**纯函数式（25 条里 22 条）**：位置只由 `t` 算出，直接调用即可，天然支持 `?t=`。

```js
// 纯函数式：一行就够
function draw(t) { S.B5(ctx, W, H, t, {}); }
```

**增量式（A1 字雨 / B4 星空连线 / D1 雨窗，共 3 条）**：内部按 `dt` 累加状态，跳帧会画错，必须重放。用下面的确定性外壳：

```js
const S = {};                       // 风格函数挂载点
// …粘贴 _公共函数.js 与 S.A1 = (c,w,h,t,s)=>{…}…
const PARENT = ['被说过的话', '又说一遍', '我都懂'];   // 按需填写
const SERIF = '"Noto Serif SC","Songti SC","SimSun",serif';

const STEP = 1 / 30;                // 必须 ≤ 0.05：这类实现内部有 clamp(dt, 0, .05)
let cache = { t: -1, s: null };

function draw(t) {
  if (cache.s && t > cache.t && t - cache.t <= 0.2) {   // 顺序播放（任意 fps）：接着算
    S.A1(ctx, W, H, t, cache.s); cache.t = t; return;
  }
  const s = {};                                          // 随机访问：从 0 重放到 t
  for (let k = 0; k < t - 1e-9; k += STEP) S.A1(ctx, W, H, k, s);
  S.A1(ctx, W, H, t, s);                                 // 末尾用真实 t 补一次，避免取整丢步
  cache = { t, s };
}
```

- 重放成本是 `t × 30` 次调用，10 秒内可接受。**不要降到 1/15**：`dt` 会被内部 `clamp(…, 0, .05)` 截断，动画会整体变慢。
- 超过 15 秒的长片，把实现改写成纯函数，或把内部 `clamp` 上限提高到 ≥ `1/fps`。
- 出片 fps 建议 ≥ 20；低于 20 时 `dt` 会逼近 0.05 的截断上限，动作会发涩。

跑通的完整实例：`references/examples/自测样片_A1字雨/index.html`（6 秒版，含公共函数、A1 原文、外部常量与外壳）。改 `PARENT` 就是换文案，改 `S.A1` 就是换风格。

## 4. 骨架 B：three.js（3D 风格用）

O 系列等 3D 风格需要 WebGL。用 importmap 引固定版本，别用 latest：

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>标题</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
  body { display: flex; align-items: center; justify-content: center; }
  canvas { width: 100vw; height: 56.25vw; max-height: 100vh; max-width: 177.78vh; display: block; }
</style>
<script type="importmap">
{ "imports": { "three": "https://unpkg.com/three@0.169.0/build/three.module.js" } }
</script>
</head>
<body>
<script type="module">
import * as THREE from 'three';
const W = 1920, H = 1080, TOTAL = 8;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(W, H, false);   // false：不写内联宽高，交给 CSS 等比缩放
renderer.setPixelRatio(1);
document.body.appendChild(renderer.domElement);
// …场景、灯光、相机…

function draw(t) { /* 相机/粒子位置只由 t 决定 */ renderer.render(scene, camera); }

window.__draw = draw;
const q = new URLSearchParams(location.search).get('t');
if (q !== null && q !== '' && !isNaN(parseFloat(q))) { draw(parseFloat(q)); }
else {
  let start = performance.now(), paused = false, pausedAt = 0;
  addEventListener('keydown', e => {
    if (e.code !== 'Space') return;
    e.preventDefault();
    if (paused) { start = performance.now() - pausedAt * 1000; paused = false; }
    else { pausedAt = (performance.now() - start) / 1000; paused = true; }
  });
  const loop = n => { if (!paused) draw((n - start) / 1000 % TOTAL); requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
}
</script>
</body>
</html>
```

- `setSize(W, H, false)` 的第三个参数必须给 `false`，否则 three.js 写死内联 `1920×1080`，非 16:9 窗口会被裁。
- 材质必须 `renderer.setPixelRatio(1)`，否则截出来尺寸不对。
- 首次加载要等模块下载；`scripts/shot.sh` 已给 4 秒虚拟时间预算。
- 竖屏（1080×1920）要把 CSS 换掉，不是把画布压扁：
  ```css
  canvas { width: 56.25vh; height: 100vh; max-width: 100vw; max-height: 177.78vw; display: block; }
  ```
- 没有网络时不得交付模式 B：退回模式 A 用 2D 近似，并在交付说明里写清。
- 已验证：macOS + Chrome headless（`--enable-unsafe-swiftshader`）能截出 WebGL 画面。

## 5. 时间轴怎么排

先写场景表再写代码，别一边写代码一边想节奏。

| 段 | 时间 | 画面 | 动作 | 声音 |
| --- | --- | --- | --- | --- |
| 开场 | 0–1.2s | 全屏标题 | 字从 0 到 1 砸入，ease-out | 低频撞击 |
| 主体 | 1.2–5.5s | 主视觉 | 每 0.8s 一个变化点 | 节拍 |
| 收尾 | 5.5–8s | 结论留在画面 | 减速、静止 1s 以上 | 收尾音 |

- **节奏网格**：默认 120 BPM（一拍 0.5s）。所有切点、入画、闪白落在拍或半拍上。
- **镜头**：每段只做一件事（推、拉、摇、切之一）。一镜到底就用连续参数化运动，别硬拼。
- **硬切优于淡入淡出**，除非风格提示词明确要溶解。
- **收尾要停住**：最后一帧至少停 0.8s，否则成片像被切断。

## 6. 多风格拼接

- 一条片子最多 2–3 种风格；超过就变成风格集锦，观众抓不到主线。
- 用**同一个衔接物**过渡：一个颜色、一个图形、一个动作、一个音效。别用花哨转场。
- 每种风格保留自己的配色和笔触，只统一**画幅、字号下限、节奏网格**。
- 转场 0.3–0.6s：形状擦除、颜色覆盖、缩放穿过，任选其一。

## 7. 核验（必做，别跳）

路径换成你自己的产物。下面用库自带样片演示（`demo/index.html` 是你将要写的文件）：

```bash
DEMO=references/examples/自测样片_A1字雨/index.html

# 0) 先确认 ?t= 真生效：采样 0.2/1.0/3.0/6.0 四个时刻，至少要出现两种画面
./scripts/shot.sh --probe "$DEMO"
# 开场是刻意静止的标题卡时，自己指定两个时间点：
# ./scripts/shot.sh --probe "$DEMO" 2.5 3.5

# 1) 抽 4 帧看画面（时间点选在关键动作上）
./scripts/shot.sh "$DEMO" 0.4 /tmp/a.png
./scripts/shot.sh "$DEMO" 2.0 /tmp/b.png
./scripts/shot.sh "$DEMO" 4.5 /tmp/c.png
./scripts/shot.sh "$DEMO" 7.0 /tmp/d.png

# 2) 确定性：同一 t 截两次比哈希，脚本直接给 PASS / FAIL
./scripts/shot.sh --verify "$DEMO" 3.3
```

然后逐条对照：风格提示词里的配色/笔触/镜头/避免项是否在画面上成立；中文有没有超框、有没有低于 20px；关键文字停留够不够。

## 8. 出片

```bash
DEMO=references/examples/自测样片_A1字雨/index.html

# 1920×1080 30fps，8 秒
./scripts/render_mp4.sh "$DEMO" out.mp4 8 30 1920 1080 6

# 加背景音乐（音频先按素材许可确认可用）
./scripts/render_mp4.sh "$DEMO" out.mp4 8 30 1920 1080 6 --audio bgm.mp3

# 竖屏
./scripts/render_mp4.sh "$DEMO" out.mp4 8 30 1080 1920 6
```

脚本自带四道防线：出片前 probe（画面不随 t 变化就拒绝）、帧数不足、全片重复帧统计（重复率过高给警告）、音频短于视频（补静音而不是截断）。

成片规格（沿用库内 V 系列的写法）：

- 视频：H.264 MP4，`yuv420p`，帧率 30，时长为精确值（如 8.000s = 240 帧）。脚本强制 `-t <时长>`，音频长短都不影响画面长度。
- 音频：有配音或音乐时 AAC **48kHz 立体声**（脚本强制 `-ar 48000 -ac 2`）。
- 响度：**−14 LUFS** 积分响度，真峰 **≤ −1 dBTP**。带 `--audio` 时 `render_mp4.sh` 会先测一遍再按测量值做第二遍（两遍 `loudnorm` + `apad`），实测安静素材与满幅素材都落在 −14.0 LUFS；单遍 loudnorm 只能到 ±2 LU，不要只跑一遍。
- 文件名不带空格，交付时一并给 `index.html`（可改可重渲）。

## 9. 常见失败与处理

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| 截出来全黑 | 没实现 `?t=`；或首帧在 `load` 后才画 | 加 `?t=` 分支；`draw` 里不要依赖异步资源 |
| 同一 t 两次哈希不同 | 用了 `Math.random`，或在 `draw` 里累加状态 | 改种子随机；状态提到启动期 |
| 出片后动作像幻灯片、有重复帧 | 帧间 `t` 精度不足，或重放外壳末帧没补 `t` | 用 `shot.sh`/`render_mp4.sh`（已用 6 位小数）；重放外壳末尾补一次 `S.XX(...,t,s)` |
| `--probe` 报 FAIL | 页面没实现 `?t=`，或动画在比较的时间点还没开始 | 加 `?t=` 分支；或把探测时间点挪到动画开始后 |
| WebGL 全黑 | Chrome 带 `--disable-gpu` 跑 | 去掉该 flag，用 `--enable-unsafe-swiftshader`（`shot.sh` 已处理） |
| 帧率掉到 10fps | 每帧新建渐变/离屏画布/数组 | 启动时建好复用；粒子降到 5000 内 |
| 中文变方块或超框 | 字体栈缺中文字体；字号按英文算 | 用 §1 第 7 条的栈；按 CJK 宽度 `字数×字号` 估框 |
| 粒子/线条出现 NaN 黑块 | 除零或距离为 0 | `Math.max(d, 1e-3)`；限制参数范围 |
| 出片时帧数不够 | 并行太高，Chrome 抢资源崩了 | 降 `parallel` 重跑；脚本默认已校验帧数 |
| 3D 出片太慢 | 每帧重启浏览器 + 软件渲染 | 降分辨率核验、只渲必要时长；或改 2D 近似 |

## 10. 交付前自查

- [ ] 单文件 `index.html`，双击能放；无外部依赖（3D 模式除外且已声明）
- [ ] `?t=` 定格正确（`shot.sh --probe` PASS）；空格暂停可用
- [ ] 关键帧截图与风格提示词逐条对得上
- [ ] 确定性哈希一致（`shot.sh --verify` PASS）
- [ ] 文字无超框、无乱码、字号达标
- [ ] mp4 时长、分辨率、帧率与要求一致；有音轨时为 48kHz 立体声
- [ ] 有声音的成片已做响度归一
