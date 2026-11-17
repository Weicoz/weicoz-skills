async page => {
  // 通用逐关通关脚本：只依赖 TestHook.ts 的标准字段（globalThis.__game），复制到 tests/e2e/levels.mjs 即可用。
  // 改这两个名字适配项目：START 是首页“开始”按钮名，NEXT 是过关面板“下一关”按钮名。
  // FAST 读环境变量 PLAYTEST_FAST（'1' 开快速模式）：cocos-verify --quick 会设，全检不设。
  const START = 'start', NEXT = 'next', MAX_LEVELS = 999
  const FAST = typeof process !== 'undefined' && process.env?.PLAYTEST_FAST === '1'
  const W = page.viewportSize().width, H = page.viewportSize().height
  const g = (fn, ...a) => page.evaluate(([fn, a]) => globalThis.__game[fn](...a), [fn, a])
  const click = async (f) => { if (!f) throw new Error('目标位置为 null'); await page.mouse.click(f.fx * W, f.fy * H) }
  const until = (fnBody, ms = 15000) => page.waitForFunction(fnBody, null, { timeout: ms })

  await page.reload()
  await until(() => globalThis.__game)
  await g('resetSave')
  await page.reload()
  await until(() => globalThis.__game?.screen() === 'home')
  if (FAST) await g('fast', true)
  await click(await g('button', START))
  await until(() => globalThis.__game.screen() === 'game')

  const log = []
  let levelCount
  try {
    for (let n = 1; n <= MAX_LEVELS; n++) {
      await until(() => globalThis.__game.state().status === 'playing' && globalThis.__game.idle())
      const start = await g('state')
      if (n === 1) levelCount = start.levelCount
      let taps = 0
      while ((await g('state')).status === 'playing' && taps < 500) {
        await until(() => globalThis.__game.idle())
        await click(await g('hint'))
        taps++
      }
      await until(() => globalThis.__game.panelOpen(), 30000)
      const end = await g('state')
      const residue = await g('residue')
      const ok = end.status === 'won' && residue === 0
      log.push({ step: `第 ${n} 关`, ok, taps, residue })
      if (!ok) break
      if (start.levelCount !== undefined && start.levelIndex >= start.levelCount - 1) break
      await page.screenshot({ path: `temp/playtest-level-${String(n).padStart(2, '0')}.png` })
      await click(await g('button', NEXT))
      await until(() => globalThis.__game.state().levelIndex !== undefined)
    }
  } catch (e) {
    await page.screenshot({ path: 'temp/playtest-level-fail.png' })
    log.push({ step: '异常', ok: false, error: String(e).slice(0, 200), screen: await g('screen'), state: await g('state') })
  }
  // 通关数必须等于 state().levelCount；缺 levelCount 记失败（否则少跑几关也会“通过”）
  const cleared = log.filter((l) => l.ok).length
  log.push(levelCount === undefined
    ? { step: '通关数', ok: false, error: 'state().levelCount 缺失，无法核对通关数' }
    : { step: '通关数', ok: cleared === levelCount, cleared, levelCount })
  const m = await g('metrics')
  const levels = m.levels
  const metrics = {
    cleared,
    misses: m.misses,
    // 每关点击数与耗时，交给制作人判断难度曲线（快速模式下耗时只作相对比较）
    tapsPerLevel: levels.map((l) => l.taps),
    secondsPerLevel: levels.map((l) => Math.round(l.ms / 100) / 10),
  }
  return { pass: log.length > 0 && log.every((l) => l.ok), log, metrics }
}
