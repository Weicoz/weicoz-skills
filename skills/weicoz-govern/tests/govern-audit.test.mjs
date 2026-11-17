import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { audit, globToRe, ARCHIVE_RE } from '../scripts/govern-audit.mjs';

const SCRIPT = join(import.meta.dirname, '../scripts/govern-audit.mjs');

function repo(files, { date } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'govern-'));
  const g = (...a) => execFileSync('git', a, { cwd: dir, stdio: 'ignore', env: { ...process.env, GIT_AUTHOR_DATE: date, GIT_COMMITTER_DATE: date, GIT_CONFIG_GLOBAL: '/dev/null' } });
  g('init', '-q', '-b', 'main');
  g('config', 'user.email', 't@t'); g('config', 'user.name', 't');
  for (const [f, c] of Object.entries(files)) { mkdirSync(dirname(join(dir, f)), { recursive: true }); writeFileSync(join(dir, f), c); }
  g('add', '-A'); g('commit', '-q', '-m', 'init');
  return { dir, g, done: () => rmSync(dir, { recursive: true, force: true }) };
}
const find = (r, re) => r.findings.filter((f) => re.test(f.message));
const OLD = '2020-01-01T00:00:00';

test('AGENTS.md 超 10KB 为高；CLAUDE.md 非单行入口为中', () => {
  const r = repo({ 'AGENTS.md': 'x'.repeat(11000), 'CLAUDE.md': '# 另写一份\n' });
  const a = audit(r.dir);
  assert.equal(find(a, /超过 10 KB/)[0].level, '高');
  assert.equal(find(a, /不是单行/)[0].level, '中');
  r.done();
});

test('AGENTS.md 体积正常且 CLAUDE.md 仅 @AGENTS.md 时无发现', () => {
  const r = repo({ 'AGENTS.md': '# 地图\n', 'CLAUDE.md': '@AGENTS.md\n' });
  assert.equal(audit(r.dir).findings.length, 0);
  r.done();
});

test('死链命中；存在的链接、外链、锚点、围栏内链接、path:行号后缀不误报', () => {
  const r = repo({
    'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md',
    'docs/a.md': '[坏](missing.md)\n[好](b.md#x)\n[外](https://x.y/z)\n[锚](#top)\n[行号](b.md:12)\n```\n[围栏](nope.md)\n```\n[占位](issues/NN-x.md)\n',
    'docs/b.md': 'b',
  });
  const d = find(audit(r.dir), /死链/);
  assert.equal(d.length, 1);
  assert.equal(d[0].path, 'docs/a.md:1');
  r.done();
});

test('疑似过期：旧文档引用不存在路径命中；新文档与存在的路径不命中', () => {
  const stale = repo({ 'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md', 'src/real.ts': '', 'docs/old.md': '见 `src/gone.ts` 和 `src/real.ts`\n' }, { date: OLD });
  const r1 = find(audit(stale.dir), /疑似过期/);
  assert.equal(r1.length, 1);
  assert.match(r1[0].message, /gone\.ts/);
  assert.doesNotMatch(r1[0].message, /real\.ts/);
  const fresh = repo({ 'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md', 'src/real.ts': '', 'docs/new.md': '见 `src/gone.ts`\n' }, { date: new Date().toISOString() });
  assert.equal(find(audit(fresh.dir), /疑似过期/).length, 0);
  const apiLike = repo({ 'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md', 'src/real.ts': '', 'docs/old.md': '调用 `tags/update` 版本 `22.04/24.04`\n' }, { date: OLD });
  assert.equal(find(audit(apiLike.dir), /疑似过期/).length, 0);
  [stale, fresh, apiLike].forEach((x) => x.done());
});

test('孤儿测试：vitest include 之外且无引用命中；范围内与被脚本引用的不命中', () => {
  const r = repo({
    'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md',
    'package.json': JSON.stringify({ scripts: { 'test:extra': 'vitest run extra/ref.test.ts' }, devDependencies: { vitest: '1' } }),
    'vitest.config.ts': "export default { test: { include: ['tests/**/*.test.ts'] } }",
    'tests/in.test.ts': "import {it,expect} from 'vitest'; it('a',()=>{expect(1+1).toBe(2)})",
    'lost/orphan.test.ts': "import {it,expect} from 'vitest'; it('a',()=>{expect(1+1).toBe(2)})",
    'extra/ref.test.ts': "import {it,expect} from 'vitest'; it('a',()=>{expect(1+1).toBe(2)})",
  });
  const a = audit(r.dir);
  const o = find(a, /孤儿测试/);
  assert.equal(o.length, 1);
  assert.equal(o[0].path, 'lost/orphan.test.ts:1');
  assert.equal(a.tests.total, 3);
  r.done();
});

test('无 include 时按 vitest 默认规则；include 无法解析标待确认', () => {
  const ok = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md', 'package.json': JSON.stringify({ devDependencies: { vitest: '1' } }), 'a/x.spec.ts': "it('a',()=>{expect(1).toBe(1+0)})" });
  assert.equal(find(audit(ok.dir), /孤儿/).length, 0);
  const unk = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md', 'vitest.config.ts': 'export default { test: { include: patterns } }', 'a/x.__tests__.ts': '', 'z/__tests__/y.ts': "it('a',()=>{expect(2).toBe(1+1)})" });
  const u = find(audit(unk.dir), /待确认/);
  assert.ok(u.length >= 1 && u.every((f) => f.level === '低'));
  [ok, unk].forEach((x) => x.done());
});

test('node:test 文件被 node --test 脚本覆盖时不算孤儿', () => {
  const body = "import test from 'node:test'; import assert from 'node:assert'; test('a',()=>{assert.equal(1,1+0)})";
  const r = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md', 'package.json': JSON.stringify({ scripts: { test: 'node --test tests/' } }), 'tests/a.test.mjs': body, 'other/b.test.mjs': body });
  const o = find(audit(r.dir), /孤儿/);
  assert.equal(o.length, 1);
  assert.equal(o[0].path, 'other/b.test.mjs:1');
  r.done();
});

test('假测试：.only 高、断言常量中、零断言中、固定长等待低；辅助函数内断言不误报', () => {
  const r = repo({
    'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md',
    'package.json': JSON.stringify({ devDependencies: { vitest: '1' } }),
    'a.test.ts': [
      "import {it,expect} from 'vitest'",
      "function check(x){ expect(x).toBe(1+0) }",
      "it.only('o',()=>{ expect(add(1,2)).toBe(3) })",
      "it('const',()=>{ expect(true).toBe(true) })",
      "it('none',()=>{ run() })",
      "it('helper',()=>{ check(1) })",
      "it('sleep',async()=>{ await sleep(3000); expect(add(1,1)).toBe(2) })",
      "it.skip('s',()=>{ expect(add(1,1)).toBe(2) })",
    ].join('\n'),
  });
  const a = audit(r.dir);
  assert.equal(find(a, /\.only/)[0].level, '高');
  assert.equal(find(a, /断言常量/)[0].path, 'a.test.ts:4');
  const z = find(a, /零断言/);
  assert.deepEqual(z.map((f) => f.path), ['a.test.ts:5']);
  assert.equal(find(a, /固定长等待/)[0].level, '低');
  assert.equal(find(a, /skip/)[0].level, '低');
  r.done();
});

test('快检脚本混入 e2e 为中', () => {
  const r = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md', 'package.json': JSON.stringify({ scripts: { test: 'vitest run && playwright test' } }) });
  assert.equal(find(audit(r.dir), /混入重测/)[0].level, '中');
  r.done();
});

test('worktree：已合并、没有独立提交、未合入分别识别；只列出不删除', () => {
  const r = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md' });
  const wt = (name) => r.g('worktree', 'add', '-q', '-b', name, join(r.dir, '.worktrees', name));
  const commit = (name, file) => {
    const d = join(r.dir, '.worktrees', name);
    writeFileSync(join(d, file), name);
    execFileSync('git', ['add', '-A'], { cwd: d }); execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', name], { cwd: d });
  };
  wt('empty'); wt('merged'); wt('squashed'); wt('open');
  commit('merged', 'm.txt'); commit('squashed', 's.txt'); commit('open', 'o.txt');
  r.g('merge', '-q', '--no-ff', '-m', 'merge', 'merged');
  r.g('merge', '-q', '--squash', 'squashed'); r.g('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'squash');
  const w = audit(r.dir).findings.filter((f) => /worktree/.test(f.message));
  const state = (b) => w.find((f) => f.message.includes(`worktree ${b}：`))?.message;
  assert.match(state('empty'), /没有独立提交/);
  assert.match(state('merged'), /已合并（普通合并/);
  assert.match(state('squashed'), /squash/);
  assert.match(state('open'), /未合入/);
  assert.ok(w.every((f) => !/^删除/.test(f.advice)));
  r.done();
});

test('--base：集成分支不是默认分支时按它判定，并跳过基线自身的 worktree', () => {
  const r = repo({ 'AGENTS.md': '#', 'CLAUDE.md': '@AGENTS.md' });
  r.g('worktree', 'add', '-q', '-b', 'develop', join(r.dir, '.worktrees', 'develop'));
  const dev = join(r.dir, '.worktrees', 'develop');
  const c = (d, f, m) => { writeFileSync(join(d, f), m); execFileSync('git', ['add', '-A'], { cwd: d }); execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', m], { cwd: d }); };
  c(dev, 'd.txt', 'dev');
  r.g('worktree', 'add', '-q', '-b', 'feat', join(r.dir, '.worktrees', 'feat'), 'develop');
  const feat = join(r.dir, '.worktrees', 'feat');
  c(feat, 'f.txt', 'feat');
  execFileSync('git', ['merge', '-q', '--no-ff', '-m', 'm', 'feat'], { cwd: dev });
  const msg = (res, b) => res.findings.find((f) => f.message.includes(`worktree ${b}：`))?.message;
  const byMain = audit(r.dir);
  assert.match(msg(byMain, 'feat'), /未合入/);
  const byDev = audit(r.dir, { base: 'develop' });
  assert.equal(byDev.base, 'develop');
  assert.match(msg(byDev, 'feat'), /已合并/);
  assert.equal(msg(byDev, 'develop'), undefined);
  assert.throws(() => audit(r.dir, { base: 'nope' }), /基线分支不存在/);
  r.done();
});

test('CLI：结论行格式、退出码 0；--json 可解析；错误参数退出码 2', () => {
  const r = repo({ 'AGENTS.md': 'x'.repeat(11000), 'CLAUDE.md': '@AGENTS.md' });
  const p = spawnSync('node', [SCRIPT, '--project', r.dir], { encoding: 'utf8' });
  assert.equal(p.status, 0);
  const last = p.stdout.trim().split('\n').pop();
  assert.match(last, /^结论：\d+ 项待处理（高 \d+、中 \d+、低 \d+）$/);
  assert.equal(last, '结论：1 项待处理（高 1、中 0、低 0）');
  const j = JSON.parse(spawnSync('node', [SCRIPT, '--project', r.dir, '--json'], { encoding: 'utf8' }).stdout);
  assert.equal(j.conclusion, last);
  assert.equal(spawnSync('node', [SCRIPT, '--project', join(r.dir, 'nope')]).status, 2);
  assert.equal(spawnSync('node', [SCRIPT]).status, 2);
  r.done();
});

test('globToRe 处理 ** 与 {a,b}', () => {
  assert.ok(globToRe('**/*.{test,spec}.ts').test('a/b/c.spec.ts'));
  assert.ok(globToRe('**/*.{test,spec}.ts').test('c.test.ts'));
  assert.ok(!globToRe('tests/**/*.ts').test('src/a.ts'));
});

test('归档匹配只认整段目录名：tmpl-guide.md 不跳过，archive/ 与 CHANGELOG.md 跳过', () => {
  assert.ok(ARCHIVE_RE.test('docs/archive/a.md'));
  assert.ok(ARCHIVE_RE.test('归档/a.md'));
  assert.ok(ARCHIVE_RE.test('docs/deprecated/a.md'));
  assert.ok(ARCHIVE_RE.test('CHANGELOG.md'));
  assert.ok(!ARCHIVE_RE.test('docs/tmpl-guide.md'));
  assert.ok(!ARCHIVE_RE.test('docs/history-of-x.md'));
  assert.ok(!ARCHIVE_RE.test('docs/archive-notes.md'));
});

test('端到端：缺 FEATURES.md 与零断言流程为中；有断言或有功能地图则不报', () => {
  const bad = repo({ 'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md', 'tests/e2e/a.flow.mjs': 'await run();\n', 'tools/playtest-x.mjs': 'console.log(1)\n' });
  const a = audit(bad.dir);
  assert.equal(find(a, /缺 FEATURES\.md/).length, 1);
  assert.deepEqual(find(a, /零断言流程/).map((f) => f.path).sort(), ['tests/e2e/a.flow.mjs:1', 'tools/playtest-x.mjs:1']);
  bad.done();
  const ok = repo({ 'AGENTS.md': '# a\n', 'CLAUDE.md': '@AGENTS.md', 'tests/e2e/FEATURES.md': '# 功能\n', 'tests/e2e/a.flow.mjs': "step('x', () => {});\n", 'levels-1.mjs': "if (!ok) throw new Error('x');\n" });
  const b = audit(ok.dir);
  assert.equal(find(b, /缺 FEATURES\.md|零断言流程/).length, 0);
  ok.done();
});
