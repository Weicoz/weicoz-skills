#!/usr/bin/env node
// 通用门与戳记自测：临时 git 仓库覆盖各情形。用法：node gate.test.mjs
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const gate = join(here, 'verify-gate.mjs')
const stampCli = join(here, 'stamp.mjs')
const root = mkdtempSync(join(tmpdir(), 'verify-gate-'))
const git = (cwd, ...a) => spawnSync('git', a, { cwd, encoding: 'utf8' })
let fail = 0
const report = (ok, text, extra = '') => { if (!ok) fail++; console.log(`${ok ? '✅' : '❌'} ${text}${ok ? '' : `\n${extra}`}`) }

const mkRepo = () => {
  const d = mkdtempSync(join(root, 'repo-'))
  git(d, 'init', '-q', '-b', 'main')
  git(d, 'config', 'user.email', 't@example.com'); git(d, 'config', 'user.name', 't')
  writeFileSync(join(d, '.gitignore'), 'out/\n')
  writeFileSync(join(d, 'a.txt'), '1')
  git(d, 'add', '.'); git(d, 'commit', '-qm', 'init')
  return d
}
const head = (d) => git(d, 'rev-parse', 'HEAD').stdout.trim()
const gdir = (d) => git(d, 'rev-parse', '--absolute-git-dir').stdout.trim()
const stampFile = (d) => join(gdir(d), 'verify-stamp.json')
const stamp = (d, o = {}) => writeFileSync(stampFile(d), JSON.stringify({ commit: head(d), tier: 'full', base: 'main', clean: true, verdict: '通过', at: 'x', ...o }))
const build = (o) => { const b = mkdtempSync(join(root, 'build-')); writeFileSync(join(b, '.build-commit.json'), JSON.stringify(o)); return b }
const check = (name, d, builds, want, extra = []) => {
  const r = spawnSync(process.execPath, [gate, '--project', d, ...extra, ...builds.flatMap((b) => ['--build', b])], { encoding: 'utf8' })
  report(r.status === want, `${name}（退出码 ${r.status}，期望 ${want}）`, r.stdout)
}
const ok = (d, o = {}) => ({ commit: head(d), dirty: false, platform: 'wechatgame', release: true, ...o })

let d = mkRepo(); check('无戳记', d, [], 1)
d = mkRepo(); stamp(d, { commit: 'deadbeef' }); check('commit 不符', d, [], 1)
d = mkRepo(); stamp(d, { tier: 'quick' }); check('tier 错', d, [], 1)
d = mkRepo(); stamp(d, { verdict: '不通过' }); check('verdict 错', d, [], 1)
d = mkRepo(); stamp(d, { base: null }); check('base 为空', d, [], 1)
d = mkRepo(); stamp(d, { base: 'other' }); check('base 不符', d, [], 1)
d = mkRepo(); stamp(d); writeFileSync(join(d, 'a.txt'), '2'); check('工作区脏（已跟踪）', d, [], 1)
d = mkRepo(); stamp(d); writeFileSync(join(d, 'new.txt'), 'x'); check('未跟踪文件', d, [], 1)
d = mkRepo(); stamp(d); mkdirSync(join(d, 'out')); writeFileSync(join(d, 'out/x'), 'x'); check('ignored 目录不算脏', d, [], 0)
d = mkRepo(); stamp(d); check('build commit 不符', d, [build(ok(d, { commit: 'deadbeef' }))], 1)
d = mkRepo(); stamp(d); const nd = ok(d); delete nd.dirty; check('build dirty 缺失', d, [build(nd)], 1)
d = mkRepo(); stamp(d); check('build dirty=true', d, [build(ok(d, { dirty: true }))], 1)
d = mkRepo(); stamp(d); check('build release=false', d, [build(ok(d, { release: false }))], 1)
d = mkRepo(); stamp(d); check('build release=false 且 --allow-debug', d, [build(ok(d, { release: false }))], 0, ['--allow-debug'])
d = mkRepo(); stamp(d)
{
  const b = build(ok(d))
  const run = (spec) => spawnSync(process.execPath, [gate, '--project', d, '--build', spec], { encoding: 'utf8' }).status
  report(run(`${b}:bytedance-mini-game`) === 1, '平台不符')
  report(run(`${b}:wechatgame`) === 0, '平台一致')
}
d = mkRepo(); stamp(d); check('全部满足', d, [build(ok(d))], 0)
d = mkRepo(); stamp(d); check('不传 --base 时默认取 main', d, [], 0)
// worktree：git-dir 是 .git/worktrees/<名>，戳记按 worktree 区分
d = mkRepo()
{
  const w = join(root, `wt-${Math.random()}`)
  git(d, 'worktree', 'add', '-q', '-b', 'feat', w)
  check('worktree 无戳记', w, [], 1)
  writeFileSync(stampFile(w), JSON.stringify({ commit: head(w), tier: 'full', base: 'main', clean: true, verdict: '通过', at: 'x' }))
  report(stampFile(w).includes('worktrees'), 'worktree 的 git-dir 在 worktrees 下', stampFile(w))
  check('worktree 全部满足', w, [], 0)
  check('主工作区不受 worktree 戳记影响', d, [], 1)
}

// stamp finish
const cli = (d, ...a) => spawnSync(process.execPath, [stampCli, ...a, '--project', d], { encoding: 'utf8' })
const fin = (d, ...a) => cli(d, 'finish', '--tier', 'full', '--code', '0', '--base', 'main', ...a)
const stale = (d) => writeFileSync(stampFile(d), '{"commit":"old"}')
const expectNone = (name, d) => report(!existsSync(stampFile(d)), name, '戳记不应存在')
d = mkRepo(); cli(d, 'start'); fin(d); report(existsSync(stampFile(d)) && JSON.parse(spawnSync('cat', [stampFile(d)], { encoding: 'utf8' }).stdout).commit === head(d), 'finish 满足条件写戳记')
d = mkRepo(); stale(d); cli(d, 'start'); expectNone('start 删旧戳记', d)
d = mkRepo(); writeFileSync(join(d, 'u.txt'), 'x'); cli(d, 'start'); stale(d); fin(d); expectNone('开始时脏：不写并删旧戳记', d)
d = mkRepo(); cli(d, 'start'); writeFileSync(join(d, 'u.txt'), 'x'); stale(d); fin(d); expectNone('结束时脏：不写', d)
d = mkRepo(); cli(d, 'start'); writeFileSync(join(d, 'b.txt'), 'x'); git(d, 'add', '.'); git(d, 'commit', '-qm', 'mid'); stale(d); fin(d); expectNone('HEAD 中途变化：不写', d)
d = mkRepo(); cli(d, 'start'); stale(d); cli(d, 'finish', '--tier', 'quick', '--code', '0', '--base', 'main'); expectNone('quick：不写', d)
d = mkRepo(); cli(d, 'start'); stale(d); fin(d, '--narrowed'); expectNone('narrowed：不写', d)
d = mkRepo(); cli(d, 'start'); stale(d); cli(d, 'finish', '--tier', 'full', '--code', '1', '--base', 'main'); expectNone('code≠0：不写', d)
d = mkRepo(); cli(d, 'start'); stale(d); cli(d, 'finish', '--tier', 'full', '--code', '0'); expectNone('无 base：不写', d)
d = mkRepo(); stale(d); fin(d); expectNone('未调用 start：不写', d)
// build / build-start
d = mkRepo()
{
  const o = join(root, 'o'); mkdirSync(o)
  cli(d, 'build', '--dir', o, '--platform', 'wechatgame', '--release')
  const bc = JSON.parse(spawnSync('cat', [join(o, '.build-commit.json')], { encoding: 'utf8' }).stdout)
  report(bc.commit === head(d) && bc.dirty === false && bc.release === true && bc.platform === 'wechatgame', 'build 写来源戳')
  cli(d, 'build-start', '--dir', o)
  report(!existsSync(join(o, '.build-commit.json')), 'build-start 删旧来源戳')
}

rmSync(root, { recursive: true, force: true })
console.log(fail ? `结论：不通过（${fail} 项失败）` : '结论：通过')
process.exit(fail ? 1 : 0)
