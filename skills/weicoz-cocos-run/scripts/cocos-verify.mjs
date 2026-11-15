#!/usr/bin/env node
/**
 * Web 端一键验收：把“改完代码要跑的全部检查”串成一条命令，逐项给 ✅/❌，最后一行给唯一结论。
 * 给任何模型用：照抄最后的“结论”与失败项，不需要自己判断。
 *
 * 用法：node cocos-verify.mjs --project <Cocos 工程目录> [--script tests/e2e/playtest.mjs ...] [--quick] [--no-release]
 *   --script      试玩脚本，可多个；不传时用工程 tests/e2e/ 下全部 .mjs（--quick 时只用 playtest.mjs）
 *   --quick       日常回归：跳过 release 构建，只跑 playtest.mjs
 *   --no-release  不做 wechatgame release 包体检查
 * 顺序：类型检查 → 单元测试（package.json 有 test 脚本时）→ 引擎模块 → web-mobile 构建 → 试玩（含联系图）→ release 包体。
 * 任一项失败继续跑完其余项，便于一次看全；退出码 0 = 通过，1 = 不通过。
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const project = resolve(all('--project')[0] ?? process.cwd())
const quick = args.includes('--quick')
const here = dirname(fileURLToPath(import.meta.url))
const typecheck = join(here, '../../weicoz-cocos-dev/scripts/cocos-typecheck.mjs')
const rows = []

const run = (name, cmd, cmdArgs, judge) => {
  process.stdout.write(`… ${name}\n`)
  const r = spawnSync(cmd, cmdArgs, { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  const out = `${r.stdout ?? ''}\n${r.stderr ?? ''}`
  const { ok, detail } = judge(r.status, out)
  rows.push({ name, ok, detail })
  return out
}
const lastLine = (out, re) => out.split('\n').filter((l) => re.test(l)).pop()?.trim() ?? ''

if (!existsSync(join(project, 'assets'))) {
  console.error(`错误：${project} 下没有 assets/。--project 要指向 Cocos 工程目录`)
  process.exit(2)
}

run('类型检查', process.execPath, [typecheck, '--project', project], (code, out) =>
  ({ ok: code === 0, detail: code === 0 ? '通过' : lastLine(out, /error TS/) || '失败' }))

const pkg = existsSync(join(project, 'package.json')) ? JSON.parse(readFileSync(join(project, 'package.json'), 'utf8')) : {}
if (pkg.scripts?.test) {
  run('单元测试', 'npm', ['test', '--silent'], (code, out) =>
    ({ ok: code === 0, detail: lastLine(out, /Tests\s+\d+|passed|failed/) || (code === 0 ? '通过' : '失败') }))
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
  const out = run('浏览器试玩', process.execPath, [join(here, 'cocos-playtest.mjs'), '--project', project, ...scripts.flatMap((s) => ['--script', s])], (code, o) => {
    const lines = o.split('\n').filter((l) => /^(✅|❌)|失败步骤|错误：/.test(l)).map((l) => l.trim())
    return { ok: code === 0, detail: lines.join('；') || '无输出' }
  })
  const contact = out.match(/联系图（视觉巡检看这张）：(\S+)/)?.[1]
  rows.push({ name: '视觉巡检', ok: true, detail: contact ? `待人工或看图模型检查：${contact}（清单见 SKILL.md 第 4 节；不能看图时用 modlens）` : '无截图' })
} else {
  rows.push({ name: '浏览器试玩', ok: false, detail: '跳过：构建失败' })
}

if (!quick && !args.includes('--no-release')) {
  run('release 包体', process.execPath, [join(here, 'cocos-build.mjs'), '--project', project, '--platform', 'wechatgame', '--release'], (_c, out) => {
    const main = lastLine(out, /^主包/)
    const over = /主包超过 4 MB/.test(out)
    return { ok: /构建已验证/.test(out) && !over, detail: main || lastLine(out, /失败|错误/) || '没有产物' }
  })
}

console.log('\n| 检查 | 结果 | 说明 |\n| --- | --- | --- |')
for (const r of rows) console.log(`| ${r.name} | ${r.ok ? '✅' : '❌'} | ${r.detail.replace(/\|/g, '/')} |`)
const pass = rows.every((r) => r.ok)
console.log(`\n结论：${pass ? '通过' : '不通过'}${pass ? '（web 端验证等级：核心循环已验证；视觉巡检项需看联系图）' : `（失败：${rows.filter((r) => !r.ok).map((r) => r.name).join('、')}）`}`)
process.exit(pass ? 0 : 1)
