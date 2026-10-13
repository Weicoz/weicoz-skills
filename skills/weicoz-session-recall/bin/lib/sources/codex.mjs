// Codex 会话源（~/.codex/sessions/YYYY/MM/DD/rollout-<时间>-<uuid>.jsonl）。
//
// 实测要点（2026-10，247 个会话、2.5G）：
//  - 事件骨架：session_meta(1) / event_msg(数千) / response_item(数千) / turn_context(轮数)；
//  - 消息只出现在 response_item：{payload.type:'message', payload.role, payload.content[].text}；
//  - role 有 developer / user / assistant，developer 全是系统注入，整条跳过；
//  - role='user' 里混着 AGENTS.md、environment_context 等注入，必须按前缀剔除，
//    否则摘要会变成"用户的每句话都是 AGENTS.md 的规则"；
//  - originator 为 codex_exec 的多是自动化执行（无人工对话），codex-tui 才是交互会话。
import { readdir, stat, open } from 'node:fs/promises';
import { join, basename } from 'node:path';
import { homedir } from 'node:os';

import { mapLimit, projectKey, projectLabel, isActive } from '../session-source.mjs';
import { eachJsonLine, countBy, clipTitle, toMs, isAutomatedOrHeadlessText } from '../parse.mjs';

/** 只读文件开头若干字节（判来源用，不解析全文）。 */
async function readHeadBytes(file, maxBytes = 8192) {
  const fh = await open(file, 'r');
  try {
    const buf = Buffer.alloc(maxBytes);
    const { bytesRead } = await fh.read(buf, 0, maxBytes, 0);
    return buf.subarray(0, bytesRead).toString('utf8');
  } catch { return ''; } finally { await fh.close(); }
}

/**
 * 这个会话是不是无头（程序驱动，没有人打过字）。
 * Codex 的 codex_exec 是自动化调用入口；子代理与自动化任务（Automation: / 定时任务等）
 * 也一并判定为无头会话排除出索引。
 */
export async function isHeadlessFile(file) {
  let isHeadless = false;
  await eachJsonLine(file, (j) => {
    if (j.type === 'session_meta') {
      const orig = j.payload?.originator;
      if (orig === 'codex_exec' || orig === 'subagent') {
        isHeadless = true;
        return false;
      }
    } else if (j.type === 'response_item') {
      const p = j.payload || {};
      if (p.type === 'message' && p.role === 'user') {
        const text = (p.content || []).map((c) => c?.text || '').join('\n');
        if (!isInjectedUserText(text)) {
          if (isAutomatedOrHeadlessText(text)) {
            isHeadless = true;
          }
          return false;
        }
      }
    }
  }, 1000000);
  return isHeadless;
}

export const META = { id: 'codex', label: 'Codex' };

export const CODEX_ROOT = process.env.SESSION_RECALL_CODEX_ROOT
  || join(homedir(), '.codex', 'sessions');

// 只有一条 session_meta、还没产生交互的空壳会话（实测最小的不足 1KB）。
export const EMPTY_CODEX_BYTES = Number(process.env.SESSION_RECALL_CODEX_MIN_BYTES ?? 1200);

// rollout-<ISO时间>-<uuid>.jsonl，也有 rollout-<ISO>-<uuid>_<uuid>.jsonl 这种变体（取最后一段）
const ROLLOUT_RE = /^rollout-.*[-_]([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jsonl$/;

/** role='user' 里属于系统注入的内容前缀（实测统计得出的白名单，不是猜的）。 */
const INJECT_PREFIXES = [
  '# AGENTS.md instructions for',
  '<environment_context>',
  '<user_instructions>',
  '<send_user_message_question_reply>',
  '<turn_context>',
  '<permissions',
  '<image name=',
  '</image>',
  'You are performing a one-time structur',
];

/** 这段 user 文本是不是系统注入（不是人打的字）。 */
export function isInjectedUserText(text) {
  const t = String(text || '').trim();
  if (!t) return true;
  return INJECT_PREFIXES.some((p) => t.startsWith(p));
}

/**
 * 快扫：只 stat 文件，不解压、不解析。
 * known 是中央库水位线（键为 codex:<会话id>）。
 * 返回有摘要价值的全部会话，每项自带 cached / active 标记，由调用方决定是否重新摘要。
 */
export async function scanSessions({ known = {}, minBytes = EMPTY_CODEX_BYTES } = {}) {
  let rel;
  try { rel = await readdir(CODEX_ROOT, { recursive: true }); } catch { return []; }
  const paths = rel.filter((f) => f.endsWith('.jsonl')).map((f) => join(CODEX_ROOT, f));

  const rows = await mapLimit(paths, 24, async (file) => {
    let st;
    try { st = await stat(file); } catch { return null; }
    const name = basename(file);
    const m = ROLLOUT_RE.exec(name);
    const id = m ? m[1] : name.replace(/\.jsonl$/, '');
    const key = `${META.id}:${id}`;
    const prior = known[key];
    // 从没产生过交互的空壳会话不进索引
    if (!prior && st.size < minBytes) return null;
    // 无头会话（codex_exec 自动化执行）不进索引。已判过的沿用旧结论，不重复读文件。
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
  let meta = null;
  let turns = 0;
  let firstTime = 0;
  let lastTime = 0;
  const userMsgs = [];
  const assistantTexts = [];
  const toolNames = [];

  await eachJsonLine(entry.file, (j) => {
    const t = toMs(j.timestamp);
    if (t) { if (!firstTime) firstTime = t; lastTime = t; }
    switch (j.type) {
      case 'session_meta':
        meta = j.payload || null;
        return;
      case 'turn_context':
        turns++;
        return;
      case 'response_item': break;
      default: return;
    }
    const p = j.payload || {};
    if (p.type === 'message' && p.role === 'user') {
      const text = (p.content || []).map((c) => c?.text || '').join('\n');
      if (!isInjectedUserText(text)) userMsgs.push(text.trim());
    } else if (p.type === 'message' && p.role === 'assistant') {
      const text = (p.content || []).map((c) => c?.text || '').join('\n').trim();
      if (text) assistantTexts.push(text);
    } else if (p.type === 'custom_tool_call' || p.type === 'function_call') {
      toolNames.push(p.name || '');
    }
  });

  const cwd = meta?.cwd || '';
  return {
    meta: {
      sessionId: meta?.session_id || entry.id,
      cwd,
      projectKey: cwd ? projectKey(cwd) : '',
      projectLabel: projectLabel(cwd, META.label),
      originator: meta?.originator || '',
      cliVersion: meta?.cli_version || '',
    },
    // Codex 不存标题，用第一条真实用户消息兜底
    title: clipTitle(userMsgs[0] || ''),
    userMsgs,
    assistantTexts,
    tools: countBy(toolNames),
    turns,
    firstTime,
    lastTime,
    empty: userMsgs.length === 0,
  };
}

/** 回到这个会话的命令（Codex 官方支持按 session id 恢复）。 */
export function resumeCommand(rec) {
  const cmd = `codex resume ${rec.id}`;
  return rec.cwd ? `cd ${rec.cwd} && ${cmd}` : cmd;
}
