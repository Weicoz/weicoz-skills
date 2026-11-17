import test from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs, mergeConfig, matchIgnore, verdict, parseEnvFile, loadLine, safeName, tailLines, failureLines,
  flowStatus, partialSwitches, partialItem, badIgnorePatterns, cleanIgnore, resolveScript, verifyScriptsChanged, withTimeout } from '../scripts/lib.mjs';

test('parseArgs：全部参数', () => {
  const a = parseArgs(['--project', '/p', '--quick', '--base-url', 'http://x:1', '--script', 'a.mjs', '--script', 'b.mjs', '--no-start']);
  assert.deepEqual(a, { project: '/p', quick: true, baseUrl: 'http://x:1', scripts: ['a.mjs', 'b.mjs'], noStart: true, envFile: null, noChecks: false, base: null });
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
test('failureLines：取失败行去重，没有时退回末尾行', () => {
  const out = 'x\n \x1b[31mFAIL\x1b[0m  a.test.ts > t1\nstack\n FAIL  a.test.ts > t1\nnot ok 2 - t2\nTests 2 failed';
  assert.equal(failureLines(out, 5), 'FAIL  a.test.ts > t1\nnot ok 2 - t2');
  assert.equal(failureLines('a\nb\nc', 2), 'b\nc');
  assert.match(failureLines('FAIL a\nFAIL b\nFAIL c', 2), /另有 1 条失败/);
  assert.equal(failureLines('× retry t3 15000ms\n FAIL  a.test.ts > t1'), 'FAIL  a.test.ts > t1');
  assert.equal(failureLines('× t3 15000ms\nx'), '× t3 15000ms');
});

test('parseArgs：--no-checks', () => {
  assert.equal(parseArgs(['--project', '.', '--no-checks']).noChecks, true);
  assert.equal(parseArgs(['--project', '.']).noChecks, false);
});

test('loadLine / safeName / tailLines', () => {
  assert.match(loadLine(20, 10), /高于核数/);
  assert.doesNotMatch(loadLine(2, 10), /高于核数/);
  assert.equal(safeName('会话 中心/a:b'), '会话-中心-a-b');
  assert.equal(tailLines('1\n2\n3\n', 2), '2\n3');
});

test('flowStatus：失败优先，unverified 不抹掉已有失败，零 step 记失败', () => {
  assert.equal(flowStatus({ stepCount: 2 }), 'pass');
  assert.equal(flowStatus({ unverifiedWhy: '凭据', stepCount: 1 }), 'unverified');
  assert.equal(flowStatus({ unverifiedWhy: '凭据' }), 'unverified');
  assert.equal(flowStatus({ unverifiedWhy: '凭据', stepFailed: true, stepCount: 1 }), 'fail');
  assert.equal(flowStatus({ unverifiedWhy: '凭据', problems: 1, stepCount: 1 }), 'fail');
  assert.equal(flowStatus({ flowError: true, stepCount: 1 }), 'fail');
  assert.equal(flowStatus({ stepCount: 0 }), 'zero');
});

test('partialItem：缩小开关降级为未验证，--base-url/--no-start 不降级', () => {
  const base = { quick: false, noChecks: false, scripts: [] };
  assert.equal(partialItem({ ...base, noStart: true, baseUrl: 'http://x' }), null);
  assert.deepEqual(partialSwitches({ ...base, noChecks: true, scripts: ['a'] }), ['--no-checks', '--script']);
  const it = partialItem({ ...base, quick: true, scripts: ['smoke'] });
  assert.equal(verdict([{ status: 'pass', name: 'a' }, it]).line, '结论：未验证（缺：完整快检，本次用了 --script）');
  assert.equal(verdict([{ status: 'pass', name: 'a' }, it]).code, 3);
  assert.equal(verdict([{ status: 'fail', name: 'a' }, it]).code, 1);
});

test('badIgnorePatterns / cleanIgnore：能匹配空串的模式有害', () => {
  const ig = { console: ['.', 'favicon', '.*', ''], requests: ['a|b', '^$'], pageerror: ['[bad'] };
  assert.deepEqual(badIgnorePatterns({ console: ['.*', 'x'], requests: ['^$'] }), ['console:.*', 'requests:^$']);
  assert.deepEqual(badIgnorePatterns({ console: ['.', 'favicon'], pageerror: ['[bad'] }), ['console:.']);
  assert.deepEqual(badIgnorePatterns({ console: ['favicon\\.ico$'], pageerror: ['[bad'] }), []);
  assert.deepEqual(cleanIgnore({ console: ['.*', 'x'] }), { console: ['x'] });
});

test('resolveScript：路径与流程名都可用', () => {
  const ex = (set) => (f) => set.includes(f);
  assert.equal(resolveScript('smoke', '/p', '/p/t', ex(['/p/t/smoke.flow.mjs'])), '/p/t/smoke.flow.mjs');
  assert.equal(resolveScript('smoke', '/p', '/p/t', ex(['/p/t/smoke.mjs'])), '/p/t/smoke.mjs');
  assert.equal(resolveScript('t/a.flow.mjs', '/p', '/p/t', ex([])), '/p/t/a.flow.mjs');
  assert.equal(resolveScript('x', '/p', '/p/t', ex(['/p/x'])), '/p/x');
});

test('verifyScriptsChanged：只看 verify:* 项', () => {
  const o = JSON.stringify({ scripts: { 'verify:web': 'a', build: 'x' } });
  assert.deepEqual(verifyScriptsChanged(o, JSON.stringify({ scripts: { 'verify:web': 'true', build: 'y' } })), ['verify:web']);
  assert.deepEqual(verifyScriptsChanged(o, JSON.stringify({ scripts: { 'verify:web': 'a', build: 'y' } })), []);
  assert.deepEqual(verifyScriptsChanged('', JSON.stringify({ scripts: { 'verify:web:quick': 'q' } })), ['verify:web:quick']);
});

test('withTimeout：超时 reject，正常返回', async () => {
  assert.equal(await withTimeout(Promise.resolve(1), 1, 'x'), 1);
  await assert.rejects(withTimeout(new Promise(() => {}), 0.05, '流程 a '), /超过 0.05 秒/);
});

test('parseArgs：--base', () => {
  assert.equal(parseArgs(['--project', '.', '--base', 'main']).base, 'main');
});
