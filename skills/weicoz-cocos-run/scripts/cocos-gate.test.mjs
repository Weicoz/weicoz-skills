#!/usr/bin/env node
// cocos-gate 自测：临时 git 仓库覆盖各情形，断言退出码。用法：node cocos-gate.test.mjs
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const gate = join(dirname(fileURLToPath(import.meta.url)), 'cocos-gate.mjs')
const root = mkdtempSync(join(tmpdir(), 'cocos-gate-'))
const git = (cwd, ...a) => spawnSync('git', a, { cwd, encoding: 'utf8' })
let fail = 0

const mkRepo = () => {
  const d = mkdtempSync(join(root, 'repo-'))
  git(d, 'init', '-q', '-b', 'main')
  git(d, 'config', 'user.email', 't@example.com'); git(d, 'config', 'user.name', 't')
  writeFileSync(join(d, 'a.txt'), '1')
  git(d, 'add', '.'); git(d, 'commit', '-qm', 'init')
  return d
}
const head = (d) => git(d, 'rev-parse', 'HEAD').stdout.trim()
const stamp = (d, commit) => writeFileSync(join(d, '.git', 'verify-stamp.json'), JSON.stringify({ commit, tier: 'full', base: 'main', clean: true, verdict: '通过', at: 'x' }))
const build = (d, name, o) => { const b = join(root, `${name}-${Math.random()}`); mkdirSync(b); writeFileSync(join(b, '.build-commit.json'), JSON.stringify({ platform: 'wechatgame', release: true, ...o })); return b }
const check = (name, d, builds, want) => {
  const r = spawnSync(process.execPath, [gate, '--project', d, ...builds.flatMap((b) => ['--build', b])], { encoding: 'utf8' })
  const ok = r.status === want
  if (!ok) fail++
  console.log(`${ok ? '✅' : '❌'} ${name}（退出码 ${r.status}，期望 ${want}）${ok ? '' : `\n${r.stdout}`}`)
}

let d = mkRepo()
check('无戳记', d, [], 1)
d = mkRepo(); stamp(d, 'deadbeef'); check('戳记提交号不符', d, [], 1)
d = mkRepo(); stamp(d, head(d)); writeFileSync(join(d, 'a.txt'), '2'); check('工作区有改动', d, [], 1)
d = mkRepo(); stamp(d, head(d)); check('build 提交号不符', d, [build(d, 'b', { commit: 'deadbeef', dirty: false })], 1)
d = mkRepo(); stamp(d, head(d)); check('build dirty', d, [build(d, 'b', { commit: head(d), dirty: true })], 1)
d = mkRepo(); stamp(d, head(d)); check('build 缺记录文件', d, [join(root)], 1)
d = mkRepo(); stamp(d, head(d)); check('全部满足', d, [build(d, 'b', { commit: head(d), dirty: false })], 0)
d = mkRepo(); stamp(d, head(d)); check('全部满足（无 build）', d, [], 0)

rmSync(root, { recursive: true, force: true })
console.log(fail ? `结论：不通过（${fail} 项失败）` : '结论：通过')
process.exit(fail ? 1 : 0)
