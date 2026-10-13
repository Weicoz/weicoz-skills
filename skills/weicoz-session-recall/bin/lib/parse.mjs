// 大会话文件的解析工具。
//
// Codex 与 Claude Code 的会话文件是单行 JSONL，实测有 35MB / 51MB 的样本——
// 整文件读进内存不划算，而且摘要只需要用户消息与助手正文，
// 所以这里用流式逐行读，并允许调用方在中途返回 false 收工。
import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';

/** 单个会话最多读入多少字符（防止个别巨型会话把内存吃光）。 */
export const READ_LIMIT_CHARS = Number(process.env.SESSION_RECALL_READ_LIMIT ?? 40_000_000);

/**
 * 逐行读取 JSONL，对每个可解析的对象调用 onLine。
 * onLine 返回 false 表示提前结束（已经拿够需要的内容）。
 * 返回 { chars, stopped }：stopped 为 true 表示是被 onLine 叫停的，不是读完了。
 */
export async function eachJsonLine(file, onLine, maxChars = READ_LIMIT_CHARS) {
  const stream = createReadStream(file, { encoding: 'utf8' });
  const rl = createInterface({ input: stream, crlfDelay: Infinity });
  let chars = 0;
  let stopped = false;
  try {
    for await (const line of rl) {
      chars += line.length + 1;
      if (chars > maxChars) break;
      if (line.charCodeAt(0) !== 0x7b /* { */) continue;
      let j;
      try { j = JSON.parse(line); } catch { continue; }
      if (onLine(j) === false) { stopped = true; break; }
    }
  } finally {
    rl.close();
    stream.destroy();
  }
  return { chars, stopped };
}

/** 按出现次数排序的工具名计数。 */
export function countBy(names) {
  const m = {};
  for (const name of names) {
    if (!name) continue;
    m[name] = (m[name] || 0) + 1;
  }
  return m;
}

/** 把文本压成单行标题，超长截断（会话没有自带标题时用它兜底）。 */
export function clipTitle(text, max = 56) {
  const t = String(text || '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

/** ISO 时间戳或秒/毫秒数字 → 毫秒；拿不准就返回 0。 */
export function toMs(value) {
  if (!value) return 0;
  if (typeof value === 'number') return value < 1e12 ? value * 1000 : value;
  const t = Date.parse(value);
  return Number.isFinite(t) ? t : 0;
}

/** 跨 harness 通用的无头、自动化任务与子代理特征词。 */
export const AUTOMATED_OR_HEADLESS_PATTERNS = [
  'Automation:',
  'Automation ID:',
  '定时任务：',
  '定时任务:',
  '自动化任务：',
  '自动化任务:',
  '[定时任务]',
  '[自动化任务]',
  'probe.txt',
  '_probe.txt',
  '健康探测',
  '健康检查',
  '创建探测文件',
  'KIMI_NEWAPI_HEADROOM_OK',
  'modlens-work',
  '只回复 OK',
  'You are a search evidence engine',
  'search evidence engine',
  'You are a subagent',
  '你是一个子代理',
  '子代理任务',
  'agent-swarm',
  'You are a delegated agent',
];

/** 检查文本是否命中任何自动化任务、定时任务或无头特征。 */
export function isAutomatedOrHeadlessText(text) {
  if (!text || typeof text !== 'string') return false;
  for (const pattern of AUTOMATED_OR_HEADLESS_PATTERNS) {
    if (text.includes(pattern)) return true;
  }
  return false;
}
