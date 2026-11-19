#!/usr/bin/env node
/**
 * 合并与上传门（通用）：只在“合并到主分支”和“上传”前运行。
 * 用法：node verify-gate.mjs --project <目录> [--base <分支>] [--build <产物目录>[:<平台>]]... [--allow-debug]
 * 检查：戳记存在；commit==HEAD；tier=full；verdict=通过；戳记 base 非空且等于 --base；工作区干净；
 *       每个产物 commit==HEAD、dirty===false、release===true（--allow-debug 放宽）、平台一致。
 * 不传 --base 时按 develop、main、master 取第一个存在的分支。退出码：0 通过，1 不通过。最后一行是唯一结论。
 */
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const project = resolve(all('--project')[0] ?? process.cwd())
const allowDebug = args.includes('--allow-debug')
const here = dirname(fileURLToPath(import.meta.url))
const git = (a) => spawnSync('git', ['-C', project, ...a], { encoding: 'utf8' })
const readJson = (f) => { try { return JSON.parse(readFileSync(f, 'utf8')) } catch { return null } }
const short = (c) => String(c).slice(0, 8)

const missing = []
const row = (ok, okText, failText, fix) => {
  console.log(ok ? `✅ ${okText}` : `❌ ${failText}\n   下一步：${fix}`)
  if (!ok) missing.push(failText)
}

const head = git(['rev-parse', 'HEAD'])
const gitDir = git(['rev-parse', '--absolute-git-dir'])
if (head.status !== 0 || gitDir.status !== 0) {
  console.log(`❌ ${project} 不是 git 仓库\n结论：不通过（缺：git 仓库）`)
  process.exit(1)
}
const HEAD = head.stdout.trim()
const base = all('--base')[0] ?? ['develop', 'main', 'master'].find((b) => git(['rev-parse', '--verify', '--quiet', `refs/heads/${b}`]).status === 0)
const verifyCmd = `在项目验证约定（AGENTS.md「## 验证约定」）里的全检命令后加 --base ${base ?? '<基础分支>'}，在 ${project} 运行`

const stamp = readJson(join(gitDir.stdout.trim(), 'verify-stamp.json'))
row(!!stamp, '全检戳记存在', '全检戳记不存在', `提交改动后：${verifyCmd}`)
if (stamp) {
  row(stamp.commit === HEAD, '戳记提交号等于 HEAD', `戳记提交号不符（戳记 ${short(stamp.commit)}，HEAD ${short(HEAD)}）`, `提交后重跑全检。${verifyCmd}`)
  row(stamp.tier === 'full' && stamp.verdict === '通过', '戳记是全检且结论通过', '戳记不是全检通过', `重跑全检。${verifyCmd}`)
  row(!!stamp.base && stamp.base === base, `戳记基线与 ${base} 一致`, `戳记基线不符（戳记 ${stamp.base || '空'}，要求 ${base ?? '无可用基础分支'}）`, `带 --base ${base ?? '<基础分支>'} 重跑全检`)
}
row(git(['status', '--porcelain']).stdout.trim() === '', '工作区干净', '工作区有未提交改动或未跟踪文件', '先提交或清理改动，再重新全检（戳记只在干净工作区生成）')

for (const spec of all('--build')) {
  const m = spec.match(/^(.*?)(?::([A-Za-z][\w-]*))?$/) // 平台名以字母开头，避免吃掉 Windows 盘符
  const dir = resolve(m[1])
  const wantPlatform = m[2]
  const bc = readJson(join(dir, '.build-commit.json'))
  const rebuild = `提交后重新构建（构建脚本要调用 stamp.mjs build-start/build，release 构建加 --release）：${join(here, 'stamp.mjs')} build`
  const bad = !bc ? '缺 .build-commit.json（不是本流程构建的产物）'
    : bc.commit !== HEAD ? `构建提交号不符（产物 ${short(bc.commit)}，HEAD ${short(HEAD)}）`
    : bc.dirty !== false ? '构建时工作区有改动或 dirty 字段缺失'
    : !allowDebug && bc.release !== true ? '不是 release 构建'
    : wantPlatform && bc.platform !== wantPlatform ? `平台不符（产物 ${bc.platform}，要求 ${wantPlatform}）`
    : ''
  row(!bad, `${dir} 构建出自当前 HEAD`, `${dir} ${bad}`, rebuild)
}

if (!missing.length) console.log(`结论：通过（HEAD ${short(HEAD)}${all('--build').length ? `，${all('--build').length} 个产物` : ''}）`)
else console.log(`结论：不通过（缺：${missing.join('；')}）`)
process.exit(missing.length ? 1 : 0)
