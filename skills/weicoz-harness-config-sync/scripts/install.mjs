#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const [baseArg] = process.argv.slice(2);
if (!baseArg) throw new Error('提供已解包目录；其中必须有 manifest.json 和 payload/');
const base = path.resolve(baseArg);
const home = os.homedir();
const manifest = JSON.parse(fs.readFileSync(path.join(base, 'manifest.json')));
assert.equal(manifest.target_home.toLowerCase(), home.replaceAll('\\', '/').toLowerCase(), '目标用户目录不匹配');
assert.equal(manifest.includes_personal_history, false);
const deny = new Set(['.ssh', 'sessions', 'memories', 'memories_v2', 'generated_images', 'attachments', 'automations']);
function safe(root, rel) {
  assert(!rel.includes('\\') && !rel.includes(':') && !path.isAbsolute(rel));
  assert(!rel.split('/').some(p => p === '..' || deny.has(p)), '拒绝个人数据或越界路径');
  const p = path.resolve(root, rel);
  assert(p.startsWith(root + path.sep));
  return p;
}
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
for (const [rel, item] of Object.entries(manifest.files)) {
  const src = safe(path.join(base, 'payload'), rel);
  assert.equal(fs.lstatSync(src).isSymbolicLink(), false);
  assert.equal(hash(src), item.sha256, `包哈希错误: ${rel}`);
}
for (const [rel, target] of Object.entries(manifest.links)) {
  safe(home, rel); safe(home, target);
}
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const backup = path.join(home, '.local', 'state', 'harness-config-sync-backups', stamp);
fs.mkdirSync(backup, { recursive: true, mode: 0o700 });
const saved = new Set();
const preservedShellExports = {};
function preserve(dst, rel) {
  if (saved.has(dst)) return;
  saved.add(dst);
  let stat;
  try { stat = fs.lstatSync(dst); } catch (e) { if (e.code === 'ENOENT') return; throw e; }
  const target = safe(backup, rel);
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o700 });
  if (stat.isSymbolicLink()) {
    fs.writeFileSync(target + '.original-link.json', JSON.stringify({ link: fs.readlinkSync(dst) }), { mode: 0o600 });
  } else {
    fs.cpSync(dst, target, { recursive: stat.isDirectory(), verbatimSymlinks: true, preserveTimestamps: true });
  }
}
function parents(dst) {
  const rel = path.relative(home, path.dirname(dst));
  let cursor = home;
  for (const part of rel.split(path.sep).filter(Boolean)) {
    cursor = path.join(cursor, part);
    try { assert(!fs.lstatSync(cursor).isSymbolicLink(), '父目录是链接；先核对实际配置入口'); }
    catch (e) { if (e.code !== 'ENOENT') throw e; fs.mkdirSync(cursor, { mode: 0o700 }); }
  }
}
for (const [rel, item] of Object.entries(manifest.files)) {
  const dst = safe(home, rel);
  parents(dst); preserve(dst, rel);
  let merged;
  if (/^\.zsh(?:env|rc|profile)$/.test(rel) && fs.existsSync(dst)) {
    const exports = fs.readFileSync(dst, 'utf8').split(/\r?\n/).filter(line => {
      const match = line.match(/^\s*export\s+(\w+)\s*=/);
      return match && /^(?:PATH|.*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PROXY|BASE_URL|ENDPOINT|API_TIMEOUT).*)$/i.test(match[1]);
    });
    if (exports.length) {
      merged = fs.readFileSync(safe(path.join(base, 'payload'), rel), 'utf8') +
        '\n# 保留目标已有 PATH、代理及凭据导出\n' + exports.join('\n') +
        '\nexport PATH="$HOME/.local/bin:$PATH"\n';
      const check = spawnSync('zsh', ['-n'], { input: merged, encoding: 'utf8' });
      assert.equal(check.status, 0, '目标 Shell 导出包含复杂多行语法；保留原文件，改用人工合并');
      preservedShellExports[rel] = exports.map(line => line.match(/^\s*export\s+(\w+)/)[1]);
    }
  }
  try { if (fs.lstatSync(dst).isSymbolicLink()) fs.unlinkSync(dst); }
  catch (e) { if (e.code !== 'ENOENT') throw e; }
  if (merged !== undefined) fs.writeFileSync(dst, merged);
  else fs.copyFileSync(safe(path.join(base, 'payload'), rel), dst);
  if (process.platform !== 'win32') fs.chmodSync(dst, /^\.zsh(?:env|rc|profile)$/.test(rel) ? 0o600 : item.mode);
  assert.equal(hash(dst), merged === undefined ? item.sha256 : crypto.createHash('sha256').update(merged).digest('hex'));
}
const materialized = [];
for (const [rel, target] of Object.entries(manifest.links)) {
  const dst = safe(home, rel), src = safe(home, target);
  parents(dst); preserve(dst, rel);
  if (fs.existsSync(dst) || (() => { try { return fs.lstatSync(dst).isSymbolicLink(); } catch { return false; } })()) {
    // 只替换本次授权的配置入口，原有入口已备份。
    fs.rmSync(dst, { recursive: true, force: true });
  }
  const directory = fs.statSync(src).isDirectory();
  try {
    fs.symlinkSync(process.platform === 'win32' ? src : path.relative(path.dirname(dst), src), dst,
      directory && process.platform === 'win32' ? 'junction' : directory ? 'dir' : 'file');
    assert.equal(fs.realpathSync(dst), fs.realpathSync(src));
  } catch (e) {
    if (process.platform !== 'win32' || directory || !['EPERM', 'EACCES'].includes(e.code)) throw e;
    // shortcut: Windows 未开放文件软链时用硬链接；跨卷时需用户开启软链权限。
    fs.linkSync(src, dst); materialized.push(rel);
    assert.equal(fs.statSync(dst).ino, fs.statSync(src).ino);
  }
}
for (const rel of ['.codex/auth.json', '.codex/config.toml', '.dsh/.credentials.yaml']) {
  const p = safe(home, rel);
  if (fs.existsSync(p) && process.platform !== 'win32') fs.chmodSync(p, 0o600);
}
const result = { files: Object.keys(manifest.files).length, hash_mismatches: 0,
  links: Object.keys(manifest.links).length, hardlink_fallbacks: materialized,
  backup, excluded_personal_history: true, unavailable: manifest.unavailable,
  preserved_shell_exports: preservedShellExports };
fs.writeFileSync(path.join(base, 'install-report.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
console.log(JSON.stringify(result));
