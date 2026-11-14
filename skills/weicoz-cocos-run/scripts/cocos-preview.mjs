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
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname)
  const file = normalize(join(root, path.endsWith('/') ? `${path}index.html` : path))
  // 只服务构建目录内的文件
  if (!file.startsWith(root + sep) || !existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404).end('not found')
    return
  }
  res.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' })
  createReadStream(file).pipe(res)
})

server.on('error', (e) => {
  console.error(e.code === 'EADDRINUSE' ? `错误：端口 ${port} 已占用，换 --port` : `错误：${e.message}`)
  process.exit(1)
})
server.listen(port, lan ? '0.0.0.0' : '127.0.0.1', () => {
  const url = `http://127.0.0.1:${port}/`
  console.log(`预览：${url}`)
  if (lan) {
    const ips = Object.values(networkInterfaces()).flat().filter((n) => n?.family === 'IPv4' && !n.internal).map((n) => n.address)
    for (const ip of ips) console.log(`手机（同一 Wi-Fi）：http://${ip}:${port}/`)
  }
  if (args.includes('--open')) spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { stdio: 'ignore', detached: true }).unref()
})
