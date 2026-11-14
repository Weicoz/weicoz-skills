#!/usr/bin/env node
/**
 * 命令行构建 Cocos Creator 3.8 工程（不需要打开编辑器 UI）。
 * 用法：node cocos-build.mjs [--project <工程根>] [--platform web-mobile|wechatgame] [--release] [--config <构建配置.json>]
 *
 * Creator CLI 构建成功也返回退出码 36（32 = 参数错误，34 = 构建异常）。
 * 成功判据：产物关键文件存在且为本次构建生成，而不是退出码。
 */
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { unusedModules } from './cocos-modules.mjs'

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : fallback
}
const project = resolve(flag('--project', process.cwd()))
const platform = flag('--platform', 'web-mobile')
const config = flag('--config')
const release = args.includes('--release')

const wanted = (() => {
  try { return JSON.parse(readFileSync(join(project, 'package.json'), 'utf8')).creator?.version } catch { return undefined }
})()
const creator = [
  process.env.COCOS_CREATOR_BIN,
  wanted && `/Applications/Cocos/Creator/${wanted}/CocosCreator.app/Contents/MacOS/CocosCreator`,
  '/Applications/CocosCreator.app/Contents/MacOS/CocosCreator',
].filter(Boolean).find((p) => existsSync(p))
if (!creator) {
  console.error('错误：找不到 CocosCreator。\n请配置：export COCOS_CREATOR_BIN=<CocosCreator 可执行文件路径>')
  process.exit(1)
}

const buildArg = config ? `configPath=${resolve(config)}` : `platform=${platform};debug=${!release}`
const logFile = join(tmpdir(), `cocos-build-${platform}-${Date.now()}.log`)
console.log(`构建 ${platform}（${buildArg}）\n日志：${logFile}`)

const startedAt = Date.now()
const run = spawnSync(creator, ['--project', project, '--build', buildArg], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
writeFileSync(logFile, `${run.stdout ?? ''}\n${run.stderr ?? ''}`)
const meaning = { 0: '成功', 36: '成功（Creator CLI 惯例）', 32: '构建参数无效', 34: '构建异常，查日志' }
console.log(`退出码 ${run.status}：${meaning[run.status] ?? '未知，查日志'}`)

const outDir = join(project, 'build', platform)
const required = platform === 'wechatgame' ? ['game.json', 'project.config.json'] : ['index.html']
// 旧产物可能残留：只认本次构建后更新过的文件
const missing = required.filter((f) => !existsSync(join(outDir, f)) || statSync(join(outDir, f)).mtimeMs < startedAt - 1000)
if (missing.length) {
  console.error(`失败：${outDir} 缺少或未更新 ${missing.join(', ')}`)
  console.error(execFileSync('tail', ['-n', '30', logFile], { encoding: 'utf8' }))
  process.exit(1)
}

const sizeOf = (p) => {
  const s = statSync(p)
  return s.isDirectory() ? readdirSync(p).reduce((sum, f) => sum + sizeOf(join(p, f)), 0) : s.size
}
const mb = (n) => (n / 1024 / 1024).toFixed(2)
const total = sizeOf(outDir)
console.log(`产物：${outDir}（${mb(total)} MB）`)

if (platform === 'wechatgame') {
  // 微信小游戏：主包 ≤ 4 MB，总包 ≤ 20 MB。整个目录超 4 MB 不算失败，需核对分包。
  if (total > 20 * 1024 * 1024) console.warn('⚠️ 总包超过 20 MB 上限')
  else if (total > 4 * 1024 * 1024) console.warn('⚠️ 目录超过 4 MB：核对主包与分包大小（subpackages / Asset Bundle）')
  const largest = []
  const walk = (dir) => {
    for (const f of readdirSync(dir)) {
      const p = join(dir, f)
      if (statSync(p).isDirectory()) walk(p)
      else largest.push([statSync(p).size, p.slice(outDir.length + 1)])
    }
  }
  walk(outDir)
  largest.sort((a, b) => b[0] - a[0])
  console.log('最大文件：')
  for (const [size, file] of largest.slice(0, 5)) console.log(`  ${mb(size)} MB  ${file}`)
}
const { unused } = unusedModules(project)
if (unused.length) console.warn(`⚠️ 引擎已启用但工程未使用：${unused.join(', ')}（项目设置 → 功能裁剪中关闭可减小包体）`)
console.log('状态：构建已验证；运行时未验证。')
