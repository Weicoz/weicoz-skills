import test from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs, mergeConfig, matchIgnore, verdict, parseEnvFile, loadLine, safeName, tailLines } from '../scripts/lib.mjs';

test('parseArgs：全部参数', () => {
  const a = parseArgs(['--project', '/p', '--quick', '--base-url', 'http://x:1', '--script', 'a.mjs', '--script', 'b.mjs', '--no-start']);
  assert.deepEqual(a, { project: '/p', quick: true, baseUrl: 'http://x:1', scripts: ['a.mjs', 'b.mjs'], noStart: true, envFile: null });
});
test('parseArgs：缺 project、未知参数、缺值都报错', () => {
  assert.throws(() => parseArgs([]), /--project/);
  assert.throws(() => parseArgs(['--project', 'p', '--x']), /未知参数/);
  assert.throws(() => parseArgs(['--project']), /缺少值/);
  assert.throws(() => parseArgs(['--project', '--quick']), /缺少值/);
});
test('mergeConfig：默认值、子键合并、命令行覆盖', () => {
  const c = mergeConfig({ baseUrl: 'http://a:3700/', ignore: { console: ['x'] }, checks: { quick: [{ name: 'n', cmd: 'true' }] } }, {});
  assert.equal(c.baseUrl, 'http://a:3700');
  assert.deepEqual(c.ignore, { console: ['x'], pageerror: [], requests: [] });
  assert.equal(c.checks.full.length, 0);
  assert.equal(c.viewports.length, 2);
  assert.equal(c.flows, 'tests/e2e/*.flow.mjs');
  const d = mergeConfig({ start: { command: 'x' }, viewports: [] }, { baseUrl: 'http://b', noStart: true });
  assert.equal(d.baseUrl, 'http://b');
  assert.equal(d.start, null);
  assert.equal(d.viewports.length, 2);
});
test('matchIgnore：正则、子串退化、空列表', () => {
  assert.ok(matchIgnore('GET 404 http://h/favicon.ico', ['favicon\\.ico$']));
  assert.ok(matchIgnore('a[b', ['[b'])); // 非法正则按子串
  assert.ok(!matchIgnore('boom', []));
  assert.ok(!matchIgnore('boom', ['^x']));
});
test('verdict：通过 / 不通过 / 未验证，失败优先', () => {
  assert.deepEqual(verdict([{ status: 'pass', name: 'a' }]), { code: 0, line: '结论：通过' });
  assert.deepEqual(verdict([]), { code: 0, line: '结论：通过' });
  assert.deepEqual(verdict([{ status: 'fail', name: 'a' }, { status: 'fail', name: 'b' }, { status: 'unverified', name: 'c' }]), { code: 1, line: '结论：不通过（失败：a、b）' });
  assert.deepEqual(verdict([{ status: 'pass', name: 'a' }, { status: 'unverified', name: 'c', missing: '服务' }, { status: 'unverified', name: 'd', missing: '服务' }]), { code: 3, line: '结论：未验证（缺：服务）' });
});
test('parseEnvFile：引号、注释、export', () => {
  const e = parseEnvFile('# c\nA=1\nexport B="x y"\nC=\'z\'\nD=v # 注释\nbad line\n');
  assert.deepEqual(e, { A: '1', B: 'x y', C: 'z', D: 'v' });
});
test('loadLine / safeName / tailLines', () => {
  assert.match(loadLine(20, 10), /高于核数/);
  assert.doesNotMatch(loadLine(2, 10), /高于核数/);
  assert.equal(safeName('会话 中心/a:b'), '会话-中心-a-b');
  assert.equal(tailLines('1\n2\n3\n', 2), '2\n3');
});
