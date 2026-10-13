// 会话源判定的自测：项目目录名编码 + 水位线变更判定。
// 这两块的规则来自 DSH 的 dsh-session-persistence-jsonl（projectKey / encodeSegment），
// 写死一份预期值，避免某天解析规则变了而索引悄悄漂移。
//
//   node --test bin/lib/session-source.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import {
  ACTIVE_WINDOW_MS, EMPTY_SESSION_BYTES, SESSIONS_ROOT, isActive, isChanged, listProjectDirs,
  listSessionDirs, projectKey, projectLabel, readSessionHeader, currentSource,
} from './session-source.mjs';

test('projectKey 复刻 DSH 编码：分隔符折叠、特殊字符转 ~XXXX', () => {
  assert.equal(projectKey('/Users/developer/File/git/LLM-wiki'),
    '--Users-developer-File-git-LLM-wiki--');
  assert.equal(projectKey('/Users/developer/File/git/ai_geo'),
    '--Users-developer-File-git-ai_geo--');
  // 中文按 UTF-16 code unit 转四位大写十六进制：中 = 4E2D，台 = 53F0
  assert.equal(projectKey('/Users/developer/File/git/LLM-wiki/workspace/projects/AI中台'),
    '--Users-developer-File-git-LLM-wiki-workspace-projects-AI~4E2D~53F0--');
  // 末尾斜杠、连续分隔符都折叠成单个 -
  assert.equal(projectKey('/a/b/'), '--a-b--');
  assert.equal(projectKey('/Users//developer///x'), '--Users-developer-x--');
  // ~ 不是安全字符
  assert.equal(projectKey('/tmp/~/x'), '--tmp-~007E-x--');
  // 根目录 → root
  assert.equal(projectKey('/'), '--root--');
});

test('projectKey 按 251 截断（保持与 DSH 一致的目录名长度上限）', () => {
  const name = projectKey('/' + 'a'.repeat(400));
  assert.equal(name.length, 251 + 4); // 251 + 两侧 --
  assert.ok(name.startsWith('--aaa') && name.endsWith('--'));
});

test('projectLabel 用目录名做显示名', () => {
  assert.equal(projectLabel('/Users/developer/File/git/LLM-wiki'), 'LLM-wiki');
  assert.equal(projectLabel('/Users/developer/File/git/ai-content-ops-wt-fu-01'), 'ai-content-ops-wt-fu-01');
  assert.equal(projectLabel('', '兜底'), '兜底');
});

test('isChanged：没记录、采集失败、换版本、字节或 mtime 变了都算变化', () => {
  const src = { version: 'session.v4.jsonl.zstd', size: 1000, mtimeMs: 5_000_000 };
  assert.equal(isChanged(undefined, src), true);
  assert.equal(isChanged({ ok: false }, src), true);
  // 版本切换即变化：不同版本文件的字节数不可比
  assert.equal(isChanged({ ok: true, version: 'session.jsonl.zstd', bytes: 1000, mtime: 5_000_000 }, src), true);
  assert.equal(isChanged({ ok: true, version: src.version, bytes: 999, mtime: 5_000_000 }, src), true);
  assert.equal(isChanged({ ok: true, version: src.version, bytes: 1000, mtime: 5_060_000 }, src), true);
  // 完全相同、或只有亚秒级抖动 → 未变化
  assert.equal(isChanged({ ok: true, version: src.version, bytes: 1000, mtime: 5_000_000 }, src), false);
  assert.equal(isChanged({ ok: true, version: src.version, bytes: 1000, mtime: 5_000_900 }, src), false);
  // empty（已确认没有人工对话）不是失败，文件没变就不该反复重采
  const em = { ok: false, empty: true, version: src.version, bytes: 1000, mtime: 5_000_000 };
  assert.equal(isChanged(em, src), false);
  assert.equal(isChanged({ ...em, bytes: 1200 }, src), true);
  assert.equal(isChanged({ ...em, version: 'session.jsonl.zstd' }, src), true);
});

test('空种子阈值低于最小的有内容会话', () => {
  assert.equal(EMPTY_SESSION_BYTES, 4000);
  // 实测：空种子目录最大 1308 字节，有内容的会话最小 5984 字节
  assert.ok(EMPTY_SESSION_BYTES > 1308 && EMPTY_SESSION_BYTES < 5984);
});

test('真实会话目录：cwd 正向编码能还原出目录名（编码有损，只能正向验证）', async (t) => {
  if (!existsSync(SESSIONS_ROOT)) return t.skip(`没有 ${SESSIONS_ROOT}`);
  const dirs = (await listProjectDirs()).slice(0, 6);
  assert.ok(dirs.length > 0, '至少应有一个项目目录');
  for (const projectDir of dirs) {
    const sessions = await listSessionDirs(projectDir);
    if (!sessions.length) continue;
    let checked = 0;
    for (const name of sessions.slice(0, 3)) {
      const src = await currentSource(projectDir, name);
      if (!src || src.size < EMPTY_SESSION_BYTES) continue;
      const header = await readSessionHeader(src.path);
      const cwd = header?.data?.cwd || header?.cwd;
      if (!cwd) continue;
      assert.equal(projectKey(cwd), projectDir,
        `cwd ${cwd} 应编码为 ${projectDir}`);
      checked += 1;
    }
    if (checked) await t.test(`  ${projectDir} 校验 ${checked} 个`, () => {});
  }
});

test('isActive：刚被写过的会话算"进行中"，安静下来的不算', () => {
  assert.ok(ACTIVE_WINDOW_MS >= 60_000, '默认窗口至少 1 分钟');
  const now = 10_000_000_000;
  assert.equal(isActive(now - 1_000, now), true, '1 秒前写过 → 进行中');
  assert.equal(isActive(now - 60_000, now), true, '1 分钟前写过 → 进行中');
  assert.equal(isActive(now - (ACTIVE_WINDOW_MS - 1), now), true, '窗口内 → 进行中');
  assert.equal(isActive(now - (ACTIVE_WINDOW_MS + 1), now), false, '超出窗口 → 已安静');
  assert.equal(isActive(now - 3600_000, now), false, '1 小时前 → 已安静');
  assert.equal(isActive(0, now), false, 'mtime 为 0 → 不当作进行中');
  assert.equal(isActive(null, now), false, 'mtime 缺失 → 不当作进行中');
});

test('SOURCES 覆盖 DSH、Codex、Claude Code、Antigravity、Kimi Code 五个 harness', async () => {
  const { SOURCES, sourceById } = await import('./harness.mjs');
  const ids = SOURCES.map((s) => s.META.id);
  assert.deepEqual(ids, ['dsh', 'codex', 'claude', 'agy', 'kimi']);
  assert.equal(sourceById('agy').META.label, 'Antigravity');
  assert.equal(sourceById('kimi').META.label, 'Kimi Code');
});

test('防重入排他锁：获得锁后阻止并发写入，释放后可重新获得', async () => {
  const { acquireLock, releaseLock, isLockActive } = await import('./store.mjs');
  const { tmpdir } = await import('node:os');
  const testLock = join(tmpdir(), `test-recall-lock-${Date.now()}.json`);

  // 确保初态干净
  await releaseLock(testLock);

  const ok1 = await acquireLock(testLock);
  assert.equal(ok1, true, '第一次 acquireLock 应成功');
  assert.equal(await isLockActive(testLock), true, '加锁后 isLockActive 应为 true');

  // 并发再次尝试获取锁，必须被阻止
  const ok2 = await acquireLock(testLock);
  assert.equal(ok2, false, '并发再次 acquireLock 应返回 false 被阻止');

  // 释放锁
  await releaseLock(testLock);
  assert.equal(await isLockActive(testLock), false, '释放后 isLockActive 应为 false');

  // 释放后应能再次成功获取
  const ok3 = await acquireLock(testLock);
  assert.equal(ok3, true, '释放后再次 acquireLock 应成功');
  await releaseLock(testLock);
});

test('isAutomatedOrHeadlessText：精准识别定时任务、自动化任务与探针特征', async () => {
  const { isAutomatedOrHeadlessText } = await import('./parse.mjs');
  assert.equal(isAutomatedOrHeadlessText('Automation: 飞书任务跟踪上午汇报'), true);
  assert.equal(isAutomatedOrHeadlessText('定时任务：运行本机会话摘要采集'), true);
  assert.equal(isAutomatedOrHeadlessText('在当前目录新建文件 probe.txt，内容为 ok'), true);
  assert.equal(isAutomatedOrHeadlessText('创建一个文件 _probe.txt，内容写 ok'), true);
  assert.equal(isAutomatedOrHeadlessText('仅输出 KIMI_NEWAPI_HEADROOM_OK'), true);
  assert.equal(isAutomatedOrHeadlessText('普通用户提问：请帮我写一个 Python 脚本'), false);
  assert.equal(isAutomatedOrHeadlessText(''), false);
  assert.equal(isAutomatedOrHeadlessText(null), false);
});

test('VERSION 常量定义与 --version 命令行输出', async () => {
  const { VERSION } = await import('./version.mjs');
  assert.equal(VERSION, '1.0.0', 'VERSION 应为 1.0.0');

  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const execFileAsync = promisify(execFile);
  const recallPath = join(process.cwd(), 'skills/weicoz-session-recall/bin/recall.mjs');
  const { stdout } = await execFileAsync(process.execPath, [recallPath, '--version']);
  assert.match(stdout, /weicoz-session-recall v1\.0\.0/);
});


