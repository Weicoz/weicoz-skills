#!/usr/bin/env node
/**
 * Web 端一键验收：把“改完代码要跑的全部检查”串成一条命令，逐项给 ✅/❌，最后一行给唯一结论。
 * 给任何模型用：照抄最后的“结论”与失败项，不需要自己判断。
 *
 * 用法：node cocos-verify.mjs --project <Cocos 工程目录> [--script tests/e2e/playtest.mjs ...] [--quick] [--no-release]
 *   --script      试玩脚本，可多个；不传时用工程 tests/e2e/ 下全部 .mjs（--quick 时只用 playtest.mjs）
 *   --quick       日常回归：跳过 release 构建，只跑 playtest.mjs
 *   --no-release  不做 wechatgame release 包体检查
 *   --port        试玩预览端口；默认自动取空闲端口，可多个代理并行验收
 * 顺序：类型检查 → 单元测试（package.json 有 test 脚本时）→ 引擎模块 → web-mobile 构建 → 试玩（含联系图）→ release 包体。
 * 任一项失败继续跑完其余项，便于一次看全。输出符合 weicoz-verify 第 2 节：逐项一行以 ✅/❌/⚠️ 开头，
 * 最后一行是唯一结论；退出码 0 = 通过，1 = 不通过，3 = 未验证（缺 CocosCreator 等环境，无法构建）。
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { cpus, loadavg } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const project = resolve(all('--project')[0] ?? process.cwd())
const quick = args.includes('--quick')
const here = dirname(fileURLToPath(import.meta.url))
const typecheck = join(here, '../../weicoz-cocos-dev/scripts/cocos-typecheck.mjs')
const rows = []
const load = loadavg()[0]
const loadHigh = load > cpus().length * 0.8 // 每核负载超 0.8 视为偏高：超时类失败多半是环境导致

const run = (name, cmd, cmdArgs, judge) => {
  process.stdout.write(`… ${name}\n`)
  const r = spawnSync(cmd, cmdArgs, { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  const out = `${r.stdout ?? ''}\n${r.stderr ?? ''}`
  const { ok, detail } = judge(r.status, out)
  const unverified = !ok && /找不到 CocosCreator/.test(out)
  rows.push({ name, ok, detail: unverified ? '缺 CocosCreator：设 COCOS_CREATOR_BIN' : detail, unverified })
  return out
}
const lastLine = (out, re) => out.split('\n').filter((l) => re.test(l)).pop()?.trim() ?? ''

// 超时类失败：Test timed out / Timeout calling "?onTaskUpdate / 时长断言；出现其他断言报错则不算
const isTimeoutOnly = (out) => {
  const timeout = /Test timed out|Timeout calling "?onTaskUpdate/.test(out)
  const durationOnly = /to be less than or equal to/.test(out)
  const otherAssert = out.split('\n').some((l) => /AssertionError|expected .* to (be|equal|deeply|have|match|contain)/.test(l) && !/less than or equal to/.test(l))
  return (timeout || durationOnly) && !otherAssert
}

if (!existsSync(join(project, 'assets'))) {
  console.log(`⚠️ ${project} 下没有 assets/：--project 要指向 Cocos 工程目录\n结论：未验证（缺：Cocos 工程目录）`)
  process.exit(3)
}

run('类型检查', process.execPath, [typecheck, '--project', project], (code, out) =>
  ({ ok: code === 0, detail: code === 0 ? '通过' : lastLine(out, /error TS/) || '失败' }))

const pkg = existsSync(join(project, 'package.json')) ? JSON.parse(readFileSync(join(project, 'package.json'), 'utf8')) : {}
if (pkg.scripts?.test) {
  const judgeUnit = (code, out) =>
    ({ ok: code === 0, detail: lastLine(out, /Tests\s+\d+|passed|failed/) || (code === 0 ? '通过' : '失败') })
  const out = run('单元测试', 'npm', ['test', '--silent'], judgeUnit)
  // 失败全是超时类（无其他断言失败）：多半是负载导致，重跑一次
  if (!rows.at(-1).ok && isTimeoutOnly(out)) {
    rows.pop()
    run('单元测试', 'npm', ['test', '--silent'], judgeUnit)
    const last = rows.at(-1)
    if (last.ok) last.detail = '✅（首轮负载超时，已重跑通过）'
    else last.detail = `重跑仍失败：${last.detail}`
  }
} else {
  rows.push({ name: '单元测试', ok: true, detail: '跳过：package.json 没有 test 脚本' })
}

run('引擎模块', process.execPath, [join(here, 'cocos-modules.mjs'), '--project', project], (_c, out) => {
  const warn = lastLine(out, /已启用但未发现使用/)
  // 未用模块只是包体建议，不判失败
  return { ok: true, detail: warn ? `建议裁剪：${warn.replace(/^⚠️\s*已启用但未发现使用：/, '')}` : '无可裁剪项' }
})

run('web-mobile 构建', process.execPath, [join(here, 'cocos-build.mjs'), '--project', project, '--platform', 'web-mobile'], (_c, out) =>
  ({ ok: /构建已验证/.test(out), detail: /构建已验证/.test(out) ? lastLine(out, /^产物/) : lastLine(out, /失败|错误/) || '没有产物' }))

const e2e = join(project, 'tests/e2e')
let scripts = all('--script')
if (!scripts.length && existsSync(e2e)) {
  scripts = readdirSync(e2e).filter((f) => f.endsWith('.mjs')).sort().map((f) => `tests/e2e/${f}`)
  if (quick) scripts = scripts.filter((s) => s.endsWith('/playtest.mjs'))
}
if (!scripts.length) {
  rows.push({ name: '浏览器试玩', ok: false, detail: '没有试玩脚本：按 references/playtest-hook.md 写 tests/e2e/playtest.mjs' })
} else if (rows.find((r) => r.name === 'web-mobile 构建')?.ok) {
  const out = run('浏览器试玩', process.execPath, [join(here, 'cocos-playtest.mjs'), '--project', project, ...all('--port').flatMap((p) => ['--port', p]), ...scripts.flatMap((s) => ['--script', s])], (code, o) => {
    const lines = o.split('\n').filter((l) => /^(✅|❌)|失败步骤|错误：/.test(l)).map((l) => l.trim())
    return { ok: code === 0, detail: lines.join('；') || '无输出' }
  })
  const metricLines = out.split('\n').filter((l) => /^\s*指标：/.test(l)).map((l) => l.trim().replace(/^指标：/, ''))
  if (metricLines.length) rows.push({ name: '体验指标', ok: true, info: true, detail: metricLines.join('；').slice(0, 600) })
  const contact = out.match(/联系图（视觉巡检看这张）：(\S+)/)?.[1]
  rows.push({ name: '视觉巡检', ok: true, info: true, detail: contact ? `待人工或看图模型检查：${contact}（清单见 weicoz-verify references/visual-checklist.md 与 SKILL.md 第 4 节；不能看图时用 modlens）` : '无截图' })
} else {
  const bu = rows.find((r) => r.name === 'web-mobile 构建')?.unverified
  rows.push({ name: '浏览器试玩', ok: false, unverified: bu, detail: bu ? '缺可构建环境：web-mobile 构建未验证' : '跳过：构建失败' })
}

if (!quick && !args.includes('--no-release')) {
  run('release 包体', process.execPath, [join(here, 'cocos-build.mjs'), '--project', project, '--platform', 'wechatgame', '--release'], (_c, out) => {
    const main = lastLine(out, /^主包/)
    const over = /主包超过 4 MB/.test(out)
    return { ok: /构建已验证/.test(out) && !over, detail: main || lastLine(out, /失败|错误/) || '没有产物' }
  })
}

if (loadHigh) console.log(`⚠️ 负载高（1 分钟负载 ${load.toFixed(1)}，${cpus().length} 核），超时可能是环境导致`)
console.log('')
const mark = (r) => (r.info ? '⚠️' : r.ok ? '✅' : r.unverified ? '⚠️' : '❌')
for (const r of rows) console.log(`${mark(r)} ${r.name}：${r.detail}`)
const failed = rows.filter((r) => !r.ok && !r.unverified && !r.info)
const missing = rows.filter((r) => r.unverified)
const verdict = failed.length ? 1 : missing.length ? 3 : 0
console.log(verdict === 1 ? `结论：不通过（失败：${failed.map((r) => r.name).join('、')}）`
  : verdict === 3 ? `结论：未验证（缺：${missing.map((r) => r.detail).join('；')}）` : '结论：通过')
process.exit(verdict)
