#!/usr/bin/env node
/**
 * Web 端一键验收：把“改完代码要跑的全部检查”串成一条命令，逐项给 ✅/❌，最后一行给唯一结论。
 * 给任何模型用：照抄最后的“结论”与失败项，不需要自己判断。
 *
 * 用法：node cocos-verify.mjs --project <Cocos 工程目录> [--script tests/e2e/playtest.mjs ...] [--quick] [--no-release] [--base <基础分支>]
 *   --script      试玩脚本，可多个；不传时用工程 tests/e2e/ 下全部 .mjs（--quick 时只用 playtest.mjs；以 _ 开头的是辅助文件，不运行）
 *   --quick       日常回归：跳过 release 构建，只跑 playtest.mjs
 *   --no-release  不做 wechatgame release 包体检查（档位标“部分”，结论至多为未验证）
 *   --base        基础分支；AGENTS.md、CLAUDE.md、package.json 相对它有改动时结论至多为未验证（交用户确认）
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
import { checkArgs, SCORING_FILES, finalVerdict, flakyDetail, noTestScriptRow, partialReasons, shouldRerun } from './lib-verify.mjs'

const args = process.argv.slice(2)
const argCheck = checkArgs(args)
if (argCheck.error) {
  console.log(`⚠️ 无法识别的参数：${argCheck.error}\n结论：未验证（缺：可识别的参数 ${argCheck.error}）`)
  process.exit(3)
}
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const project = resolve(all('--project')[0] ?? process.cwd())
const quick = args.includes('--quick')
const here = dirname(fileURLToPath(import.meta.url))
const typecheck = join(here, '../../weicoz-cocos-dev/scripts/cocos-typecheck.mjs')
const rows = []
const load = loadavg()[0]
const loadHigh = load > cpus().length * 0.8 // 每核负载超 0.8 视为偏高：超时类失败多半是环境导致

const tier = quick ? 'quick' : 'full'
const run = (name, cmd, cmdArgs, judge, env = {}) => {
  process.stdout.write(`… ${name}\n`)
  const r = spawnSync(cmd, cmdArgs, { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, ...env } })
  const out = `${r.stdout ?? ''}\n${r.stderr ?? ''}`
  const { ok, detail } = judge(r.status, out)
  const unverified = !ok && /找不到 CocosCreator/.test(out)
  rows.push({ name, ok, detail: unverified ? '缺 CocosCreator：设 COCOS_CREATOR_BIN' : detail, unverified })
  return out
}
const lastLine = (out, re) => out.split('\n').filter((l) => re.test(l)).pop()?.trim() ?? ''

process.on('uncaughtException', (e) => {
  console.log(`⚠️ 脚本异常：${String(e?.message ?? e).slice(0, 200)}\n结论：未验证（缺：脚本异常，见上一行）`)
  process.exit(3)
})
process.on('unhandledRejection', (e) => { throw e })

if (!existsSync(join(project, 'assets'))) {
  console.log(`⚠️ ${project} 下没有 assets/：--project 要指向 Cocos 工程目录\n结论：未验证（缺：Cocos 工程目录）`)
  process.exit(3)
}

const base = all('--base')[0]
if (base) {
  const git = (a) => spawnSync('git', ['-C', project, ...a], { encoding: 'utf8' })
  const d = git(['diff', '--name-only', '--relative', base, '--', ...SCORING_FILES])
  if (d.status !== 0) {
    rows.push({ name: '评分配置对照', ok: false, unverified: true, missing: `评分配置对照（${base} 不可用）`, detail: `无法对照基线 ${base}：${(d.stderr || '').split('\n')[0]}` })
  } else {
    const u = git(['ls-files', '--others', '--exclude-standard', '--', ...SCORING_FILES])
    const changed = [...d.stdout.split('\n'), ...(u.stdout || '').split('\n')].filter(Boolean)
    if (changed.length) rows.push({ name: '评分配置', ok: false, unverified: true, missing: '评分配置改动待用户确认', detail: `相对 ${base} 有改动：${changed.join('、')}` })
  }
}

run('类型检查', process.execPath, [typecheck, '--project', project], (code, out) =>
  ({ ok: code === 0, detail: code === 0 ? '通过' : lastLine(out, /error TS/) || '失败' }))

let pkg = {}
try {
  if (existsSync(join(project, 'package.json'))) pkg = JSON.parse(readFileSync(join(project, 'package.json'), 'utf8'))
} catch {
  console.log('⚠️ package.json 读不出来（不是合法 JSON 或无权限）\n结论：未验证（缺：可读的 package.json）')
  process.exit(3)
}
if (pkg.scripts?.test) {
  const judgeUnit = (code, out) =>
    ({ ok: code === 0, detail: lastLine(out, /^\s*FAIL\s/) || lastLine(out, /Tests\s+\d+|passed/) || (code === 0 ? '通过' : '失败') })
  // VERIFY_TIER 让项目测试按档位调整规模（如属性测试的种子数）
  const env = { VERIFY_TIER: tier }
  const out = run('单元测试', 'npm', ['test', '--silent'], judgeUnit, env)
  // 仅本机负载高且失败全是超时类时重跑 1 次；时长断言和逻辑失败不重跑
  if (!rows.at(-1).ok && shouldRerun(out, loadHigh)) {
    const first = rows.pop()
    run('单元测试', 'npm', ['test', '--silent'], judgeUnit, env)
    const last = rows.at(-1)
    if (last.ok) { last.detail = flakyDetail(out); last.warn = true }
    else last.detail = `重跑仍失败：${last.detail}（首轮：${first.detail}）`
  }
} else {
  rows.push(noTestScriptRow())
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
  scripts = readdirSync(e2e).filter((f) => f.endsWith('.mjs') && !f.startsWith('_')).sort().map((f) => `tests/e2e/${f}`)
  if (quick) scripts = scripts.filter((s) => s.endsWith('/playtest.mjs'))
}
if (!scripts.length) {
  rows.push({ name: '浏览器试玩', ok: false, detail: '没有试玩脚本：按 references/playtest-hook.md 写 tests/e2e/playtest.mjs' })
} else if (rows.find((r) => r.name === 'web-mobile 构建')?.ok) {
  const out = run('浏览器试玩', process.execPath, [join(here, 'cocos-playtest.mjs'), '--project', project, ...all('--port').flatMap((p) => ['--port', p]), ...scripts.flatMap((s) => ['--script', s])], (code, o) => {
    const lines = o.split('\n').filter((l) => /^(✅|❌)|失败步骤|错误：/.test(l)).map((l) => l.trim())
    return { ok: code === 0, detail: lines.join('；') || '无输出' }
  }, quick ? { PLAYTEST_FAST: '1' } : {}) // 快检开快速模式，全检用真实动画
  const metricLines = out.split('\n').filter((l) => /^\s*指标：/.test(l)).map((l) => l.trim().replace(/^指标：/, ''))
  if (metricLines.length) rows.push({ name: '体验指标', ok: true, info: true, detail: metricLines.join('；').slice(0, 600) })
  const contacts = [...out.matchAll(/联系图（视觉巡检看这张）：(.+)/g)].map((m) => m[1].trim())
  rows.push({ name: '视觉巡检', ok: true, info: true, detail: contacts.length ? `待人工或看图模型检查（共 ${contacts.length} 张，逐张看）：${contacts.join('；')}（清单见 weicoz-verify references/visual-checklist.md 与 SKILL.md 第 4 节；不能看图时用 modlens）` : '无截图' })
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

const partial = partialReasons({ quick, noRelease: args.includes('--no-release'), scriptGiven: all('--script').length > 0 })
if (partial.length) rows.push({ name: '档位', ok: true, info: true, detail: `部分（用了 ${partial.join('、')}）` })
if (loadHigh) console.log(`⚠️ 负载高（1 分钟负载 ${load.toFixed(1)}，${cpus().length} 核），超时可能是环境导致`)
console.log('')
const mark = (r) => (r.info || r.warn ? '⚠️' : r.ok ? '✅' : r.unverified ? '⚠️' : '❌')
for (const r of rows) console.log(`${mark(r)} ${r.name}：${r.detail}`)
const { verdict, line } = finalVerdict(rows, partial)
console.log(line)
process.exit(verdict)
