// 会话源文件的单一事实来源：决定"属于哪个项目""读哪个版本""是否变化"。
//
// 所有入口（digest / recall / status）必须共用这里的规则：
//  - 版本优先级写错一格（旧版排前面）会读到过期字节，把已摘要会话误判成"永久待摘要"；
//  - projectKey 编码与 DSH 不一致会定位到别的项目目录，看到的是别人的会话。
// 改完跑：node --test bin/lib/session-source.test.mjs
import { readdir, stat } from 'node:fs/promises';
import { join, basename } from 'node:path';
import { homedir } from 'node:os';
import { spawn } from 'node:child_process';

/** DSH 会话库根目录（所有项目都在这里，每个项目一个目录）。 */
export const SESSIONS_ROOT = process.env.SESSION_RECALL_SESSIONS_ROOT
  || join(homedir(), '.dsh', 'sessions');

// 优先级从新到旧：同一会话可能同时存在多个版本文件，只有最高版本是最新数据。
// v2 曾漏掉过：2026-10-10 清点空会话时发现 5 个只带 session.v2.jsonl.zstd 的老会话
// （「企业AI中台定位与行动指南」「PHP接入银行支付接口」「农业银行收款流水汇总核对」等，
// 共约 1.7MB、13 条用户消息）既没匹配 v4/v3、也不叫 session.jsonl.zstd，从未被扫到。
// 少列一个版本就是静默漏掉一批会话 —— 改动这里务必对照磁盘上的实际文件名。
export const VERSION_ORDER = ['session.v4.jsonl.zstd', 'session.v3.jsonl.zstd', 'session.v2.jsonl.zstd', 'session.jsonl.zstd'];

// 从未产生对话的空种子目录压缩后都在 1.3KB 以内
// （实测 1346 个空目录 ≤1308 字节，119 个有内容会话最小 5984 字节）。
export const EMPTY_SESSION_BYTES = 4000;

const SEPARATORS = '/\\:';
const SAFE = /[A-Za-z0-9._-]/;

/**
 * cwd → DSH 项目目录名。
 * 复刻 @deepseek-ai/dsh-session-persistence-jsonl 的 projectKey()：
 *  - 路径分隔符（/ \ :）折叠为单个 '-'（连续多个只出一个）；
 *  - [A-Za-z0-9._-] 且非 '~' 的字符原样保留；
 *  - 其余字符（含中文、'~'）编码为 '~' + 四位大写十六进制码元；
 *  - 结果去掉前导 '-'，空则用 'root'，截断到 251，最后用 '--' 包起来。
 * 该编码有损（分隔符被折叠、超长被截断），不可反解，
 * 所以项目的显示名必须从会话头里的 cwd 读。
 */
export function projectKey(cwd) {
  let out = '';
  let pendingSep = false;
  for (let i = 0; i < cwd.length; i++) {
    const ch = cwd[i];
    if (SEPARATORS.includes(ch)) { pendingSep = true; continue; }
    if (pendingSep) { out += '-'; pendingSep = false; }
    out += (ch !== '~' && SAFE.test(ch))
      ? ch
      : `~${cwd.charCodeAt(i).toString(16).toUpperCase().padStart(4, '0')}`;
  }
  return `--${(out.replace(/^-+/, '') || 'root').slice(0, 251)}--`;
}

/** 项目显示名：cwd 的最后一段；拿不到 cwd 时退回目录名。 */
export function projectLabel(cwd, fallback = '') {
  if (!cwd) return fallback;
  return basename(cwd) || cwd;
}

/** 当前工作目录对应的项目目录名（skill 被调用时用来优先检索"这个项目"）。 */
export function currentProjectKey(cwd = process.cwd()) {
  return projectKey(cwd);
}

/** 列出所有项目目录名。 */
export async function listProjectDirs() {
  try {
    const entries = await readdir(SESSIONS_ROOT, { withFileTypes: true });
    return entries.filter((d) => d.isDirectory()).map((d) => d.name);
  } catch { return []; }
}

/** 列出某个项目下的会话目录名。 */
export async function listSessionDirs(projectDir) {
  try {
    const entries = await readdir(join(SESSIONS_ROOT, projectDir), { withFileTypes: true });
    return entries.filter((d) => d.isDirectory()).map((d) => d.name);
  } catch { return []; }
}

/** 会话原始目录的绝对路径（写进详情，供人工查看原始数据）。 */
export function sessionDirPath(projectDir, sessionDir) {
  return join(SESSIONS_ROOT, projectDir, sessionDir);
}

/** 取会话的当前源文件：{ version, path, size, mtimeMs }，无文件时返回 null。 */
export async function currentSource(projectDir, sessionDir) {
  for (const version of VERSION_ORDER) {
    const path = join(SESSIONS_ROOT, projectDir, sessionDir, version);
    try {
      const st = await stat(path);
      return { version, path, size: st.size, mtimeMs: st.mtimeMs };
    } catch { /* 试下一个版本 */ }
  }
  return null;
}

/**
 * 会话相对摘要记录是否有变化。
 * 版本切换本身也算变化——旧记录的字节数来自另一个文件，不可比。
 */
export function isChanged(rec, src) {
  if (!rec) return true;
  // empty = 已确认"没有人工对话"的会话（Codex 的自动化执行最常见）：不是失败，
  // 不必反复重试，只有文件本身变了才值得重新看一遍。
  if (!rec.ok && !rec.empty) return true;
  if (rec.version !== src.version) return true;
  if (rec.bytes !== src.size) return true;
  return Math.abs((rec.mtime || 0) - src.mtimeMs) > 1000;
}

/** 限制并行度的 map（全机扫描要 stat 数千个文件，串行会拖慢到秒级）。 */
export async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    for (;;) {
      const i = cursor++;
      if (i >= items.length) return;
      out[i] = await fn(items[i], i);
    }
  });
  await Promise.all(workers);
  return out;
}

/** 解压会话文件；超过 maxBytes 就掐掉（异常巨型会话不值得为摘要读满）。 */
export function zstdDecode(file, maxBytes = 12_000_000) {
  return new Promise((resolve) => {
    const p = spawn('zstd', ['-dc', file]);
    const chunks = [];
    let total = 0;
    let done = false;
    p.stdout.on('data', (c) => {
      if (done) return;
      chunks.push(c);
      total += c.length;
      if (total > maxBytes) { done = true; p.kill(); }
    });
    p.on('close', () => { if (!done) done = true; resolve(Buffer.concat(chunks).toString('utf8')); });
    p.on('error', () => resolve(''));
  });
}

/**
 * 只读会话开头的 session 事件（含 cwd / createdAt）。
 * 给 maxBytes 上限，避免为拿一个字段解压十几兆的会话。
 */
export async function readSessionHeader(srcPath) {
  const text = await zstdDecode(srcPath, 300_000);
  for (const line of text.split('\n')) {
    if (!line.startsWith('{')) continue;
    try {
      const j = JSON.parse(line);
      if (j.type === 'session') return j;
    } catch { /* 末行可能被截断 */ }
  }
  return null;
}

/**
 * 距上次写入不到这么久，就认为会话还在进行中。
 * 这类会话不值得采：摘要生成完就已经过时，而且它通常正是用户此刻正在用的那个会话——
 * 每次检索都等它重新摘要一次，是"调用即采集"变慢的唯一原因。设 0 可关闭该判断。
 */
export const ACTIVE_WINDOW_MS = Number(process.env.SESSION_RECALL_ACTIVE_MS ?? 10 * 60 * 1000);

/** 会话是否"正在进行中"（刚被写过，八成还在继续）。 */
export function isActive(mtimeMs, now = Date.now()) {
  return ACTIVE_WINDOW_MS > 0 && now - Number(mtimeMs || 0) < ACTIVE_WINDOW_MS;
}

/**
 * 快扫：找出哪些会话需要（重新）生成摘要。
 * 只 stat 源文件，不解压、不调用模型——这是"调用 skill 顺手采集"能秒级响应"无变更"的原因。
 * sessions 是中央库里的水位线（键为 <项目目录>/<会话目录>）。
 */
export async function pendingSessions(sessions = {}, { projectFilter = null, minBytes = EMPTY_SESSION_BYTES } = {}) {
  const projects = await listProjectDirs();
  const out = [];
  for (const projectDir of projects) {
    if (projectFilter && !projectDir.includes(projectFilter)) continue;
    const dirs = await listSessionDirs(projectDir);
    const rows = await mapLimit(dirs, 24, async (name) => {
      const src = await currentSource(projectDir, name);
      if (!src) return null;
      const key = `${projectDir}/${name}`;
      const prior = sessions[key];
      // 空种子目录（点开过但没说话的）不算待处理
      if (!prior && src.size < minBytes) return null;
      if (prior && !isChanged(prior, src)) return null;
      return { key, projectDir, name, size: src.size, mtimeMs: src.mtimeMs, isNew: !prior, changed: !!prior };
    });
    for (const r of rows) if (r) out.push(r);
  }
  return out;
}
