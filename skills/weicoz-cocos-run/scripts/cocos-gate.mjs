#!/usr/bin/env node
/**
 * 兼容封装：转调通用门 weicoz-verify/scripts/verify-gate.mjs，参数原样透传。
 * 用法：node cocos-gate.mjs --project <工程> [--base <分支>] [--build <产物目录>[:<平台>]]... [--allow-debug]
 */
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const gate = join(dirname(fileURLToPath(import.meta.url)), '../../weicoz-verify/scripts/verify-gate.mjs')
const r = spawnSync(process.execPath, [gate, ...process.argv.slice(2)], { stdio: 'inherit' })
process.exit(r.status ?? 1)
