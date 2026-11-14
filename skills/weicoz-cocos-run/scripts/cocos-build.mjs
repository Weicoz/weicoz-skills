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

// 微信官方（2026-04 版文档）：主包 ≤ 4 MB，主包 + 全部分包 ≤ 30 MB，普通分包不限，独立分包 ≤ 4 MB
// https://developers.weixin.qq.com/minigame/dev/guide/base-ability/subPackage/useSubPackage.html
const TOTAL_LIMIT_MB = 30
const COCOS_DEFAULT_APPID = 'wx6ac3f5090a6b99c5'

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : fallback
}
const project = resolve(flag('--project', process.cwd()))
const config = flag('--config')
const release = args.includes('--release')
// --config 时以配置文件里的平台与输出目录为准
const cfg = config ? JSON.parse(readFileSync(resolve(config), 'utf8')) : {}
const platform = cfg.platform ?? flag('--platform', 'web-mobile')
const buildRoot = cfg.buildPath ? resolve(project, cfg.buildPath.replace(/^project:\/\//, '')) : join(project, 'build')
const outDir = join(buildRoot, cfg.outputName ?? platform)

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
  // AppID：Cocos 构建面板默认值不是有效 AppID，开发者工具命令行导入会报“不存在此 AppID”
  const pcPath = join(outDir, 'project.config.json')
  const pc = JSON.parse(readFileSync(pcPath, 'utf8'))
  if (process.env.WECHAT_APPID && pc.appid !== process.env.WECHAT_APPID) {
    pc.appid = process.env.WECHAT_APPID
    writeFileSync(pcPath, JSON.stringify(pc, null, 2))
    console.log(`AppID：已写入 WECHAT_APPID（${pc.appid}）`)
  } else if (pc.appid === COCOS_DEFAULT_APPID) {
    console.warn(`⚠️ AppID 仍是 Cocos 默认值 ${COCOS_DEFAULT_APPID}，开发者工具无法导入。设 WECHAT_APPID（小游戏测试号即可），或在构建面板填写`)
  }
  // 主包 = 上传目录 - game.json 声明的分包；remote/ 是远程包，不上传
  const MB4 = 4 * 1024 * 1024
  const subs = JSON.parse(readFileSync(join(outDir, 'game.json'), 'utf8')).subpackages ?? []
  const subSizes = subs.map((s) => [s.name ?? s.root, existsSync(join(outDir, s.root)) ? sizeOf(join(outDir, s.root)) : 0, s.independent])
  const remote = existsSync(join(outDir, 'remote')) ? sizeOf(join(outDir, 'remote')) : 0
  const upload = total - remote
  const main = upload - subSizes.reduce((sum, [, n]) => sum + n, 0)
  console.log(`主包 ${mb(main)} MB（上限 4 MB）；上传总计 ${mb(upload)} MB${remote ? `；远程包 ${mb(remote)} MB（不计入）` : ''}`)
  for (const [name, n, indep] of subSizes) console.log(`  ${indep ? '独立分包' : '分包'} ${name}：${mb(n)} MB${indep && n > MB4 ? '  ⚠️ 独立分包超过 4 MB' : ''}`)
  if (main > MB4) console.warn(`⚠️ 主包超过 4 MB${release ? '' : '（debug 未压缩，以 --release 为准）'}`)
  if (upload > TOTAL_LIMIT_MB * 1024 * 1024) console.warn(`⚠️ 上传总计超过 ${TOTAL_LIMIT_MB} MB`)
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
