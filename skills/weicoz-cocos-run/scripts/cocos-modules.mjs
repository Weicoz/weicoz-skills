#!/usr/bin/env node
/**
 * 引擎模块裁剪检查：列出“项目设置 → 功能裁剪”中已启用、但工程里找不到使用痕迹的重型模块。
 * 用法：node cocos-modules.mjs [--project <工程根>]
 * 也被 cocos-build.mjs 调用。只读，不改设置。
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// 模块 → 使用痕迹（TS 代码与 .scene/.prefab 序列化类型名都会命中）与可识别的资源扩展名
const HEAVY = {
  'spine-3.8': { use: /\bsp\.Skeleton\b/, ext: ['.skel'] },
  'dragon-bones': { use: /\bdragonBones\.\w+/, ext: ['.dbbin'] },
  'tiled-map': { use: /\bTiledMap\b/, ext: ['.tmx'] },
  'physics-2d-box2d': { use: /\b(RigidBody2D|\w*Collider2D|PhysicsSystem2D)\b/ },
  'physics-2d-builtin': { use: /\b(\w*Collider2D|PhysicsSystem2D)\b/ },
  'video': { use: /\bVideoPlayer\b/ },
  'webview': { use: /\bWebView\b/ },
  'particle-2d': { use: /\bParticleSystem2D\b/, ext: ['.plist'] },
  '3d': { use: /\b(MeshRenderer|SkinnedMeshRenderer)\b/, ext: ['.fbx', '.gltf', '.glb'] },
}

export function unusedModules(project) {
  const settings = join(project, 'settings/v2/packages/engine.json')
  if (!existsSync(settings)) return { included: [], unused: [] }
  const modules = JSON.parse(readFileSync(settings, 'utf8')).modules ?? {}
  const config = modules.configs?.[modules.globalConfigKey ?? 'defaultConfig'] ?? {}
  const included = config.includeModules ?? []

  const texts = []
  const exts = new Set()
  const walk = (dir) => {
    for (const f of readdirSync(dir)) {
      const p = join(dir, f)
      if (statSync(p).isDirectory()) { walk(p); continue }
      const e = extname(f).toLowerCase()
      exts.add(e)
      if (['.ts', '.js', '.scene', '.prefab'].includes(e)) texts.push(readFileSync(p, 'utf8'))
    }
  }
  if (existsSync(join(project, 'assets'))) walk(join(project, 'assets'))
  const corpus = texts.join('\n')

  const unused = included.filter((m) => HEAVY[m] && !HEAVY[m].use.test(corpus) && !(HEAVY[m].ext ?? []).some((e) => exts.has(e)))
  return { included, unused }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  const i = args.indexOf('--project')
  const project = resolve(i >= 0 ? args[i + 1] : process.cwd())
  const { included, unused } = unusedModules(project)
  console.log(`已启用模块（${included.length}）：${included.join(', ') || '未读到 settings/v2/packages/engine.json'}`)
  console.log(unused.length
    ? `⚠️ 已启用但未发现使用：${unused.join(', ')}\n   → 编辑器“项目设置 → 功能裁剪”中关闭，重新构建后对比包体`
    : '✅ 未发现可裁剪的重型模块')
}
