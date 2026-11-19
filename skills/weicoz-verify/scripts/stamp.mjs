#!/usr/bin/env node
/**
 * 全检戳记与构建来源戳。可 import，也可命令行调用（shell 自建适配器用）。
 *   node stamp.mjs start [--project <目录>]
 *   node stamp.mjs finish [--project <目录>] --tier <full|quick> --code <退出码> [--base <分支>] [--narrowed]
 *   node stamp.mjs build-start --dir <产物目录>
 *   node stamp.mjs build --dir <产物目录> --platform <名> [--release] [--project <目录>]
 * 戳记写在 git-dir/verify-stamp.json（按 worktree 区分）；“干净”= git status --porcelain 为空。
 * 命令行永远退出 0：是否通过看验证命令自己的结论行。
 */
import { spawnSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const git = (project, a) => {
  const r = spawnSync('git', ['-C', project, ...a], { encoding: 'utf8' })
  return r.status === 0 ? r.stdout.trim() : null
}
export const gitState = (project) => ({
  gitDir: git(project, ['rev-parse', '--absolute-git-dir']),
  head: git(project, ['rev-parse', 'HEAD']),
  status: git(project, ['status', '--porcelain']), // null = 不是 git 仓库
})
const readJson = (f) => { try { return JSON.parse(readFileSync(f, 'utf8')) } catch { return null } }

/** 验证开始时调用：记 HEAD 与是否干净，删旧戳记 */
export function start(project) {
  const s = gitState(resolve(project))
  if (!s.gitDir) return
  rmSync(join(s.gitDir, 'verify-stamp.json'), { force: true })
  writeFileSync(join(s.gitDir, 'verify-run.json'), JSON.stringify({ head: s.head, clean: s.status === '' }))
}

/** 验证结束时调用：满足全部条件才写戳记，否则删除。返回 { written, reason } 并打印一行状态 */
export function finish({ project, tier, code, base, narrowed = false }) {
  const s = gitState(resolve(project))
  if (!s.gitDir || !s.head) return report(false, '不是 git 仓库或没有提交')
  const stampFile = join(s.gitDir, 'verify-stamp.json')
  const runFile = join(s.gitDir, 'verify-run.json')
  const run = readJson(runFile)
  rmSync(stampFile, { force: true })
  rmSync(runFile, { force: true })
  const why = tier !== 'full' ? `档位是 ${tier}，只有全检写戳记`
    : Number(code) !== 0 ? `结论不是通过（退出码 ${code}）`
    : narrowed ? '不是完整全检（范围被缩小）'
    : !base ? '没有 --base（评分配置没对照基线）'
    : !run ? '没有开始记录（运行前未调用 start）'
    : !run.clean ? '运行开始时工作区有改动'
    : s.status !== '' ? '运行结束时工作区有改动'
    : run.head !== s.head ? 'HEAD 在验证途中变化'
    : ''
  if (why) return report(false, why)
  writeFileSync(stampFile, JSON.stringify({ commit: s.head, tier, base, clean: true, verdict: '通过', at: new Date().toISOString() }, null, 2))
  return report(true, `已写 ${stampFile}（commit ${s.head.slice(0, 8)}）`)
}
function report(written, reason) {
  console.log(written ? `戳记：${reason}` : `戳记：未写（${reason}），已清除旧戳记`)
  return { written, reason }
}

/** 构建开始前调用：删旧来源戳，构建失败时不会残留旧文件 */
export const buildStart = (dir) => rmSync(join(resolve(dir), '.build-commit.json'), { force: true })

/** 构建成功后调用：写 <dir>/.build-commit.json */
export function build({ dir, project = process.cwd(), platform, release = false }) {
  const s = gitState(resolve(project))
  mkdirSync(resolve(dir), { recursive: true })
  writeFileSync(join(resolve(dir), '.build-commit.json'), JSON.stringify({ commit: s.head, dirty: s.status !== '', platform, release }, null, 2))
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [cmd, ...rest] = process.argv.slice(2)
  const val = (n) => { const i = rest.indexOf(n); return i >= 0 ? rest[i + 1] : undefined }
  const project = val('--project') ?? process.cwd()
  if (cmd === 'start') start(project)
  else if (cmd === 'finish') finish({ project, tier: val('--tier'), code: val('--code') ?? '1', base: val('--base'), narrowed: rest.includes('--narrowed') })
  else if (cmd === 'build-start' && val('--dir')) buildStart(val('--dir'))
  else if (cmd === 'build' && val('--dir')) build({ dir: val('--dir'), project, platform: val('--platform'), release: rest.includes('--release') })
  else console.error('用法：stamp.mjs <start|finish|build-start|build> ...（见文件头注释）')
}
