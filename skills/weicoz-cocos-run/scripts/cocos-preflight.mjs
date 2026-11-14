#!/usr/bin/env node
/**
 * Cocos 工程开工前检查：Creator 版本、编辑器绑定的工程、funplay-cocos MCP 端口与工具档、预览端口。
 * 用法：node cocos-preflight.mjs [--project <工程根>] [--json]
 * 退出码：0 = 无阻塞项；1 = 有阻塞项（❌）。
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { connect } from 'node:net'
import { dirname, join, resolve } from 'node:path'

const args = process.argv.slice(2)
const flag = (name) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : undefined
}
const project = resolve(flag('--project') ?? process.cwd())
const asJson = args.includes('--json')
const checks = []
const add = (level, item, detail, fix) => checks.push({ level, item, detail, fix })

const readJson = (p) => {
  try { return JSON.parse(readFileSync(p, 'utf8')) } catch { return null }
}

const portOpen = (port, host = '127.0.0.1') =>
  new Promise((done) => {
    const socket = connect({ port, host })
    const finish = (ok) => { socket.destroy(); done(ok) }
    socket.setTimeout(800, () => finish(false))
    socket.once('connect', () => finish(true))
    socket.once('error', () => finish(false))
  })

// 1. 工程与期望版本
const pkg = readJson(join(project, 'package.json'))
const wanted = pkg?.creator?.version
if (!existsSync(join(project, 'assets'))) {
  add('fail', '工程', `${project} 下没有 assets/`, '用 --project 指向 Cocos 工程根目录')
} else {
  add('ok', '工程', `${project}（package.json creator.version=${wanted ?? '未写'}）`)
}

// 2. Creator 可执行文件：环境变量优先，其次 macOS 标准安装位置
const creatorCandidates = (version) => [
  process.env.COCOS_CREATOR_BIN,
  version && `/Applications/Cocos/Creator/${version}/CocosCreator.app/Contents/MacOS/CocosCreator`,
  '/Applications/CocosCreator.app/Contents/MacOS/CocosCreator',
].filter(Boolean)
const creator = creatorCandidates(wanted).find((p) => existsSync(p))
if (!creator) {
  add('fail', 'Creator', '找不到 CocosCreator 可执行文件', 'export COCOS_CREATOR_BIN=<CocosCreator 可执行文件路径>')
} else {
  let installed = 'unknown'
  try {
    const plist = join(creator, '../../Info.plist')
    installed = execFileSync('plutil', ['-extract', 'CFBundleShortVersionString', 'raw', plist], { encoding: 'utf8' }).trim()
  } catch { /* 非 macOS 或无 plist：版本未知 */ }
  const same = !wanted || installed === 'unknown' || installed === wanted
  add(same ? 'ok' : 'warn', 'Creator', `${creator}（${installed}）`, same ? undefined : `工程要求 ${wanted}，与安装版本不一致`)
}

// 3. 正在运行的编辑器绑定了哪些工程
let openProjects = []
try {
  const ps = execFileSync('ps', ['-axo', 'command'], { encoding: 'utf8' })
  // 只认可执行文件本身是 CocosCreator 的进程；shortcut: 工程路径含空格时截断，遇到再改用 lsof
  openProjects = [...ps.matchAll(/^\S*\/CocosCreator --project (\S+)/gm)].map((m) => resolve(m[1]))
  openProjects = [...new Set(openProjects)]
} catch { /* ps 不可用时跳过 */ }
const editorOnThis = openProjects.includes(project)
const others = openProjects.filter((p) => p !== project)
if (editorOnThis) add('ok', '编辑器', '当前工程已在编辑器中打开')
else add('warn', '编辑器', '当前工程未在编辑器中打开；MCP 与编辑器预览不可用', `"${creator ?? 'CocosCreator'}" --project "${project}" 或让用户在 Dashboard 打开`)
if (others.length) {
  add(editorOnThis ? 'warn' : 'fail', '编辑器', `另有工程占用编辑器：${others.join(', ')}`, '关闭其他工程的编辑器，否则 MCP 固定端口会连到错误工程')
}

// 4. funplay-cocos MCP：扩展、项目 skill、端口与工具档
const home = process.env.HOME ?? ''
const extDirs = [join(project, 'extensions/funplay-cocos-mcp'), wanted && join(home, '.CocosCreator/builtin-extensions', wanted, 'funplay-cocos-mcp')].filter(Boolean)
const ext = extDirs.find((d) => existsSync(join(d, 'package.json')))
if (ext) add('ok', 'funplay 扩展', `${ext}（${readJson(join(ext, 'package.json'))?.version ?? '?'}）`)
else add('fail', 'funplay 扩展', '未找到 funplay-cocos-mcp 扩展', '按 https://github.com/FunplayAI/funplay-cocos-mcp 安装到 ~/.CocosCreator/builtin-extensions/<Creator 版本>/')
// funplay 的 Kimi Code / DSH 等目录装在最近的 Git 根；monorepo 时 Git 根与工程根不同
const gitRoot = (() => {
  for (let d = project; ; d = dirname(d)) {
    if (existsSync(join(d, '.git'))) return d
    if (dirname(d) === d) return null
  }
})()
const skillRoots = ['.claude/skills', '.agents/skills', '.dsh/skills', '.kimi-code/skills']
const skillBases = [...new Set([project, gitRoot].filter(Boolean))]
const projectSkills = skillBases.flatMap((base) => skillRoots.map((r) => join(base, r)))
  .filter((d) => existsSync(join(d, 'funplay-cocos-mcp-workflow', 'SKILL.md')))
if (projectSkills.length) add('ok', 'funplay 项目 skill', `已装于 ${projectSkills.join(', ')}`)
else add('warn', 'funplay 项目 skill', `工程与 Git 根（${gitRoot ?? '无'}）内都未安装 funplay-cocos-mcp-workflow / funplay-cocos-ui-composition`, '编辑器 Funplay > MCP Server 选当前客户端，点 Configure + Skills')

// 工具档：按扩展 docs/TOOLS.md 复现 funplay 的暴露规则（core 集 + enabledTools/Categories - disabled*）
const mcpConfig = readJson(join(project, 'funplay-cocos-mcp.config.json')) ?? {}
const mcpPort = Number(process.env.COCOS_MCP_PORT ?? mcpConfig.port ?? 0)
const profile = process.env.COCOS_MCP_PROFILE ?? mcpConfig.toolProfile ?? 'core'
const profileSrc = process.env.COCOS_MCP_PROFILE ? '（来自本 shell 环境变量；编辑器以其启动环境为准）' : ''
const toolsDoc = ext && existsSync(join(ext, 'docs/TOOLS.md')) ? readFileSync(join(ext, 'docs/TOOLS.md'), 'utf8') : ''
const catalog = new Map() // 工具名 -> 分类（小写）
let category = ''
for (const line of toolsDoc.split('\n')) {
  const h = line.match(/^### (.+)/)
  if (h) category = h[1].trim().toLowerCase()
  const t = line.match(/^\| `([a-z0-9_]+)`/)
  if (t && category) catalog.set(t[1], category)
}
const coreLine = toolsDoc.split('## Core Tools')[1]?.split('\n').find((l) => l.includes('`')) ?? ''
const core = new Set([...coreLine.matchAll(/`([a-z0-9_]+)`/g)].map((m) => m[1]))
const lower = (xs) => new Set((xs ?? []).map((x) => String(x).toLowerCase()))
const exposed = (tool) => {
  const cat = catalog.get(tool)
  if (mcpConfig.disabledTools?.includes(tool) || lower(mcpConfig.disabledToolCategories).has(cat)) return false
  return profile === 'full' || core.has(tool) || mcpConfig.enabledTools?.includes(tool) || lower(mcpConfig.enabledToolCategories).has(cat)
}
const needs = {
  '预览/试玩': ['run_project_preview', 'set_preview_mode', 'capture_game_screenshot', 'simulate_preview_input'],
  '搭场景/UI': ['create_node', 'set_node_transform', 'add_component', 'set_component_property', 'instantiate_prefab', 'create_prefab_from_node', 'save_current_scene'],
}
if (!catalog.size) {
  add('warn', 'MCP 工具档', `toolProfile=${profile}${profileSrc}；读不到扩展 docs/TOOLS.md，无法核对工具`)
} else {
  const gaps = Object.entries(needs).map(([use, tools]) => [use, tools.filter((t) => !exposed(t))]).filter(([, m]) => m.length)
  if (gaps.length) {
    add('warn', 'MCP 工具档', `toolProfile=${profile}${profileSrc}；缺 ${gaps.map(([u, m]) => `${u}：${m.join(', ')}`).join('；')}`,
      '在 funplay-cocos-mcp.config.json 加 "enabledToolCategories": ["build","input","screenshots","scene","components","prefabs","ui"]，然后 Funplay > MCP Server 点 Restart')
  } else {
    add('ok', 'MCP 工具档', `toolProfile=${profile}${profileSrc}，预览与搭场景工具齐全`)
  }
}
const mcpUp = mcpPort > 0 && await portOpen(mcpPort)
if (mcpUp && editorOnThis && !others.length) add('ok', 'MCP 端口', `127.0.0.1:${mcpPort} 可连接`)
else if (mcpUp) add('warn', 'MCP 端口', `127.0.0.1:${mcpPort} 可连接，但可能属于其他工程`, '调用 get_project_info 核对 project_path')
else if (!mcpPort) add('warn', 'MCP 端口', '工程未固定端口（funplay 按工程路径分配）', '调用 get_project_info，或看 Funplay > MCP Server 面板里的 URL')
else add('warn', 'MCP 端口', `127.0.0.1:${mcpPort} 无监听`, '打开当前工程的编辑器，确认 Funplay > MCP Server 已启动；不可用时走 CLI 路径')

// 5. 编辑器浏览器预览端口
const previewPort = Number(process.env.COCOS_PREVIEW_PORT ?? 7456)
const previewUp = await portOpen(previewPort)
add(previewUp ? 'ok' : 'warn', '预览端口', `127.0.0.1:${previewPort} ${previewUp ? '可连接' : '无监听'}`, previewUp ? undefined : '编辑器内点击预览，或调用 run_project_preview(mode="browser")')

const blocked = checks.some((c) => c.level === 'fail')
if (asJson) {
  console.log(JSON.stringify({ project, blocked, checks }, null, 2))
} else {
  const icon = { ok: '✅', warn: '⚠️ ', fail: '❌' }
  for (const c of checks) {
    console.log(`${icon[c.level]} ${c.item}：${c.detail}`)
    if (c.fix) console.log(`   → ${c.fix}`)
  }
  console.log(blocked ? '\n结论：有阻塞项，先处理 ❌。' : '\n结论：无阻塞项。⚠️ 项决定可用路径（MCP 或 CLI）。')
}
process.exit(blocked ? 1 : 0)
