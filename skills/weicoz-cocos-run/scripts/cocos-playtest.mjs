#!/usr/bin/env node
/**
 * 一条命令跑浏览器试玩：(可选构建) → 起本地预览 → playwright-cli 打开手机尺寸 → 依次运行试玩脚本 →
 * 采样帧率 → 汇总通过与否、失败步骤、指标 → 拼关键截图联系图 → 关会话、停服务。
 *
 * 用法：node cocos-playtest.mjs --project <工程根> --script tests/e2e/playtest.mjs [--script ...]
 *        [--build] [--port <端口，默认自动取空闲端口>] [--shots "temp/playtest-*.png"] [--json]
 *   --build   先构建 web-mobile（默认用现有 build/web-mobile）
 *   --shots   截图 glob（相对工程根），拼成 temp/contact.png 供视觉巡检；默认 temp/playtest-*.png
 *             试玩结束后另开一个桌面上下文（1440×900、非移动、无触摸、桌面 Chrome UA）截
 *             temp/playtest-zz-desktop.png，拼在联系图末尾；手机上下文的 resize 只会得到被放大的手机画面
 * 试玩脚本约定：`async page => {...}`，返回 { pass, log: [{ step, ok, ... }], metrics? }；未按约定返回时报错会在错误信息里重述该格式。
 * 退出码：0 全部通过；1 有脚本失败或报错。依赖 playwright-cli；拼图依赖 ffmpeg（没有时跳过）。
 */
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createServer as createNetServer } from 'node:net'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []))
const flag = (name, fallback) => all(name)[0] ?? fallback
const project = resolve(flag('--project', process.cwd()))
const scripts = all('--script')
// 不传 --port 时取系统分配的空闲端口：多个代理并行验收时不会抢同一端口
const port = all('--port')[0] ? Number(all('--port')[0]) : await new Promise((ok) => {
  const srv = createNetServer().listen(0, '127.0.0.1', () => { const p = srv.address().port; srv.close(() => ok(p)) })
})
const shots = flag('--shots', 'temp/playtest-*.png')
const asJson = args.includes('--json')
const here = dirname(fileURLToPath(import.meta.url))
const session = `pt${port}`
if (!scripts.length) {
  console.error('错误：至少给一个 --script')
  process.exit(2)
}

const cli = (...a) => spawnSync('playwright-cli', [`-s=${session}`, ...a], { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

// 桌面截图用独立会话：手机上下文里 resize 只会把手机画面放大裁切，测不出桌面横屏的真实适配
const desktopSession = `${session}d`
const desktopConfig = join(tmpdir(), `playtest-desktop-${port}.json`)
const desktopCli = (...a) => spawnSync('playwright-cli', [`-s=${desktopSession}`, ...a], { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
const desktopShot = 'temp/playtest-zz-desktop.png'
// 桌面 Chrome UA：显式指定，避免宿主默认配置把 UA 或移动端标记带进来
const DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

if (args.includes('--build')) {
  const b = spawnSync(process.execPath, [join(here, 'cocos-build.mjs'), '--project', project, '--platform', 'web-mobile'], { stdio: 'inherit' })
  if (b.status !== 0) process.exit(1)
}

const server = spawn(process.execPath, [join(here, 'cocos-preview.mjs'), '--project', project, '--no-build', '--port', String(port)], { stdio: 'ignore' })
const url = `http://127.0.0.1:${port}/`
let up = false
for (let i = 0; i < 30 && !up; i++) {
  await wait(300)
  up = await fetch(url).then((r) => r.ok, () => false)
}
const results = []
let desktopShotError = null
try {
  if (!up) throw new Error(`预览服务 ${url} 没有起来`)
  cli('open', url)
  cli('resize', '390', '844')
  await wait(4000)
  // 帧率：页面内数 2 秒的 requestAnimationFrame，作为流畅度的替代指标
  const fpsOut = cli('eval', 'new Promise(r=>{let n=0;const t=performance.now();const f=()=>{n++;performance.now()-t<2000?requestAnimationFrame(f):r(Math.round(n/2))};requestAnimationFrame(f)})').stdout
  const fps = Number(fpsOut.match(/### Result\s*\n\s*(\d+)/)?.[1] ?? NaN)
  for (const s of scripts) {
    const started = Date.now()
    const out = cli('run-code', `--filename=${s}`)
    const text = `${out.stdout}\n${out.stderr}`
    const raw = text.match(/### Result\s*\n(.+)/)?.[1]
    let r
    try { r = JSON.parse(raw) } catch { r = null }
    if (!r || typeof r !== 'object' || typeof r.pass !== 'boolean') {
      // 拿不到结果时指明脚本该返回什么，否则只看到“失败”却不知改哪里
      const reason = text.match(/### Error\s*\n(.+)/)?.[1]
      r = { pass: false, error: ['没有拿到结果：试玩脚本须返回 { pass: boolean, log: [{ step, ok, ... }] }', reason && `原因：${reason}`].filter(Boolean).join('；').slice(0, 300) }
    }
    results.push({ script: s, seconds: Math.round((Date.now() - started) / 1000), fps, ...r })
  }
  // 桌面横屏截图（1440×900）：另开桌面上下文，竖屏游戏在宽窗口下是否居中留边只能这样看到；
  // 文件名排最后，进联系图末尾。失败只提示，不影响手机试玩的结果判定
  mkdirSync(join(project, 'temp'), { recursive: true })
  rmSync(join(project, desktopShot), { force: true }) // 上一轮的旧图不参与本轮判断
  writeFileSync(desktopConfig, JSON.stringify({
    browser: {
      contextOptions: {
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 1,
        isMobile: false,
        hasTouch: false,
        userAgent: DESKTOP_UA,
      },
    },
  }))
  desktopCli('open', url, `--config=${desktopConfig}`)
  // 等首页就绪：有 __game.screen() 就等它变 home（最多 12 秒），没有钩子或等不到就固定等 3 秒
  const probe = "(()=>{try{const g=window.__game;return g&&typeof g.screen==='function'&&String(g.screen())==='home'?1:0}catch(e){return 0}})()"
  let home = false
  for (let i = 0; i < 24 && !home; i++) {
    home = desktopCli('eval', probe).stdout.match(/### Result\s*\n\s*1\b/)?.[0] !== undefined
    if (!home) await wait(500)
  }
  if (!home) await wait(3000)
  desktopCli('screenshot', `--filename=${desktopShot}`)
  if (!existsSync(join(project, desktopShot))) desktopShotError = '桌面上下文没能截图，检查 playwright-cli 是否可启动桌面浏览器'
} catch (e) {
  results.push({ script: '(运行器)', pass: false, error: String(e.message ?? e) })
} finally {
  cli('close')
  desktopCli('close')
  rmSync(desktopConfig, { force: true })
  server.kill()
}

// 联系图：把匹配的截图按名字排序横向拼成一张，视觉巡检只看这一张
let contact = null
const [dirPart, pattern] = [dirname(shots), basename(shots)]
const dir = join(project, dirPart)
if (existsSync(dir) && spawnSync('ffmpeg', ['-version']).status === 0) {
  const re = new RegExp(`^${pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.')}$`)
  const files = readdirSync(dir).filter((f) => re.test(f) && f !== 'contact.png').sort().map((f) => join(dir, f))
    .filter((f) => statSync(f).mtimeMs > Date.now() - 30 * 60 * 1000) // 只拼本轮（30 分钟内）的截图
    .slice(0, 12)
  if (files.length) {
    mkdirSync(join(project, 'temp'), { recursive: true })
    contact = join(project, 'temp', 'contact.png')
    const inputs = files.flatMap((f) => ['-i', f])
    const scale = files.map((_, i) => `[${i}:v]scale=-2:640[v${i}]`).join(';')
    const stack = files.length > 1 ? `;${files.map((_, i) => `[v${i}]`).join('')}hstack=inputs=${files.length}` : ''
    const ff = spawnSync('ffmpeg', ['-loglevel', 'error', '-y', ...inputs, '-filter_complex', `${scale}${stack}`, ...(files.length > 1 ? [] : ['-map', '[v0]']), '-frames:v', '1', contact])
    if (ff.status !== 0) contact = null
  }
}

const pass = results.length > 0 && results.every((r) => r.pass === true)
if (asJson) {
  console.log(JSON.stringify({ pass, contact, results }, null, 2))
} else {
  for (const r of results) {
    const steps = r.log?.length ?? 0
    const failed = (r.log ?? []).filter((l) => !l.ok).map((l) => l.step ?? l.level)
    console.log(`${r.pass ? '✅' : '❌'} ${r.script}：${steps} 步，${r.seconds ?? '?'} 秒，帧率约 ${r.fps ?? '?'}`)
    if (failed.length) console.log(`   失败步骤：${failed.join('；')}`)
    if (r.error) console.log(`   错误：${r.error}`)
    if (r.metrics) console.log(`   指标：${JSON.stringify(r.metrics)}`)
  }
  console.log(contact ? `联系图（视觉巡检看这张）：${contact}` : '联系图：无匹配截图或缺 ffmpeg')
  if (desktopShotError) console.log(`⚠️ 桌面截图：${desktopShotError}`)
  console.log(pass ? '状态：核心循环已验证（浏览器）。' : '状态：失败。')
}
process.exit(pass ? 0 : 1)
