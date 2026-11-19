import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { execFileSync } from 'node:child_process';
import { collect, classify } from '../scripts/where.mjs';

const base = { git: true, cocos: false, web: false, verifySection: true, e2eDir: true, features: true, pending: false, tickets: 0, spec: false, worktrees: 0, evidenceHours: null, branch: 'main', base: 'main', onBase: true, dirty: 0, ahead: 0 };
const node = (o) => classify({ ...base, ...o }).node;

test('节点判定按优先级', () => {
  assert.equal(node({ git: false }), '未建仓');
  assert.equal(node({ verifySection: false, dirty: 3 }), '验证未接入');
  assert.equal(node({ dirty: 2, tickets: 5 }), '实现中');
  assert.equal(node({ onBase: false, branch: 'feat/x', ahead: 2 }), '待合并');
  assert.equal(node({ tickets: 3 }), '待实现');
  assert.equal(node({}), '空闲');
});

test('提示：小游戏、缺功能地图、有规格无票据', () => {
  const h = classify({ ...base, cocos: true, features: false, spec: true }).hints.join('\n');
  assert.match(h, /weicoz-game-flow/);
  assert.match(h, /FEATURES\.md/);
  assert.match(h, /to-tickets/);
});

test('collect 读真实仓库：develop 优先当基础分支、统计领先与未提交', () => {
  const dir = mkdtempSync(join(tmpdir(), 'where-'));
  const g = (...a) => execFileSync('git', a, { cwd: dir, stdio: 'ignore', env: { ...process.env, GIT_CONFIG_GLOBAL: '/dev/null' } });
  const put = (f, c) => { mkdirSync(dirname(join(dir, f)), { recursive: true }); writeFileSync(join(dir, f), c); };
  g('init', '-q', '-b', 'main'); g('config', 'user.email', 't@t'); g('config', 'user.name', 't');
  put('AGENTS.md', '# x\n\n## 验证约定\n- 快检：npm test\n');
  put('package.json', JSON.stringify({ devDependencies: { vite: '1' } }));
  put('.scratch/feat/issues/01.md', '**Status:** ready-for-agent\n');
  put('.scratch/feat/issues/02.md', 'Status: resolved\n');
  g('add', '-A'); g('commit', '-q', '-m', 'init');
  g('branch', 'develop'); g('checkout', '-q', '-b', 'feat/a');
  put('a.txt', '1'); g('add', '-A'); g('commit', '-q', '-m', 'a');
  put('b.txt', '2');
  const f = collect(dir);
  assert.equal(f.base, 'develop');
  assert.equal(f.ahead, 1);
  assert.equal(f.dirty, 1);
  assert.equal(f.web, true);
  assert.equal(f.tickets, 1);
  assert.equal(classify(f).node, '实现中');
  rmSync(dir, { recursive: true, force: true });
});

// ---- 1.1.0 新增：真实 git 临时仓库 ----
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { ticketStatus, isClosed } from '../scripts/where.mjs';

const SCRIPT = fileURLToPath(new URL('../scripts/where.mjs', import.meta.url));
const AGENTS = '# x\n\n## 验证约定\n- 快检：npm test\n';
function mkRepo(files = { 'AGENTS.md': AGENTS }, { commit = true } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'where-'));
  const g = (...a) => execFileSync('git', a, { cwd: dir, stdio: 'ignore', env: { ...process.env, GIT_CONFIG_GLOBAL: '/dev/null' } });
  const put = (f, c) => { mkdirSync(dirname(join(dir, f)), { recursive: true }); writeFileSync(join(dir, f), c); };
  g('init', '-q', '-b', 'main'); g('config', 'user.email', 't@t'); g('config', 'user.name', 't');
  for (const [k, v] of Object.entries(files)) put(k, v);
  if (commit) { g('add', '-A'); g('commit', '-q', '-m', 'init'); }
  return { dir, g, put, done: () => rmSync(dir, { recursive: true, force: true }) };
}
const run = (...a) => spawnSync('node', [SCRIPT, ...a], { encoding: 'utf8' });

test('S1 子目录：从仓库根读 AGENTS.md，输出仓库根与当前子目录', () => {
  const r = mkRepo({ 'AGENTS.md': AGENTS, 'src/x/a.txt': '1' });
  const f = collect(join(r.dir, 'src/x'));
  assert.equal(f.verifySection, true);
  assert.equal(f.sub, join('src', 'x'));
  const o = run('--repo', join(r.dir, 'src/x'));
  assert.match(o.stdout, /仓库根：/);
  assert.match(o.stdout, /当前子目录：src[\\/]x/);
  assert.doesNotMatch(o.stdout, /节点：验证未接入/);
  r.done();
});

test('S2 --repo 不存在：退出 2', () => {
  const o = run('--repo', '/nonexistent/where-xx');
  assert.equal(o.status, 2);
  assert.match(o.stderr, /不存在/);
});

test('S3 --base 缺值、以 -- 开头、ref 不存在：退出 2', () => {
  const r = mkRepo();
  assert.equal(run('--repo', r.dir, '--base').status, 2);
  assert.equal(run('--repo', r.dir, '--base', '--json').status, 2);
  const o = run('--repo', r.dir, '--base', 'nonexist');
  assert.equal(o.status, 2);
  assert.match(o.stderr, /nonexist/);
  assert.match(o.stderr, /main/);
  r.done();
});

test('S4 无提交的新仓库：未建仓，原因是还没有首次提交', () => {
  const r = mkRepo({ 'AGENTS.md': AGENTS }, { commit: false });
  const c = classify(collect(r.dir));
  assert.equal(c.node, '未建仓');
  assert.match(c.why, /首次提交/);
  r.done();
});

test('S5 票据状态各种写法', () => {
  const closed = ['Status: resolved', '**Status:** done', '- **Status**: Closed', 'status: "completed"', '状态：已完成', '---\nstatus: wontfix\n---', '# T\n\n## Status\n\nclosed\n', '状态：已关闭', '状态：完成'];
  const open = ['Status: done-ish, blocked', 'Status: ready-for-agent', '## Status\nin-progress', 'Status: claimed', '没有状态行', 'Status: closedx'];
  for (const t of closed) assert.equal(isClosed(t), true, t);
  for (const t of open) assert.equal(isClosed(t), false, t);
  assert.equal(ticketStatus('a\n'.repeat(25) + 'Status: done'), '');
});

test('S6 wayfinder 地图的票另计为决策票', () => {
  const r = mkRepo({
    'AGENTS.md': AGENTS,
    '.scratch/map/map.md': '# map',
    '.scratch/map/issues/01.md': 'Status: claimed\n',
    '.scratch/map/issues/02.md': 'Status: resolved\n',
    '.scratch/feat/issues/01.md': 'Status: ready-for-agent\n',
  });
  const f = collect(r.dir);
  assert.equal(f.decisions, 1);
  assert.equal(f.tickets, 1);
  assert.match(classify(f).hints.join('\n'), /wayfinder 地图有 1 张未决决策票：继续 wayfinder，清完后回 to-spec/);
  r.done();
});

test('S7 Cocos 只认 creator 字段或 settings/v2/packages', () => {
  const a = mkRepo({ 'package.json': JSON.stringify({ dependencies: { next: '1' } }), 'assets/a': '1', 'settings/b': '1' });
  assert.equal(collect(a.dir).cocos, false);
  assert.equal(collect(a.dir).web, true);
  a.done();
  const b = mkRepo({ 'package.json': JSON.stringify({ creator: { version: '3.8.0' } }) });
  assert.equal(collect(b.dir).cocos, true);
  b.done();
  const c = mkRepo({ 'settings/v2/packages/x.json': '{}' });
  assert.equal(collect(c.dir).cocos, true);
  c.done();
});

test('S8 Web 判断：扩充依赖表、@remix-run/*、monorepo 子包', () => {
  for (const d of ['@angular/core', 'solid-js', 'express', 'webpack', '@remix-run/react', 'hono']) {
    const r = mkRepo({ 'package.json': JSON.stringify({ dependencies: { [d]: '1' } }) });
    assert.equal(collect(r.dir).web, true, d);
    r.done();
  }
  const m = mkRepo({ 'package.json': '{}', 'packages/web/package.json': JSON.stringify({ dependencies: { vue: '1' } }) });
  assert.equal(collect(m.dir).web, true);
  m.done();
  const n = mkRepo({ 'apps/site/package.json': JSON.stringify({ devDependencies: { astro: '1' } }) });
  assert.equal(collect(n.dir).web, true);
  n.done();
  const o = mkRepo({ 'package.json': JSON.stringify({ dependencies: { lodash: '1' } }) });
  assert.equal(collect(o.dir).web, false);
  o.done();
});

test('S9 只有未跟踪文件：仍是实现中，原因与提示点明', () => {
  const r = mkRepo();
  r.put('tmp.txt', 'x');
  const c = classify(collect(r.dir));
  assert.equal(c.node, '实现中');
  assert.match(c.why, /全是未跟踪文件/);
  assert.match(c.hints.join('\n'), /\.gitignore/);
  r.put('AGENTS.md', AGENTS + 'y\n');
  const c2 = classify(collect(r.dir));
  assert.doesNotMatch(c2.why, /全是未跟踪/);
  r.done();
});

test('S10 develop 领先 main：提示发版合并需授权', () => {
  const r = mkRepo();
  r.g('checkout', '-q', '-b', 'develop');
  r.put('a.txt', '1'); r.g('add', '-A'); r.g('commit', '-q', '-m', 'a');
  const f = collect(r.dir);
  assert.equal(f.devAheadMain, 1);
  assert.match(classify(f).hints.join('\n'), /develop 领先 main 1 个提交：发版按项目流程合并到 main（需用户授权）/);
  r.done();
});

test('S11 待合并与实现中的审查命令带 --repo <仓库根>', () => {
  const m = classify({ ...base, onBase: false, branch: 'feat/x', ahead: 2 }).next.join('\n');
  assert.match(m, /weicoz-code-review main\.\.HEAD --repo <仓库根>/);
  const i = classify({ ...base, dirty: 1 }).next.join('\n');
  assert.match(i, /weicoz-code-review main --repo <仓库根>/);
});

test('复审补充：CRLF、closed-duplicate、✅ done、Wont fix 都算关闭', () => {
  for (const t of ['Status: resolved\r\n', 'Status: closed-duplicate\n', 'Status: ✅ done\n', "Status: Won't fix\n", 'Status: wont fix\n']) assert.equal(isClosed(t), true, t);
  for (const t of ['Status: ready-for-agent\n', 'Status: done-ish\n']) assert.equal(isClosed(t), false, t);
});

test('复审补充：package.json 为 null 不崩；react-scripts 算 Web；Type research 记决策票；ready-for-human 单计', () => {
  const r = mkRepo({
    'AGENTS.md': AGENTS,
    'package.json': JSON.stringify({ dependencies: { 'react-scripts': '5' } }),
    'apps/a/package.json': 'null',
    '.scratch/f/issues/01.md': 'Status: ready-for-human\n',
    '.scratch/f/issues/02.md': 'Status: ready-for-agent\n',
    '.scratch/f/issues/03.md': 'Type: research\nStatus: claimed\n',
  });
  const out = run('--repo', r.dir, '--json');
  assert.equal(out.status, 0, out.stderr);
  const j = JSON.parse(out.stdout);
  assert.equal(j.facts.web, true);
  assert.equal(j.facts.tickets, 2);
  assert.equal(j.facts.humanTickets, 1);
  assert.equal(j.facts.decisions, 1);
  assert.match(j.hints.join('\n'), /ready-for-human/);
  r.done();
});
