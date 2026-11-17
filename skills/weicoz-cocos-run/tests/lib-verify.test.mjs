import test from 'node:test';
import assert from 'node:assert/strict';
import { isTimeoutOnly, shouldRerun, flakyDetail, noTestScriptRow, partialReasons, finalVerdict, judgePlaytest, paginate } from '../scripts/lib-verify.mjs';

test('C1：无 test 脚本不得为通过，结论未验证', () => {
  const rows = [{ name: '类型检查', ok: true }, noTestScriptRow()];
  assert.equal(rows[1].ok, false);
  assert.match(rows[1].detail, /未验证（缺：test 脚本）/);
  const v = finalVerdict(rows);
  assert.equal(v.verdict, 3);
  assert.equal(v.line, '结论：未验证（缺：test 脚本）');
});
test('C2：仅超时类才算；时长断言与其他断言不算', () => {
  assert.equal(isTimeoutOnly('Error: Test timed out in 5000ms'), true);
  assert.equal(isTimeoutOnly('Test timed out\nAssertionError: expected 6000 to be less than or equal to 5000'), false);
  assert.equal(isTimeoutOnly('expected 6000 to be less than 5000'), false);
  assert.equal(isTimeoutOnly('AssertionError: x'), false);
});
test('C2：负载低不重跑', () => {
  assert.equal(shouldRerun('Test timed out', false), false);
  assert.equal(shouldRerun('Test timed out', true), true);
  assert.equal(shouldRerun('assert fail', true), false);
});
test('C2：不稳定明细保留末 5 行', () => {
  const d = flakyDetail('a\nb\nc\nd\ne\nf\ng\n');
  assert.match(d, /不稳定：首轮超时/);
  assert.match(d, /c \| d \| e \| f \| g/);
  assert.doesNotMatch(d, /b \|/);
});
test('C3：--no-release 全通过也是未验证；快检不算缩小', () => {
  const ok = [{ name: 'a', ok: true }];
  assert.deepEqual(partialReasons({ quick: false, noRelease: true, scriptGiven: false }), ['--no-release']);
  assert.deepEqual(partialReasons({ quick: true, noRelease: true, scriptGiven: true }), []);
  const v = finalVerdict(ok, ['--no-release']);
  assert.equal(v.verdict, 3);
  assert.equal(v.line, '结论：未验证（缺：完整全检，本次用了 --no-release）');
  assert.equal(finalVerdict(ok, []).line, '结论：通过');
});
test('失败优先于未验证', () => {
  assert.equal(finalVerdict([{ name: 'x', ok: false }, noTestScriptRow()]).verdict, 1);
});
test('C5：空 log、有失败项、自报 pass 都不可信', () => {
  assert.equal(judgePlaytest({ pass: true, log: [] }).pass, false);
  assert.match(judgePlaytest({ pass: true, log: [] }).error, /没有任何 check/);
  assert.equal(judgePlaytest({ pass: true }).pass, false);
  assert.equal(judgePlaytest({ pass: true, log: [{ ok: true }, { ok: false }] }).pass, false);
  assert.equal(judgePlaytest({ pass: true, log: [{ ok: 1 }] }).pass, false);
  assert.equal(judgePlaytest({ pass: false, log: [{ ok: true }] }).pass, false);
  assert.equal(judgePlaytest({ pass: true, log: [{ ok: true }] }).pass, true);
});
test('C6：超过 12 张分页', () => {
  const f = Array.from({ length: 25 }, (_, i) => i);
  assert.deepEqual(paginate(f).map((p) => p.length), [12, 12, 1]);
  assert.equal(paginate([]).length, 0);
});
