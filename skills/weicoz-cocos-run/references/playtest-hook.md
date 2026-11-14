# 测试钩子与试玩脚本

## 为什么要钩子

不用钩子时，试玩脚本得靠 `cc.director.getScene().getChildByName(...)` 层层找节点、手算格子到屏幕坐标，一次试玩要几十次 eval 探查。web-mobile 构建里类名还可能被改写，例如 `getComponent(cc.UITransform)` 拿不到组件、`cc.UITransformComponent` 才行。让游戏自己暴露一个稳定接口，试玩脚本只调这个接口。

## 钩子约定

只在调试构建中挂到 `globalThis.__game`。挂载点放在主控组件的 `start()` 里：

```ts
import { DEBUG } from 'cc/env'

start() {
  if (DEBUG) (globalThis as any).__game = {
    state: () => ({ phase: this.phase, level: this.levelIndex, lives: this.lives, timeLeft: this.timeLeft, modal: this.modalName }),
    // 把逻辑坐标转成屏幕坐标（CSS 像素，左上原点），供真实点击使用
    screenPoint: (x: number, y: number) => this.view.toScreen(x, y),
    // 直接驱动规则层，跳过输入；用于构造场景
    act: (name: string, ...args: unknown[]) => (this as any)[name](...args),
    solution: () => this.level.solutionOrder,
    setTime: (sec: number) => { this.timeLeft = sec },
    idle: () => !this.locked && !this.animating,
  }
}
```

字段按玩法增减，但保持三类：**读状态**（`state`、`idle`）、**真实输入坐标**（`screenPoint`）、**作弊构造**（`setTime`、`solution`、`act`）。验收“点击有效”必须用真实点击；“超时失败”这类可以用作弊构造。

## 试玩脚本模板

`playwright-cli run-code --filename=tests/playtest.mjs`，文件内容是一个 `async page => {}`：

```js
async page => {
  const state = () => page.evaluate(() => __game.state())
  const waitIdle = () => page.waitForFunction(() => __game.idle(), null, { timeout: 4000 })
  const tap = async (x, y) => {
    const p = await page.evaluate(([x, y]) => __game.screenPoint(x, y), [x, y])
    await page.mouse.click(p.x, p.y)
  }
  const shot = (name) => page.screenshot({ path: `temp/playtest-${name}.png` })
  const log = []

  log.push({ step: 'launch', state: await state() }); await shot('launch')
  // 1) 合法操作 → 进度变化
  // 2) 非法操作 → 扣命/反馈，状态不前进
  // 3) 失败 → 失败面板 → 重开回到干净状态
  // 4) 按 solution() 通关 → 胜利面板 → 下一关
  return log
}
```

截图写在工程的 `temp/` 下（Cocos 工程默认忽略该目录），汇报时给出路径。
