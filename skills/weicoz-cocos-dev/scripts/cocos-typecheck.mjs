#!/usr/bin/env node
/**
 * 离线类型检查 Cocos 脚本：不启动编辑器。
 * 声明来源：优先工程 temp/declarations/（编辑器打开过工程后生成，含 cc/env、jsb、自定义宏）；
 * 没有时回退本机 Creator 自带的引擎 cc.d.ts，并补一份 cc/env 最小声明。
 * 用法：node cocos-typecheck.mjs [--project <工程根>] [--include "assets/scripts/**\/*.ts"] [--strict]
 *   --strict  开启 TS strict（Creator 默认模板不是 strict，默认关闭以免模板代码误报）
 * 需要工程或全局可用的 typescript（npx tsc）。
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
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
const projectDecl = join(project, 'temp/declarations')
const dir = mkdtempSync(join(tmpdir(), 'cocos-typecheck-'))
let declarations
if (existsSync(join(projectDecl, 'cc.d.ts'))) {
  declarations = readdirSync(projectDecl).filter((f) => f.endsWith('.d.ts')).map((f) => join(projectDecl, f))
  console.log(`声明：${projectDecl}`)
} else {
  const engine = [
    process.env.COCOS_ENGINE_DTS,
    process.env.COCOS_CREATOR_BIN && declFrom(resolve(process.env.COCOS_CREATOR_BIN, '../../..')),
    wanted && declFrom(`/Applications/Cocos/Creator/${wanted}/CocosCreator.app`),
    declFrom('/Applications/CocosCreator.app'),
  ].filter(Boolean).find((p) => existsSync(p))
  if (!engine) {
    console.error('错误：找不到 Cocos 声明。用编辑器打开一次工程（生成 temp/declarations/），\n或配置：export COCOS_ENGINE_DTS=<cc.d.ts 路径> 或 COCOS_CREATOR_BIN=<CocosCreator 可执行文件>')
    process.exit(1)
  }
  // 引擎 cc.d.ts 不含 cc/env；补最小声明，覆盖常用宏
  const envStub = join(dir, 'cc-env-stub.d.ts')
  const macros = ['DEBUG', 'DEV', 'EDITOR', 'PREVIEW', 'BUILD', 'TEST', 'HTML5', 'NATIVE', 'MINIGAME', 'WECHAT', 'BYTEDANCE', 'RUNTIME_BASED']
  writeFileSync(envStub, `declare module 'cc/env' {\n${macros.map((m) => `  export const ${m}: boolean`).join('\n')}\n}\n`)
  declarations = [engine, envStub]
  console.log(`声明：${engine}（工程无 temp/declarations/，cc/env 用最小声明）`)
}

const tsconfig = join(dir, 'tsconfig.json')
writeFileSync(tsconfig, JSON.stringify({
  compilerOptions: {
    target: 'ES2019',
    module: 'ESNext',
    moduleResolution: 'bundler',
    strict: args.includes('--strict'),
    experimentalDecorators: true,
    noEmit: true,
    skipLibCheck: true,
    types: [],
  },
  files: declarations,
  include: [join(project, include)],
  exclude: [join(project, 'library'), join(project, 'temp'), join(project, 'build')],
}, null, 2))

const localTsc = join(project, 'node_modules/.bin/tsc')
const [cmd, cmdArgs] = existsSync(localTsc) ? [localTsc, ['-p', tsconfig]] : ['npx', ['-y', '-p', 'typescript', 'tsc', '-p', tsconfig]]
const run = spawnSync(cmd, cmdArgs, { stdio: 'inherit' })
if (run.status === 0) console.log('Cocos 脚本类型检查通过')
process.exit(run.status ?? 1)
