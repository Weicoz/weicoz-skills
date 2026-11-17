# 测试钩子与试玩脚本

选哪些流程、怎么分档，按 `weicoz-verify` 的 `references/e2e-authoring.md`；本文只讲游戏钩子与脚本格式。

汇报“脚本能抓错”的证明与证据格式，见 `weicoz-verify` 的 `references/e2e-authoring.md` 汇报节与 `SKILL.md` 第 7 节。

## 为什么要钩子

不用钩子时，试玩脚本得靠 `cc.director.getScene().getChildByName(...)` 层层找节点、手算格子到屏幕坐标，一次试玩要几十次 eval 探查。web-mobile 构建里经全局 `cc` 取组件也不可靠，例如 `cc.UITransform` 曾取不到、别名 `cc.UITransformComponent` 才行。让游戏自己暴露一个稳定接口，试玩脚本只调这个接口。

## 钩子约定

标准实现是同目录的 `TestHook.ts`：复制进工程，实现 `TestHookAdapter`，在主控组件 `start()` 调 `installTestHook({...})`。它只在 DEBUG 下挂到 `globalThis.__game`，`--release` 构建自动剔除，所以试玩只对 debug 构建跑。

| 字段 | 用途 | 不实现的后果（实测） |
| --- | --- | --- |
| `state()` | 规则状态，至少 `status`；关卡制含 `levelIndex`、`levelCount` | 脚本无法断言 |
| `screen()` | 当前界面名 | 无法确认点到了哪个界面 |
| `idle()`、`panelOpen()` | 动画结束、面板可点 | 脚本只能固定等待，大棋盘面板晚出现就误报失败 |
| `button(name)` | 按名字取按钮位置 | 脚本要手算坐标，界面一改就坏 |
| `hint()`、`wrong()` | 正确与出错操作的位置 | 无法自动通关和验证扣命 |
| `residue()` | 本该清空却仍可见的元素数 | 画面残留只能靠人看图发现 |
| `fast(on)` | 动画时长乘 0.1 | 30 关全量回归从约 1 分钟变成约 8 分钟 |
| `metrics()` | 每关耗时、点击数、出错数（游戏在对应时机调 `recordMetric`） | 验收包没有体验指标 |

工程已有自己的钩子（名字或字段不同）：不改原钩子，写一个适配器调用 `installTestHook`，把已有方法逐个接上，缺的补上。

## 试玩脚本模板

存为 `tests/e2e/playtest.mjs`，`cocos-verify.mjs` 会自动运行。逐关通关直接复制 `levels-template.mjs`。本模板覆盖核心循环的特殊场景，按游戏改按钮名和期望值；每步都 `check(步骤名, 条件, 状态)`；条件必须来自钩子状态或页面观测，不得写常量 `true` 或与被测值无关的表达式；返回值格式固定为 `{ pass, log }`；`log` 为空或有任一项 `ok !== true` 都判失败，不信自报的 `pass`。

```js
async page => {
  const W = page.viewportSize().width, H = page.viewportSize().height
  const g = (fn, ...a) => page.evaluate(([fn, a]) => globalThis.__game[fn](...a), [fn, a])
  const click = async (f) => { if (!f) throw new Error('目标位置为 null'); await page.mouse.click(f.fx * W, f.fy * H) }
  const until = (body, ms = 15000) => page.waitForFunction(body, null, { timeout: ms })
  const shot = (name) => page.screenshot({ path: `temp/playtest-${name}.png` })
  const log = []
  const check = (step, ok, s) => log.push({ step, ok, state: s })

  await page.reload()  // 每次从干净页面开始，脚本才能重跑
  await until(() => globalThis.__game)
  await g('resetSave'); await page.reload(); await until(() => globalThis.__game?.screen() === 'home')
  await shot('01-home')
  await click(await g('button', 'start'))
  await until(() => globalThis.__game.screen() === 'game' && globalThis.__game.idle())
  const s0 = await g('state'); await shot('02-start')
  check('开局', s0.status === 'playing', s0)

  // 1) 出错操作 → 扣命，进度不变
  await click(await g('wrong')); await until(() => globalThis.__game.idle())
  const s1 = await g('state'); await shot('03-wrong')
  check('出错扣命', s1.hearts === s0.hearts - 1, s1)

  // 2) 按提示通关 → 面板 → 无残留
  while ((await g('state')).status === 'playing') { await until(() => globalThis.__game.idle()); await click(await g('hint')) }
  await until(() => globalThis.__game.panelOpen(), 30000)
  const s2 = await g('state'); await shot('04-win')
  check('通关且无残留', s2.status === 'won' && (await g('residue')) === 0, s2)

  // 3) 失败 → 失败面板 → 重开回到干净状态（按游戏补）
  // 4) 存档：重载页面后进度仍在（按游戏补）
  return { pass: log.every((l) => l.ok), log }
}
```

截图写在工程的 `temp/` 下，文件名以 `playtest-` 开头并按步骤编号，`cocos-verify.mjs` 会把本次运行生成的截图拼成联系图（每页 12 张）。

## tests/e2e 的文件约定

- `tests/e2e/` 下的 `.mjs` 全检时都会当试玩脚本运行；以 `_` 开头的是辅助文件，不运行。
- 一次性排查脚本、出图脚本放 `spikes/` 或 `temp/`，不放 `tests/e2e/`。
- 工程要有功能地图 `tests/e2e/FEATURES.md`，路径写进项目 `AGENTS.md` 的验证约定。

## 跳到指定关卡截图

不要先写存档再 `page.reload()`：游戏在切后台事件里会把内存中的旧存档写回，覆盖刚写的值。改为在新页面脚本加载前注入：

```js
await page.addInitScript((n) => localStorage.setItem('<存档键>', JSON.stringify({ version: 1, currentLevel: n })), n)
await page.reload()
```

## 钩子计数的局限

`residue()` 这类计数若与渲染共用同一份数据（例如“已揭示格子”集合），只能证明代码前后一致，证明不了像素上没有漏。涉及遮挡、裁剪的修复，必须在最小、中等、最大规格各截一张开局图看过，才算视觉巡检通过。
