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
