#!/usr/bin/env node
/**
 * 一键给用户预览：构建 web-mobile → 起静态服务 → 输出可点开的 URL。
 * 用法：node cocos-preview.mjs [--project <工程根>] [--port 8123] [--no-build] [--open] [--lan]
 *   --no-build  直接服务现有 build/web-mobile
 *   --open      用系统浏览器打开
 *   --lan       监听局域网，供同一 Wi-Fi 下的手机打开（会对局域网暴露该目录，用完即停）
 * 前台常驻；Ctrl+C 停止。代理调用时放后台运行。
 */
import { spawnSync, spawn } from 'node:child_process'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import { networkInterfaces } from 'node:os'
import { dirname, extname, join, normalize, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : fallback
}
const project = resolve(flag('--project', process.cwd()))
const port = Number(flag('--port', 8123))
const lan = args.includes('--lan')
const root = join(project, 'build', 'web-mobile')

if (!args.includes('--no-build')) {
  const build = join(dirname(fileURLToPath(import.meta.url)), 'cocos-build.mjs')
  const run = spawnSync(process.execPath, [build, '--project', project, '--platform', 'web-mobile'], { stdio: 'inherit' })
  if (run.status !== 0) process.exit(run.status ?? 1)
}
if (!existsSync(join(root, 'index.html'))) {
  console.error(`错误：${root} 没有 index.html。去掉 --no-build 先构建。`)
  process.exit(1)
}

const types = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.wasm': 'application/wasm', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.ttf': 'font/ttf',
}
const server = createServer((req, res) => {
  let file
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname)
    file = normalize(join(root, path.endsWith('/') ? `${path}index.html` : path))
  } catch {
    res.writeHead(400).end('bad request') // 畸形 URL（如 %E0%A4%A）不得打掉服务
    return
  }
  // 只服务构建目录内的文件
  if (!file.startsWith(root + sep) || file.includes('\0') || !existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404).end('not found')
    return
  }
  res.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' })
  createReadStream(file).on('error', () => res.destroy()).pipe(res)
})

server.on('error', (e) => {
  console.error(e.code === 'EADDRINUSE' ? `错误：端口 ${port} 已占用，换 --port` : `错误：${e.message}`)
  process.exit(1)
})
server.listen(port, lan ? '0.0.0.0' : '127.0.0.1', async () => {
  const url = `http://127.0.0.1:${port}/`
  console.log(`预览：${url}`)
  if (lan) {
    // 默认路由网卡排第一；VPN/TUN/组网（utun、198.18.x 代理假 IP 等）标出来，免得给错地址
    let primary = ''
    try {
      const out = spawnSync(process.platform === 'darwin' ? 'route' : 'ip', process.platform === 'darwin' ? ['-n', 'get', 'default'] : ['route', 'show', 'default'], { encoding: 'utf8' }).stdout ?? ''
      primary = out.match(/interface: (\S+)/)?.[1] ?? out.match(/ dev (\S+)/)?.[1] ?? ''
    } catch { /* 取不到默认路由时只按顺序列出 */ }
    const nics = Object.entries(networkInterfaces()).flatMap(([name, list]) =>
      (list ?? []).filter((n) => n.family === 'IPv4' && !n.internal).map((n) => ({ name, ip: n.address })))
    // 198.18.x 是代理 TUN 的假 IP，手机连不上；utun/feth/tailscale/zt 上的 10.x、100.64～127.x 多是组网（EasyTier、Tailscale、ZeroTier）
    const fake = (n) => n.ip.startsWith('198.18.') || /^(bridge|vmnet|docker|veth)/.test(n.name)
    const overlay = (n) => !fake(n) && /^(utun|tun|tap|feth|zt|tailscale)/.test(n.name)
    const rank = (n) => (n.name === primary ? 0 : overlay(n) ? 1 : fake(n) ? 3 : 2)
    nics.sort((a, b) => rank(a) - rank(b))
    for (const n of nics) {
      // 本机自测每个地址，不通的不要发给用户
      const ok = await fetch(`http://${n.ip}:${port}/`, { signal: AbortSignal.timeout(1500) }).then((r) => r.ok, () => false)
      const tag = n.name === primary ? '（默认网卡，同一 Wi-Fi 用这个）' : overlay(n) ? '（组网：手机加入同一 EasyTier/Tailscale 网络后可用）' : fake(n) ? '（代理或容器假地址，手机连不上）' : ''
      console.log(`${ok ? '✅' : '❌'} 手机：http://${n.ip}:${port}/  ${n.name}${tag}${ok ? '' : '（本机访问不通，不要用）'}`)
    }
    console.log('网络切换后地址会变：重跑本命令取新地址。')
  }
  if (args.includes('--open')) spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { stdio: 'ignore', detached: true }).unref()
})
