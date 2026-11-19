#!/usr/bin/env node
/**
 * 合并与上传门：只在“合并到主分支”和“上传”前运行，日常提交不受影响。
 * 用法：node cocos-gate.mjs --project <工程> [--build <产物目录>]...
 * 检查：全检戳记存在且等于 HEAD；工作区干净；每个产物的 .build-commit.json 等于 HEAD 且 dirty 为 false。
 * 退出码：0 通过，1 不通过。最后一行是唯一结论。
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const project = resolve(all('--project')[0] ?? process.cwd())
const builds = all('--build').map((b) => resolve(b))
const here = dirname(fileURLToPath(import.meta.url))
const git = (a) => spawnSync('git', ['-C', project, ...a], { encoding: 'utf8' })
const readJson = (f) => { try { return JSON.parse(readFileSync(f, 'utf8')) } catch { return null } }

const missing = []
const row = (ok, okText, failText, fix) => {
  console.log(ok ? `✅ ${okText}` : `❌ ${failText}\n   下一步：${fix}`)
  if (!ok) missing.push(failText)
}
const verifyCmd = `node ${join(here, 'cocos-verify.mjs')} --project ${project} --base main`

const head = git(['rev-parse', 'HEAD'])
const gitDir = git(['rev-parse', '--absolute-git-dir'])
if (head.status !== 0 || gitDir.status !== 0) {
  console.log(`❌ ${project} 不是 git 仓库\n结论：不通过（缺：git 仓库）`)
  process.exit(1)
}
const HEAD = head.stdout.trim()

const stamp = readJson(join(gitDir.stdout.trim(), 'verify-stamp.json'))
row(!!stamp && stamp.commit === HEAD && stamp.tier === 'full' && stamp.verdict === '通过', '全检戳记有效且等于 HEAD',
  stamp ? `全检戳记${stamp.commit === HEAD ? '无效（档位或结论不符）' : `提交号不符（戳记 ${String(stamp.commit).slice(0, 8)}，HEAD ${HEAD.slice(0, 8)}）`}` : '全检戳记不存在',
  `提交改动后运行：${verifyCmd}`)
const dirty = git(['status', '--porcelain']).stdout.trim()
row(dirty === '', '工作区干净', '工作区有未提交改动', '先提交或清理改动，再重新全检（戳记只在干净工作区生成）')

for (const b of builds) {
  const bc = readJson(join(b, '.build-commit.json'))
  const rebuild = `提交后重新构建：node ${join(here, 'cocos-build.mjs')} --project ${project} --platform <平台> --release`
  if (!bc) row(false, '', `${b} 缺 .build-commit.json（不是本流程构建的产物）`, rebuild)
  else if (bc.commit !== HEAD) row(false, '', `${b} 构建提交号不符（产物 ${String(bc.commit).slice(0, 8)}，HEAD ${HEAD.slice(0, 8)}）`, rebuild)
  else if (bc.dirty !== false) row(false, '', `${b} 构建时工作区有改动（dirty）`, rebuild)
  else row(true, `${b} 构建出自当前 HEAD`)
}

if (!missing.length) console.log(`结论：通过（HEAD ${HEAD.slice(0, 8)}${builds.length ? `，${builds.length} 个产物` : ''}）`)
else console.log(`结论：不通过（缺：${missing.join('；')}）`)
process.exit(missing.length ? 1 : 0)
