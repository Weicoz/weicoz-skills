#!/usr/bin/env node
// Web 适配器：命令检查 + 浏览器流程 + 联系图，输出 weicoz-verify 第 2 节的结论行。
// 用法：node web-verify.mjs --project <目录> [--quick] [--base-url <URL>] [--script <路径> ...] [--no-start] [--env-file <路径>]
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import {
  parseArgs, mergeConfig, matchIgnore, verdict, parseEnvFile, expandHome, loadLine, tailLines, failureLines, safeName,
} from './lib.mjs';

const items = [];
const say = (s) => console.log(s);
const record = (status, name, line, extra = {}) => {
  items.push({ status, name, ...extra });
  say(line);
};
const finish = () => {
  const v = verdict(items);
  say(v.line);
  process.exit(v.code);
};

let args;
try {
  args = parseArgs(process.argv.slice(2));
} catch (e) {
  console.error(`参数错误：${e.message}\n用法：node web-verify.mjs --project <目录> [--quick] [--base-url <URL>] [--script <路径> ...] [--no-start] [--env-file <路径>]`);
  console.log('结论：未验证（缺：有效参数）');
  process.exit(3);
}

const project = path.resolve(expandHome(args.project));
const cfgPath = path.join(project, 'tests/e2e/web-verify.config.json');
let userCfg = {};
if (fs.existsSync(cfgPath)) {
  try {
    userCfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
  } catch (e) {
    say(`❌ 配置解析失败：${cfgPath}：${e.message}`);
    items.push({ status: 'fail', name: '配置文件' });
    finish();
  }
}
const cfg = mergeConfig(userCfg, args);
const tier = args.quick ? 'quick' : 'full';
const outDir = path.join(project, 'temp/web-verify');

say(loadLine());
say(`档位：${args.quick ? '快检' : '全检'}，项目：${project}，地址：${cfg.baseUrl}`);

// 环境文件：只读入内存供子进程和流程使用，不打印、不落盘。
const envFile = args.envFile || process.env.WEB_VERIFY_ENV_FILE || cfg.start?.envFile;
const fileEnv = {};
if (envFile) {
  const p = path.resolve(expandHome(envFile));
  if (fs.existsSync(p)) Object.assign(fileEnv, parseEnvFile(fs.readFileSync(p, 'utf8')));
  else say(`⚠️ 环境文件不存在：${p}`);
}
for (const [k, v] of Object.entries(fileEnv)) if (process.env[k] === undefined) process.env[k] = v;

// 1. 命令检查
for (const c of cfg.checks[tier] || []) {
  const r = spawnSync(c.cmd, { shell: true, cwd: project, encoding: 'utf8', timeout: (c.timeoutSec || 600) * 1000 });
  if (r.status === 0) record('pass', c.name, `✅ ${c.name}（${c.cmd}）`);
  else {
    const why = r.error ? String(r.error.message) : failureLines(`${r.stdout || ''}\n${r.stderr || ''}`, 5);
    record('fail', c.name, `❌ ${c.name}（${c.cmd}）退出码 ${r.status ?? r.signal}\n${why.replace(/^/gm, '    ')}`);
  }
}

// 2. 选流程
function listFlows() {
  if (args.scripts.length) return args.scripts.map((s) => path.resolve(project, expandHome(s)));
  const pattern = path.resolve(project, cfg.flows);
  const dir = path.dirname(pattern);
  if (!fs.existsSync(dir)) return [];
  const re = new RegExp('^' + path.basename(pattern).split('*').map((x) => x.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
  let files = fs.readdirSync(dir).filter((f) => re.test(f)).sort().map((f) => path.join(dir, f));
  if (args.quick) files = files.filter((f) => cfg.quickFlows.includes(path.basename(f).replace(/\.flow\.mjs$/, '').replace(/\.mjs$/, '')));
  return files;
}
const flows = listFlows();
if (flows.length === 0) {
  say(`⚠️ 没有可跑的流程（${args.quick ? 'quick 流程未配置或不匹配' : cfg.flows}）`);
  if (!args.scripts.length) items.push({ status: 'unverified', name: 'e2e 流程', missing: 'e2e 流程脚本' });
  finish();
}

// 3. 解析 Playwright：项目 -> 全局
function loadPlaywright() {
  const tryReq = (req) => {
    for (const id of ['playwright', '@playwright/test', 'playwright-core']) {
      try {
        const m = req(id);
        if (m?.chromium) return m;
      } catch { /* 下一个候选 */ }
    }
    return null;
  };
  const fromProject = tryReq(createRequire(path.join(project, 'package.json')));
  if (fromProject) return fromProject;
  const g = spawnSync('npm', ['root', '-g'], { encoding: 'utf8' });
  const root = g.status === 0 ? g.stdout.trim() : '';
  if (!root) return null;
  const bases = [root];
  const scoped = path.join(root, '@playwright');
  if (fs.existsSync(scoped)) for (const d of fs.readdirSync(scoped)) bases.push(path.join(scoped, d, 'node_modules'));
  for (const b of bases) {
    const m = tryReq(createRequire(path.join(b, 'noop.js')));
    if (m) return m;
  }
  return null;
}
const pw = loadPlaywright();
if (!pw) {
  say('⚠️ 找不到 Playwright。在项目里 `pnpm add -D playwright`（或 npm i -D playwright），或全局安装 playwright，再 `npx playwright install chromium`。');
  record('unverified', 'e2e 流程', '⚠️ e2e 流程未验证', { missing: 'playwright' });
  finish();
}

// 4. 服务
async function isUp(url) {
  try {
    const r = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
    return r.status < 500;
  } catch {
    return false;
  }
}
const readyUrl = cfg.baseUrl + (cfg.start?.readyPath || '/');
let child = null;
let serverLog = ''; // 只留末尾，失败时给线索
function stopChild() {
  if (!child) return;
  try { process.kill(-child.pid, 'SIGTERM'); } catch { /* 已退出 */ }
  child = null;
}
process.on('SIGINT', () => { stopChild(); process.exit(130); });
process.on('SIGTERM', () => { stopChild(); process.exit(143); });

let serverOk = await isUp(readyUrl);
if (serverOk) say(`✅ 服务已在运行：${readyUrl}（不由脚本管理）`);
else if (cfg.start?.command) {
  say(`… 启动服务：${cfg.start.command}`);
  child = spawn(cfg.start.command, { shell: true, cwd: project, detached: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ...fileEnv } });
  for (const st of [child.stdout, child.stderr]) st.on('data', (d) => { serverLog = (serverLog + d).slice(-4000); });
  const deadline = Date.now() + (cfg.start.timeoutSec || 120) * 1000;
  while (Date.now() < deadline && child.exitCode === null) {
    if (await isUp(readyUrl)) { serverOk = true; break; }
    await new Promise((r) => setTimeout(r, 1000));
  }
  if (serverOk) say(`✅ 服务就绪：${readyUrl}`);
  else {
    say(`❌ 服务未就绪（${child.exitCode === null ? `${cfg.start.timeoutSec || 120} 秒超时` : `进程已退出 ${child.exitCode}`}）：${readyUrl}\n${tailLines(serverLog.replace(/\x1b\[[0-9;]*m/g, ''), 8).replace(/^/gm, '    ')}`);
    stopChild();
  }
}
if (!serverOk) {
  record('unverified', 'e2e 流程', `⚠️ e2e 流程未验证：服务未运行（${readyUrl}）`, { missing: `服务 ${cfg.baseUrl}` });
  finish();
}

// 5. 跑流程
fs.mkdirSync(outDir, { recursive: true });
const shots = [];
// Playwright 自带的 chromium 缺失时，退到本机 Chrome。
async function launch() {
  try {
    return await pw.chromium.launch({ headless: true });
  } catch (e) {
    try {
      return await pw.chromium.launch({ headless: true, channel: 'chrome' });
    } catch {
      throw e;
    }
  }
}
let browser;
try {
  browser = await launch();
} catch (e) {
  stopChild();
  say(`⚠️ 浏览器启动失败：${String(e.message).split('\n')[0]}。试 \`npx playwright install chromium\`。`);
  record('unverified', 'e2e 流程', '⚠️ e2e 流程未验证', { missing: 'chromium 浏览器' });
  finish();
}

for (const file of flows) {
  const flowName = path.basename(file).replace(/\.flow\.mjs$/, '').replace(/\.mjs$/, '');
  let fn;
  try {
    fn = (await import(pathToFileURL(file).href)).default;
    if (typeof fn !== 'function') throw new Error('未默认导出函数');
  } catch (e) {
    record('fail', flowName, `❌ ${flowName} 加载失败：${e.message}`);
    continue;
  }
  for (const vp of cfg.viewports) {
    const label = `${flowName}@${vp.name}`;
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await ctx.newPage();
    const origin = new URL(cfg.baseUrl).origin;
    const problems = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && !matchIgnore(m.text(), cfg.ignore.console)) problems.push(`控制台 error：${m.text().slice(0, 200)}`);
    });
    page.on('pageerror', (e) => {
      if (!matchIgnore(String(e.message), cfg.ignore.pageerror)) problems.push(`未捕获异常：${String(e.message).slice(0, 200)}`);
    });
    page.on('response', (r) => {
      const u = r.url();
      if (r.status() < 400 || !u.startsWith(origin)) return;
      const line = `${r.request().method()} ${r.status()} ${u}`;
      if (!matchIgnore(line, cfg.ignore.requests)) problems.push(`请求失败：${line.slice(0, 200)}`);
    });
    const stepLines = [];
    let stepFailed = false;
    const shot = async (name) => {
      const f = path.join(outDir, `${safeName(flowName)}-${vp.name}-${safeName(name)}.png`);
      await page.screenshot({ path: f });
      shots.push(f);
      return f;
    };
    const step = async (name, f) => {
      try {
        await f();
        stepLines.push(`    ✅ ${name}`);
      } catch (e) {
        if (e.unverified) {
          stepLines.push(`    ⚠️ ${name}：缺 ${e.unverified}`);
          throw e;
        }
        stepFailed = true;
        stepLines.push(`    ❌ ${name}：${String(e.message).split('\n')[0].slice(0, 200)}`);
        throw e;
      }
    };
    let unverifiedWhy = null;
    const unverified = (missing) => {
      throw Object.assign(new Error(`未验证：缺 ${missing}`), { unverified: missing });
    };
    try {
      await fn({ page, baseUrl: cfg.baseUrl, step, shot, viewport: vp, unverified });
    } catch (e) {
      if (e.unverified) { unverifiedWhy = e.unverified; stepFailed = false; }
      else if (!stepFailed) stepLines.push(`    ❌ 流程异常：${String(e.message).split('\n')[0].slice(0, 200)}`);
      stepFailed = true;
    }
    try { await shot('end'); } catch { /* 页面已关闭 */ }
    await ctx.close();
    if (unverifiedWhy && !stepFailed) record('unverified', label, `⚠️ ${label} 未验证：缺 ${unverifiedWhy}\n${stepLines.join('\n')}`, { missing: unverifiedWhy });
    else if (!stepFailed && problems.length === 0) record('pass', label, `✅ ${label}\n${stepLines.join('\n')}`);
    else {
      const uniq = [...new Set(problems)].slice(0, 8);
      record('fail', label, `❌ ${label}\n${[...stepLines, ...uniq.map((p) => `    ❌ ${p}`)].join('\n')}`);
    }
  }
}
await browser.close();
stopChild();

// 6. 联系图
if (shots.length) {
  const sorted = [...shots].sort((a, b) => path.basename(a).localeCompare(path.basename(b)));
  const html = `<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:12px;background:#eee;font:12px sans-serif}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px}
figure{margin:0;background:#fff;padding:6px;border:1px solid #ccc}img{width:100%;display:block}</style>
<div class="g">${sorted.map((f) => `<figure><figcaption>${path.basename(f)}</figcaption><img src="${encodeURI(path.basename(f))}"></figure>`).join('')}</div>`;
  const htmlPath = path.join(outDir, 'contact.html');
  fs.writeFileSync(htmlPath, html);
  const contact = path.join(outDir, 'contact.png');
  try {
    const b2 = await launch();
    const p2 = await b2.newPage({ viewport: { width: 1500, height: 900 } });
    await p2.goto(pathToFileURL(htmlPath).href);
    await p2.waitForLoadState('load');
    await p2.screenshot({ path: contact, fullPage: true });
    await b2.close();
    say(`视觉巡检：看 ${contact}，按 weicoz-verify references/visual-checklist.md`);
  } catch (e) {
    say(`⚠️ 联系图生成失败：${String(e.message).split('\n')[0]}`);
    items.push({ status: 'unverified', name: '联系图', missing: '联系图' });
  }
}
finish();
