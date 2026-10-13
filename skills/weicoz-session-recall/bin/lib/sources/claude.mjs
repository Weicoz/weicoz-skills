// Claude Code 会话源（~/.claude/projects/<编码后的cwd>/<uuid>.jsonl）。
//
// 实测要点（2026-10，90 个会话、147M）：
//  - 同一文件里混着十几种事件：user / assistant / attachment / custom-title /
//    file-history-snapshot / queue-operation / atis-latch / mode / last-prompt …
//    只有 user 与 assistant 承载对话正文，其余按类型直接跳过；
//  - user 的 message.content 可能是字符串，也可能是数组：数组里带 tool_result 的是
//    工具返回（不是人打的字），带 image 的是贴图，只有 text 项才是正文；
//  - isSidechain 为 true 的是子代理的消息，不算用户自己的会话内容；
//  - 注入同样要过滤（skill 目录、斜杠命令包装、compact 续接标记等）。
import { readdir, stat, open } from 'node:fs/promises';
import { join, basename } from 'node:path';
import { homedir } from 'node:os';

import { mapLimit, projectKey, projectLabel, isActive } from '../session-source.mjs';
import { eachJsonLine, countBy, clipTitle, toMs, isAutomatedOrHeadlessText } from '../parse.mjs';

/** 只读文件开头若干字节（判来源用，不解析全文）。 */
async function readHeadBytes(file, maxBytes = 65536) {
  const fh = await open(file, 'r');
  try {
    const buf = Buffer.alloc(maxBytes);
    const { bytesRead } = await fh.read(buf, 0, maxBytes, 0);
    return buf.subarray(0, bytesRead).toString('utf8');
  } catch { return ''; } finally { await fh.close(); }
}

/**
 * 这个会话是不是无头（程序驱动，没有人打过字）。
 * Claude Code 的 SDK 调用会在首条 user 记录里留下 promptSource='sdk' /
 * entrypoint='sdk-cli'；人手打的字是 'typed'，老会话没有这个字段。
 * 同时也排除含「定时任务：」「自动化任务：」「probe.txt」等特征的自动化探针。
 */
export async function isHeadlessFile(file) {
  const head = await readHeadBytes(file);
  if (isAutomatedOrHeadlessText(head)) return true;
  for (const line of head.split('\n')) {
    if (!line.trim()) continue;
    let j;
    try { j = JSON.parse(line); } catch { continue; }
    if (j.type === 'user' && j.message) {
      if (j.promptSource || j.entrypoint) {
        if (j.promptSource === 'sdk' || j.promptSource === 'system' || j.entrypoint === 'sdk-cli') return true;
      }
      const text = typeof j.message === 'string' ? j.message : (j.message.content || '');
      if (isAutomatedOrHeadlessText(typeof text === 'string' ? text : JSON.stringify(text))) return true;
      return false;
    }
  }
  return false;
}

export const META = { id: 'claude', label: 'Claude Code' };

export const CLAUDE_ROOT = process.env.SESSION_RECALL_CLAUDE_ROOT
  || join(homedir(), '.claude', 'projects');

// 只有几行元数据、没有对话的空壳会话。
export const EMPTY_CLAUDE_BYTES = Number(process.env.SESSION_RECALL_CLAUDE_MIN_BYTES ?? 1200);

/** user 正文里属于注入/命令包装的前缀（实测统计得出）。 */
const INJECT_PREFIXES = [
  'Base directory for this skill:',
  '<local-command-caveat>',
  '<local-command-stdout>',
  '<command-message>',
  '<command-name>',
  '<system-reminder>',
  'Another Claude session sent a mess',
  'This session is being continued fr',
  '[Image: source:',
  '[Request interrupted by user',
];

/** 纯斜杠命令（/compact、/clear 之类）不是人写的正文。 */
const SLASH_CMD_RE = /^\/[a-z][a-z-]*$/i;

function isInjected(text) {
  const t = String(text || '').trim();
  if (!t) return true;
  if (SLASH_CMD_RE.test(t)) return true;
  return INJECT_PREFIXES.some((p) => t.startsWith(p));
}

/** message.content → 用户正文（跨形状归一）。 */
function userText(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  if (content.some((c) => c?.type === 'tool_result')) return '';
  return content.filter((c) => c?.type === 'text').map((c) => c.text || '').join('\n');
}

/** message.content → 助手正文（只要 text，丢掉 thinking 与 tool_use）。 */
function assistantText(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content.filter((c) => c?.type === 'text').map((c) => c.text || '').join('\n');
}

/**
 * 快扫：只 stat 文件。
 * known 是中央库水位线，键为 claude:<会话id>。
 */
export async function scanSessions({ known = {}, minBytes = EMPTY_CLAUDE_BYTES } = {}) {
  let dirs;
  try { dirs = await readdir(CLAUDE_ROOT, { withFileTypes: true }); } catch { return []; }
  const files = [];
  for (const d of dirs) {
    if (!d.isDirectory()) continue;
    let inner;
    try { inner = await readdir(join(CLAUDE_ROOT, d.name), { withFileTypes: true }); } catch { continue; }
    for (const f of inner) {
      if (f.isFile() && f.name.endsWith('.jsonl')) files.push(join(CLAUDE_ROOT, d.name, f.name));
    }
  }

  const rows = await mapLimit(files, 24, async (file) => {
    let st;
    try { st = await stat(file); } catch { return null; }
    const id = basename(file).replace(/\.jsonl$/, '');
    const key = `${META.id}:${id}`;
    const prior = known[key];
    // 从没产生过交互的空壳会话不进索引
    if (!prior && st.size < minBytes) return null;
    // 无头会话（SDK 调用）不进索引。已判过的沿用旧结论，不重复读文件。
    let headless = prior?.headless;
    if (headless === undefined) headless = await isHeadlessFile(file);
    const cached = !!prior && (prior.ok || prior.empty || prior.headless)
      && (!prior.headless === !headless)
      && prior.bytes === st.size
      && Math.abs((prior.mtime || 0) - st.mtimeMs) <= 1000;
    return {
      key,
      source: META.id,
      id,
      file,
      bytes: st.size,
      mtimeMs: st.mtimeMs,
      version: 'jsonl',
      isNew: !prior,
      cached,
      active: isActive(st.mtimeMs),
      headless,
      prior: prior || null,
    };
  });
  return rows.filter(Boolean);
}

/** 解出一个会话的摘要素材。 */
export async function parseSession(entry) {
  let cwd = '';
  let customTitle = '';
  let firstTime = 0;
  let lastTime = 0;
  const userMsgs = [];
  const assistantTexts = [];
  const toolNames = [];

  await eachJsonLine(entry.file, (j) => {
    const t = toMs(j.timestamp);
    if (t) { if (!firstTime) firstTime = t; lastTime = t; }
    if (j.cwd && !cwd) cwd = j.cwd;

    if (j.type === 'custom-title') {
      const v = j.customTitle || j.title || j.message?.title;
      if (typeof v === 'string' && v.trim()) customTitle = v.trim();
      return;
    }
    if (j.isSidechain) return; // 子代理的消息不算本会话
    const msg = j.message || {};
    if (j.type === 'user') {
      const text = userText(msg.content);
      if (!isInjected(text)) userMsgs.push(text.trim());
    } else if (j.type === 'assistant') {
      const text = assistantText(msg.content).trim();
      if (text) assistantTexts.push(text);
      for (const c of Array.isArray(msg.content) ? msg.content : []) {
        if (c?.type === 'tool_use') toolNames.push(c.name || '');
      }
    }
  });

  return {
    meta: {
      sessionId: entry.id,
      cwd,
      projectKey: cwd ? projectKey(cwd) : '',
      projectLabel: projectLabel(cwd, META.label),
      originator: 'claude-code',
      cliVersion: '',
    },
    title: customTitle || clipTitle(userMsgs[0] || ''),
    userMsgs,
    assistantTexts,
    tools: countBy(toolNames),
    turns: userMsgs.length,
    firstTime,
    lastTime,
    empty: userMsgs.length === 0,
  };
}

/** 回到这个会话的命令（Claude Code 支持 --resume 指定会话 id）。 */
export function resumeCommand(rec) {
  const cmd = `claude --resume ${rec.id}`;
  return rec.cwd ? `cd ${rec.cwd} && ${cmd}` : cmd;
}
