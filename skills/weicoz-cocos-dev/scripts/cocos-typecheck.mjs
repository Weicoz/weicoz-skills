#!/usr/bin/env node
/**
 * 离线类型检查 Cocos 脚本：不启动编辑器，用本机 Creator 自带的引擎声明 cc.d.ts。
 * 用法：node cocos-typecheck.mjs [--project <工程根>] [--include "assets/scripts/**\/*.ts"]
 * 需要工程或全局可用的 typescript（npx tsc）。
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : fallback
}
const project = resolve(flag('--project', process.cwd()))
const include = flag('--include', 'assets/**/*.ts')

const wanted = (() => {
  try { return JSON.parse(readFileSync(join(project, 'package.json'), 'utf8')).creator?.version } catch { return undefined }
})()
const declFrom = (app) => join(app, 'Contents/Resources/resources/3d/engine/bin/.declarations/cc.d.ts')
const declarations = [
  process.env.COCOS_ENGINE_DTS,
  process.env.COCOS_CREATOR_BIN && declFrom(resolve(process.env.COCOS_CREATOR_BIN, '../../..')),
  wanted && declFrom(`/Applications/Cocos/Creator/${wanted}/CocosCreator.app`),
  declFrom('/Applications/CocosCreator.app'),
].filter(Boolean).find((p) => existsSync(p))
if (!declarations) {
  console.error('错误：找不到 Cocos 引擎声明 cc.d.ts。\n请配置：export COCOS_ENGINE_DTS=<cc.d.ts 路径> 或 COCOS_CREATOR_BIN=<CocosCreator 可执行文件>')
  process.exit(1)
}

const dir = mkdtempSync(join(tmpdir(), 'cocos-typecheck-'))
const tsconfig = join(dir, 'tsconfig.json')
writeFileSync(tsconfig, JSON.stringify({
  compilerOptions: {
    target: 'ES2019',
    module: 'ESNext',
    moduleResolution: 'bundler',
    strict: true,
    experimentalDecorators: true,
    noEmit: true,
    skipLibCheck: true,
    types: [declarations],
  },
  include: [join(project, include)],
  exclude: [join(project, 'library'), join(project, 'temp'), join(project, 'build')],
}, null, 2))

const localTsc = join(project, 'node_modules/.bin/tsc')
const [cmd, cmdArgs] = existsSync(localTsc) ? [localTsc, ['-p', tsconfig]] : ['npx', ['-y', '-p', 'typescript', 'tsc', '-p', tsconfig]]
const run = spawnSync(cmd, cmdArgs, { stdio: 'inherit' })
if (run.status === 0) console.log('Cocos 脚本类型检查通过')
process.exit(run.status ?? 1)
