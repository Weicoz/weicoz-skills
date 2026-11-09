#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const home = os.homedir();
const stateRel = '.local/state/harness-config-sync';
const root = path.join(home, stateRel);
const statePath = path.join(root, 'state.json');
const deny = new Set(['.ssh', 'sessions', 'memories', 'memories_v2', 'generated_images', 'attachments', 'automations']);
const privatePrefixes = ['.kimi-code/oauth', '.kimi-code/credentials', '.kimi-code/logs', '.config/harness-notify/config.json', '.gemini/brain',
  '.gemini/conversations', '.gemini/log', '.gemini/cache', '.gemini/antigravity-browser-profile',
  '.gemini/google_accounts.json', '.gemini/oauth_creds.json', '.gemini/antigravity-cli/antigravity-oauth-token'];
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function parseJSON(text) {
  let value;
  try { value = JSON.parse(text); } catch { throw new Error('JSON 格式无效'); }
  const tokens = text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]/g) ?? [];
  const stack = [];
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (token === '{') stack.push(new Set());
    else if (token === '[') stack.push(null);
    else if (token === '}' || token === ']') stack.pop();
    else if (token.startsWith('"') && tokens[i + 1] === ':' && stack.at(-1) instanceof Set) {
      const key = JSON.parse(token);
      check(!stack.at(-1).has(key), 'JSON 存在重复字段');
      stack.at(-1).add(key);
    }
  }
  return value;
}
const readJSON = p => parseJSON(fs.readFileSync(p, 'utf8'));
const exists = p => { try { return fs.lstatSync(p); } catch (e) { if (e.code === 'ENOENT') return null; throw e; } };
const check = (value, message) => assert(value, message);
function safe(base, rel) {
  check(typeof rel === 'string' && rel && !rel.includes('\\') && !rel.includes(':') && !path.isAbsolute(rel), '相对路径无效');
  const parts = rel.split('/'), lower = rel.toLowerCase();
  check(!parts.some(p => !p || p === '.' || p === '..' || deny.has(p.toLowerCase())), '拒绝个人数据或越界路径');
  check(parts[0].toLowerCase() !== '.claude', 'Claude Code 不在迁移范围');
  const standardRoots = new Set(['.codex', '.dsh', '.gemini', '.kimi-code', '.agents', '.local', '.config', '.zshrc', '.zshenv', '.zprofile', '.p10k.zsh']);
  check(!standardRoots.has(parts[0].toLowerCase()) || parts[0] === parts[0].toLowerCase(), '配置根入口必须使用标准大小写');
  check(!privatePrefixes.some(p => lower === p || lower.startsWith(p + '/')) && path.basename(lower) !== 'history.jsonl', '拒绝个人运行数据或设备登录状态');
  check(!parts.some(p => /[. ]$|[\x00-\x1f]/.test(p) || /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(p)), '路径含非跨平台文件名');
  const p = path.resolve(base, rel);
  check(p.startsWith(base + path.sep), '路径越界');
  return p;
}
function parents(p, create = false) {
  let current = home;
  for (const part of path.relative(home, path.dirname(p)).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    const st = exists(current);
    if (st) check(st.isDirectory() && !st.isSymbolicLink(), '父目录是链接或非目录；先核对实际配置入口');
    else if (create) fs.mkdirSync(current, { mode: 0o700 });
  }
}
function atomic(p, bytes, mode = 0o600) {
  parents(p, true);
  const tmp = p + '.sync-' + crypto.randomUUID();
  try {
    fs.writeFileSync(tmp, bytes, { mode, flag: 'wx' });
    for (let attempt = 0; ; attempt++) {
      try { fs.renameSync(tmp, p); break; }
      catch (e) {
        if (attempt >= 5 || !['EPERM', 'EACCES', 'EBUSY'].includes(e.code)) throw e;
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50 * (attempt + 1));
      }
    }
  } finally { if (exists(tmp)) fs.unlinkSync(tmp); }
}
function jsonWrite(p, value) { atomic(p, JSON.stringify(value, null, 2) + '\n'); }
function fingerprint(p, target = null) {
  const st = exists(p);
  if (!st) return null;
  if (st.isSymbolicLink()) {
    const resolved = path.resolve(path.dirname(p), fs.readlinkSync(p));
    if (target && resolved === safe(home, target)) return { kind: 'link', target };
    return { kind: 'symlink', target: fs.readlinkSync(p) };
  }
  if (target && exists(safe(home, target))) {
    const other = fs.statSync(safe(home, target));
    if (other.dev === st.dev && other.ino === st.ino) return { kind: 'link', target };
  }
  if (st.isFile()) return { kind: 'file', sha256: digest(fs.readFileSync(p)), mode: st.mode & 0o777 };
  if (st.isDirectory()) {
    const entries = fs.readdirSync(p).sort().map(n => [n, fingerprint(path.join(p, n))]);
    return { kind: 'directory', sha256: digest(JSON.stringify(entries)) };
  }
  throw new Error('受管路径不是常规文件、目录或链接');
}
const reference = value => /^(?:Bearer\s+)?(?:\$\{[A-Za-z_]\w*\}|\$[A-Za-z_]\w*|env:[A-Za-z_]\w*)$/.test(value);
function credentials(bytes, rel) {
  rel = rel.toLowerCase();
  if (!/\.(json|toml|ya?ml)$/.test(rel)) return false;
  const text = bytes.toString('utf8');
  if (!text.trim()) return false;
  const key = name => {
    const normalized = name.toLowerCase().replace(/[^a-z0-9]/g, '');
    return /(?:apikey|accesstoken|authtoken|refreshtoken|clientsecret|bottoken|bearertoken|devicekey|password|passwd|secret|authorization|privatekey)$/.test(normalized) || normalized === 'token';
  };
  if (rel.endsWith('.json')) {
    const walk = v => Array.isArray(v) ? v.some(walk) : v && typeof v === 'object' ?
      Object.entries(v).some(([k, x]) => (key(k) && x !== null && x !== '' && (typeof x !== 'string' || !reference(x))) || walk(x)) :
      typeof v === 'string' && /https?:\/\/[^/\s:@]+:[^/\s@]+@/.test(v);
    return Boolean(walk(parseJSON(text)));
  }
  // shortcut: 非 JSON 凭据用保守词法检查；复杂内嵌格式命中时改用目标保留或独立凭据文件。
  if (/["'][^"'\n]*\\[^"'\n]*["']\s*[:=]/.test(text)) return true;
  const assignment = /(?:^|[\s{,])["']?([\w.-]+)["']?\s*[:=]\s*/gm;
  for (const match of text.matchAll(assignment)) {
    if (!key(match[1])) continue;
    const raw = text.slice(match.index + match[0].length).match(/^("(?:\\.|[^"\\])*"|'[^']*'|[^,\s#}\]]+)/)?.[1] ?? '';
    const value = raw.replace(/^["']|["']$/g, '');
    if (key(match[1]) && value && !reference(value)) return true;
  }
  return /https?:\/\/[^/\s:@]+:[^/\s@]+@/.test(text);
}
function locked(fn) {
  parents(path.join(root, 'lock'), true);
  const lock = path.join(root, 'lock');
  const fd = fs.openSync(lock, 'wx', 0o600);
  try { fs.writeFileSync(fd, String(process.pid)); return fn(); }
  finally { fs.closeSync(fd); fs.unlinkSync(lock); }
}
function link(dst, target) {
  const src = safe(home, target);
  const directory = fs.statSync(src).isDirectory();
  try {
    fs.symlinkSync(process.platform === 'win32' ? src : path.relative(path.dirname(dst), src), dst,
      directory && process.platform === 'win32' ? 'junction' : directory ? 'dir' : 'file');
  } catch (e) {
    if (process.platform !== 'win32' || directory || !['EPERM', 'EACCES'].includes(e.code)) throw e;
    fs.linkSync(src, dst);
  }
}
function remove(p) {
  const st = exists(p);
  if (!st) return;
  if (st.isDirectory() && !st.isSymbolicLink()) fs.rmSync(p, { recursive: true });
  else fs.unlinkSync(p);
}
function loadState() {
  parents(statePath);
  check(!exists(statePath)?.isSymbolicLink(), '状态文件不能是链接');
  return exists(statePath) ? readJSON(statePath) : null;
}
function pendingTransactions() {
  const transactions = path.join(root, 'transactions');
  parents(path.join(transactions, 'entry'));
  if (!exists(transactions)) return [];
  return fs.readdirSync(transactions, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name).filter(id => {
    const p = path.join(transactions, id, 'journal.json');
    parents(p);
    return exists(p) && ['applying', 'failed'].includes(readJSON(p).status);
  }).sort();
}
function inspectState(state) {
  const drift = [];
  for (const [rel, item] of Object.entries(state?.entries ?? {})) {
    const p = safe(home, rel); parents(p);
    if (!equal(fingerprint(p, item.target), item.fingerprint)) drift.push(rel);
  }
  return { schema: 2, device_id: state?.device_id ?? null, source_id: state?.source_id ?? null,
    revision: state?.revision ?? null, transaction: state?.transaction ?? null,
    last_sync: state?.last_sync ?? null, managed: Object.keys(state?.entries ?? {}).length,
    checked_at: new Date().toISOString(), pending: pendingTransactions(),
    drift, unavailable: state?.unavailable ?? [], retained: state?.retained ?? [] };
}
function probeCLI(command, args) {
  const allowed = (args.length === 1 && args[0] === '--version') ||
    (command === 'kimi' && equal(args, ['doctor', 'config']));
  check(['codex', 'dsh', 'agy', 'kimi'].includes(command) && allowed, '只接受固定 CLI 检查');
  const options = { encoding: 'utf8', timeout: 15000, maxBuffer: 1024 * 1024 };
  // Windows 的 npm .cmd 入口通过系统命令解释器启动；命令和参数均为固定白名单。
  return process.platform === 'win32' ? spawnSync('cmd.exe', ['/d', '/s', '/c', `${command} ${args.join(' ')}`], options) : spawnSync(command, args, options);
}
function verify(state) {
  const result = inspectState(state);
  const versions = {};
  const commands = { codex: '.codex/', dsh: '.dsh/', agy: '.gemini/', kimi: '.kimi-code/' };
  for (const [command, prefix] of Object.entries(commands)) {
    if (!Object.keys(state?.entries ?? {}).some(p => p.startsWith(prefix))) continue;
    const probe = probeCLI(command, ['--version']);
    const actual = (probe.stdout ?? '').match(/(?:^|[^\w])v?(\d+\.\d+\.\d+[^\s]*)/)?.[1] ?? null;
    const expected = state.versions?.[command] ?? null;
    versions[command] = { actual, expected, ok: probe.status === 0 && Boolean(actual) && (!expected || expected === actual) };
  }
  let kimiDoctor = null;
  if (versions.kimi?.ok) {
    const p = probeCLI('kimi', ['doctor', 'config']);
    kimiDoctor = p.status === 0;
  }
  return { ...result, versions, kimi_doctor: kimiDoctor, model_requests: '未验证',
    version_parity: Object.values(versions).length > 0 && Object.values(versions).every(v => v.expected && v.ok) ? '已验证' : '未验证',
    verified: Boolean(state) && !result.pending.length && !result.drift.length && Object.values(versions).every(v => v.ok) && kimiDoctor !== false };
}
function prepare(base, replacements) {
  const manifestPath = path.join(base, 'manifest.json');
  check(!exists(manifestPath)?.isSymbolicLink(), 'manifest 不能是链接');
  const manifest = readJSON(manifestPath);
  check(manifest.schema === 2 && manifest.includes_personal_history === false, '仅接受 schema 2 的无历史迁移包');
  check(manifest.platform === process.platform, '目标平台不匹配');
  const normalize = p => process.platform === 'win32' ? p.toLowerCase().replaceAll('\\', '/') : p;
  check(normalize(manifest.target_home) === normalize(home), '目标用户目录不匹配');
  check(/^[A-Za-z0-9_.-]+$/.test(manifest.source_id) && /^[A-Za-z0-9_.-]+$/.test(manifest.device_id), '配置源或设备 ID 无效');
  const state = loadState();
  if (state) check(state.source_id === manifest.source_id && state.device_id === manifest.device_id, '配置源或设备 ID 与已登记基线不同');
  const entries = {}, bytes = new Map();
  const all = [...Object.keys(manifest.files), ...Object.keys(manifest.links)];
  check(new Set(all).size === all.length, '文件与链接路径重复');
  const sorted = [...all].sort();
  const lowerPaths = new Set(all.map(p => p.toLowerCase()));
  const aliases = new Map();
  for (const rel of sorted) {
    const parts = rel.split('/');
    for (let i = 1; i <= parts.length; i++) {
      const prefix = parts.slice(0, i).join('/'), lower = prefix.toLowerCase();
      check(!aliases.has(lower) || aliases.get(lower) === prefix, '目标路径存在大小写别名冲突');
      aliases.set(lower, prefix);
      if (i < parts.length) check(!lowerPaths.has(lower), '受管路径相互包含');
    }
  }
  for (const [rel, info] of Object.entries(manifest.files)) {
    const lower = rel.toLowerCase();
    check(!lower.startsWith(stateRel + '/') && lower !== stateRel && !stateRel.startsWith(lower + '/'), '配置包不能覆盖同步状态');
    const src = safe(path.join(base, 'payload'), rel);
    let cursor = path.join(base, 'payload');
    check(!fs.lstatSync(cursor).isSymbolicLink(), 'payload 不能是链接');
    for (const part of rel.split('/')) { cursor = path.join(cursor, part); check(!fs.lstatSync(cursor).isSymbolicLink(), 'payload 路径包含链接'); }
    let data = fs.readFileSync(src);
    check(digest(data) === info.sha256, `包哈希错误：${rel}`);
    check(manifest.includes_login_files || !['.codex/auth.json', '.dsh/.credentials.yaml'].includes(rel.toLowerCase()), '包包含未授权登录文件');
    check(Number.isInteger(info.mode) && info.mode >= 0 && info.mode <= 0o777, '文件权限无效');
    if (rel.toLowerCase().endsWith('.json')) parseJSON(data.toString('utf8'));
    if (!manifest.includes_login_files) check(!credentials(data, rel), `包包含未授权凭据：${rel}`);
    if (/^\.zsh(?:env|rc|profile)$/.test(rel)) {
      const dst = safe(home, rel); parents(dst);
      if (exists(dst)?.isFile()) {
        const incoming = data.toString('utf8').split(/\r?\n/);
        const exports = fs.readFileSync(dst, 'utf8').split(/\r?\n/).filter(line => {
          const match = line.match(/^\s*export\s+(\w+)\s*=/);
          return match && /^(?:PATH|.*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PROXY|BASE_URL|ENDPOINT|API_TIMEOUT).*)$/i.test(match[1]) && !incoming.includes(line);
        });
        if (exports.length) data = Buffer.from(data.toString('utf8') + '\n# 保留目标已有 PATH、代理及凭据导出\n' + [...new Set(exports)].join('\n') + '\n');
      }
    }
    if (/^\.(?:zsh(?:env|rc|profile)|p10k\.zsh)$/.test(rel)) {
      const probe = spawnSync('zsh', ['-n'], { input: data, encoding: 'utf8', timeout: 10000 });
      check(probe.status === 0, 'Shell 语法检查失败或目标未安装 zsh；尚未写入配置');
    }
    bytes.set(rel, data);
    entries[rel] = { kind: 'file', sha256: digest(data), mode: process.platform === 'win32' ? 0o666 : (info.mode & 0o111 ? 0o700 : 0o600) };
  }
  for (const [rel, target] of Object.entries(manifest.links)) {
    const lower = rel.toLowerCase();
    check(!lower.startsWith(stateRel + '/') && lower !== stateRel && !stateRel.startsWith(lower + '/'), '配置包不能覆盖同步状态');
    safe(home, target);
    check(!Object.keys(manifest.links).some(p => target === p || target.startsWith(p + '/')), '链接目标必须指向常规文件或目录');
    entries[rel] = { kind: 'link', target };
    const available = Object.keys(manifest.files).some(p => p === target || p.startsWith(target + '/')) || exists(safe(home, target));
    check(available, `链接目标缺失：${rel}`);
  }
  const plan = [], conflicts = [], current = {};
  for (const [rel, desired] of Object.entries(entries)) {
    const dst = safe(home, rel); parents(dst);
    current[rel] = fingerprint(dst, desired.target);
    if (equal(current[rel], desired)) continue;
    if (!manifest.includes_login_files && current[rel]?.kind === 'file')
      check(!credentials(fs.readFileSync(dst), rel), `目标含独立凭据，保留该路径或显式授权账号迁移：${rel}`);
    const previous = state?.entries[rel]?.fingerprint;
    const conflict = current[rel] !== null && (!previous || !equal(previous, current[rel]));
    if (conflict && !replacements.has(rel)) conflicts.push(rel);
    plan.push({ path: rel, action: current[rel] ? 'replace' : 'create', conflict });
  }
  // Windows 的硬链接必须在公共规则正文替换后重建。
  for (const [rel, target] of Object.entries(manifest.links)) {
    if (!exists(safe(home, rel))?.isSymbolicLink() && plan.some(p => p.path === target) && !plan.some(p => p.path === rel))
      plan.push({ path: rel, action: 'relink', conflict: false });
  }
  for (const rel of replacements) { safe(home, rel); check(rel in entries, '替换授权路径不在本次包内'); }
  const retained = Object.keys(state?.entries ?? {}).filter(p => !(p in entries));
  const token = digest(JSON.stringify({ manifest, current, state, replace: [...replacements].sort() }));
  return { manifest, state, entries, bytes, current, result: { schema: 2, source_id: manifest.source_id,
    device_id: manifest.device_id, revision: manifest.revision, plan_token: token, changes: plan,
    conflicts, retained, keep: manifest.keep ?? [], pending: pendingTransactions(), unavailable: manifest.unavailable } };
}
function rollback(transaction, automatic = false) {
  check(/^[A-Za-z0-9-]+$/.test(transaction), '恢复点 ID 无效');
  const folder = path.join(root, 'transactions', transaction);
  parents(path.join(folder, 'journal.json'));
  const journal = readJSON(path.join(folder, 'journal.json'));
  check(journal.transaction === transaction && ['applying', 'committed', 'failed'].includes(journal.status), '恢复点不可回滚');
  const progressPath = path.join(folder, 'applied.jsonl');
  const progress = exists(progressPath);
  if (progress) {
    check(progress.isFile() && !progress.isSymbolicLink(), '进度日志不能是链接或目录');
    // 未完成的末行对应尚未开始的写入；完整记录在修改目标前已刷盘。
    const records = fs.readFileSync(progressPath, 'utf8').split('\n').slice(0, -1).map(parseJSON);
    check(records.every(rel => typeof rel === 'string' && Object.hasOwn(journal.entries, rel) && Object.hasOwn(journal.snapshots, rel)), '进度日志包含未知路径');
    journal.applied = [...new Set([...journal.applied, ...records])];
  }
  const state = loadState();
  if (journal.status === 'committed') check(state?.transaction === transaction, '仅能回滚当前最新同步');
  else check(equal(state, journal.previous_state) || state?.transaction === transaction, '恢复点已过期；当前基线属于后续同步');
  const affected = [...new Set([...journal.applied, ...Object.keys(journal.snapshots).filter(rel =>
    journal.snapshots[rel]?.kind === 'managed-link' && journal.applied.includes(journal.snapshots[rel].target))])];
  for (const rel of affected) {
    const dst = safe(home, rel); parents(dst);
    const now = fingerprint(dst, journal.entries[rel].target);
    const intermediate = journal.status !== 'committed' && journal.snapshots[rel]?.kind === 'managed-link' &&
      equal(now, journal.before[journal.snapshots[rel].target]);
    check(equal(now, journal.entries[rel]) || equal(now, journal.before[rel]) || intermediate || (journal.status !== 'committed' && now === null), `回滚前发现新改动：${rel}`);
  }
  for (const rel of [...affected].reverse()) {
    const dst = safe(home, rel), snapshot = safe(folder, 'files/' + rel);
    const saved = journal.snapshots[rel];
    if (equal(fingerprint(dst, journal.entries[rel].target), journal.before[rel])) continue;
    remove(dst); parents(dst, true);
    if (saved?.kind === 'symlink') fs.symlinkSync(saved.target, dst, saved.directory ? 'junction' : 'file');
    else if (saved?.kind === 'managed-link') continue;
    else if (saved) fs.cpSync(snapshot, dst, { recursive: saved.kind === 'directory', verbatimSymlinks: true, preserveTimestamps: true });
  }
  for (const rel of affected) {
    const saved = journal.snapshots[rel];
    if (saved?.kind === 'managed-link') { const dst = safe(home, rel); remove(dst); link(dst, saved.target); }
  }
  if (journal.previous_state) jsonWrite(statePath, journal.previous_state);
  else if (exists(statePath)) fs.unlinkSync(statePath);
  journal.status = 'rolled-back'; jsonWrite(path.join(folder, 'journal.json'), journal);
  return { transaction, rolled_back: true, automatic };
}
function apply(base, replacements, token) {
  return locked(() => {
    const prepared = prepare(base, replacements);
    const { manifest, state, entries, bytes, current, result } = prepared;
    check(token === result.plan_token, '预览已过期，重新预览后使用新的 plan_token');
    check(!result.pending.length, `存在未完成事务，先恢复：${result.pending.join(', ')}`);
    check(!result.conflicts.length, '目标有独立改动；先解决冲突或逐路径 --replace 后重新预览');
    if (!result.changes.length && state?.payload_id === manifest.payload_id && state?.revision === manifest.revision) return { ...result, unchanged: true };
    const transaction = crypto.randomUUID();
    const folder = path.join(root, 'transactions', transaction);
    const journal = { transaction, status: 'applying', applied: [], before: current, entries,
      previous_state: state, snapshots: {} };
    for (const { path: rel } of result.changes) {
      const dst = safe(home, rel), st = exists(dst);
      if (!st) { journal.snapshots[rel] = null; continue; }
      if (st.isSymbolicLink()) journal.snapshots[rel] = { kind: 'symlink', target: fs.readlinkSync(dst), directory: fs.statSync(dst, { throwIfNoEntry: false })?.isDirectory() ?? false };
      else if (current[rel]?.kind === 'link') journal.snapshots[rel] = { kind: 'managed-link', target: current[rel].target };
      else {
        const snapshot = safe(folder, 'files/' + rel); parents(snapshot, true);
        fs.cpSync(dst, snapshot, { recursive: st.isDirectory(), verbatimSymlinks: true, preserveTimestamps: true });
        journal.snapshots[rel] = { kind: st.isDirectory() ? 'directory' : 'file' };
      }
    }
    const journalPath = path.join(folder, 'journal.json');
    jsonWrite(journalPath, journal);
    let progressFD;
    const transactionRel = `${stateRel}/transactions/${transaction}`;
    let active = { stage: 'open-progress', path: `${transactionRel}/applied.jsonl` };
    try {
      progressFD = fs.openSync(path.join(folder, 'applied.jsonl'), 'ax', 0o600);
      for (const { path: rel, action } of result.changes) {
        active = { stage: 'check-target', path: rel };
        const dst = safe(home, rel); parents(dst, true);
        const now = fingerprint(dst, entries[rel].target);
        const relinking = action === 'relink' && equal(now, current[entries[rel].target]);
        check(equal(now, current[rel]) || relinking, `写入前发现新改动：${rel}`);
        active = { stage: 'append-progress', path: `${transactionRel}/applied.jsonl` };
        journal.applied.push(rel);
        fs.appendFileSync(progressFD, JSON.stringify(rel) + '\n');
        fs.fsyncSync(progressFD);
        active = { stage: 'write-target', path: rel };
        const item = entries[rel];
        if (item.kind === 'file') {
          if (exists(dst)?.isDirectory() || exists(dst)?.isSymbolicLink()) remove(dst);
          atomic(dst, bytes.get(rel), item.mode);
        } else { remove(dst); link(dst, item.target); }
      }
      for (const [rel, item] of Object.entries(entries)) {
        active = { stage: 'verify-target', path: rel };
        check(equal(fingerprint(safe(home, rel), item.target), item), `安装后校验失败：${rel}`);
      }
      const next = { schema: 2, source_id: manifest.source_id, device_id: manifest.device_id,
        revision: manifest.revision, payload_id: manifest.payload_id, transaction, last_sync: new Date().toISOString(), versions: manifest.versions,
        unavailable: manifest.unavailable, retained: result.retained,
        entries: Object.fromEntries(Object.entries(entries).map(([rel, item]) => [rel, { target: item.target, fingerprint: item }])) };
      active = { stage: 'write-state', path: `${stateRel}/state.json` };
      jsonWrite(statePath, next);
      active = { stage: 'write-journal', path: `${transactionRel}/journal.json` };
      journal.status = 'committed'; jsonWrite(journalPath, journal);
      active = { stage: 'inspect-state', path: stateRel };
      const report = { ...inspectState(next), changes: result.changes.length, backup: transaction, model_requests: '未验证' };
      active = { stage: 'write-report', path: `${transactionRel}/install-report.json` };
      jsonWrite(path.join(folder, 'install-report.json'), report);
      return report;
    } catch (e) {
      journal.status = 'failed';
      journal.failure = { ...active, code: /^[A-Z_]{2,32}$/.test(e.code ?? '') ? e.code : 'ERROR' };
      try { jsonWrite(journalPath, journal); } catch { /* 日志故障仍须尝试按已落盘日志恢复。 */ }
      try { rollback(transaction, true); }
      catch { throw new Error(`安装失败且自动回滚未完成；使用 --rollback ${transaction} 恢复，保留全部备份`); }
      throw new Error(`安装失败（${journal.failure.code}，${journal.failure.path ?? '事务初始化'}），已自动回滚；目标配置恢复到安装前`);
    } finally {
      if (progressFD !== undefined) fs.closeSync(progressFD);
    }
  });
}
function main() {
  const args = process.argv.slice(2);
  if (args[0] === '--collect') {
    const devices = args.slice(1).map(p => readJSON(p));
    check(devices.length && devices.every(d => d.schema === 2 && typeof d.device_id === 'string' && Array.isArray(d.drift)), '必须提供各设备状态或验证报告');
    return { devices: devices.map(d => ({ device_id: d.device_id, source_id: d.source_id, revision: d.revision,
      last_sync: d.last_sync, checked_at: d.checked_at, pending: d.pending ?? [],
      drift: d.drift.length, verified: d.verified ?? null, unavailable: d.unavailable })) };
  }
  if (args[0] === '--status') return inspectState(loadState());
  if (args[0] === '--verify') {
    const result = verify(loadState());
    if (!result.verified) process.exitCode = 1;
    return result;
  }
  if (args[0] === '--rollback') return locked(() => rollback(args[1]));
  check(args[0] && !args[0].startsWith('--'), '用法：install.mjs <包目录> [--apply --plan TOKEN] [--replace 相对路径]；另有 --status / --verify / --rollback ID / --collect 报告...');
  const base = path.resolve(args.shift());
  const replacements = new Set(); let doApply = false, token;
  while (args.length) {
    const option = args.shift();
    if (option === '--apply') doApply = true;
    else if (option === '--plan') token = args.shift();
    else if (option === '--replace') replacements.add(args.shift());
    else throw new Error('未知参数');
  }
  return doApply ? apply(base, replacements, token) : prepare(base, replacements).result;
}
try { console.log(JSON.stringify(main(), null, 2)); }
catch (e) { console.error(e instanceof assert.AssertionError ? e.message : '同步失败：' + (e.code ?? (e.constructor === Error ? e.message : '配置解析或文件操作失败'))); process.exitCode = 1; }
