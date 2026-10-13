// Antigravity (AGY) 会话源（~/.gemini/antigravity-cli/brain/<uuid>/.system_generated/logs/transcript.jsonl）。
//
// 实测要点（2026-10，113 个会话）：
//  - 会话目录为 ~/.gemini/antigravity-cli/brain/<uuid>/；
//  - 紧凑会话流在 .system_generated/logs/transcript.jsonl；
//  - 顶层数据库 ~/.gemini/antigravity-cli/conversation_summaries.db 保存会话元数据（title、workspace_uris、parent_conversation_id、nesting_depth 等）；
//  - 备用工作区路径在 ~/.gemini/antigravity-cli/history.jsonl；
//  - 消息事件：
//    - type='USER_INPUT': source='USER_EXPLICIT'，用户发言正文包含在 <USER_REQUEST>...</USER_REQUEST> 中；
//    - type='GENERIC': source='MODEL'，助手回答正文；
//    - type='PLANNER_RESPONSE': tool_calls[].name 工具调用；
//  - 无头判定（isHeadlessFile）：
//    - 子代理会话（search evidence engine、subagent）或首条为系统指示的消息按无头跳过；
//  - 回到会话：
//    - agy --conversation <id>
import { readdir, stat, open, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';

import { mapLimit, projectKey, projectLabel, isActive } from '../session-source.mjs';
import { eachJsonLine, countBy, clipTitle, toMs, isAutomatedOrHeadlessText } from '../parse.mjs';

export const META = { id: 'agy', label: 'Antigravity' };

export const AGY_ROOT = process.env.SESSION_RECALL_AGY_ROOT
  || join(homedir(), '.gemini', 'antigravity-cli');

export const BRAIN_ROOT = join(AGY_ROOT, 'brain');
export const DB_PATH = join(AGY_ROOT, 'conversation_summaries.db');
export const HISTORY_PATH = join(AGY_ROOT, 'history.jsonl');

export const EMPTY_AGY_BYTES = Number(process.env.SESSION_RECALL_AGY_MIN_BYTES ?? 1200);

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
 * Antigravity 的子代理（web search evidence engine、subagent）首条提示词带固定模式，
 * 或首条消息为 SYSTEM_MESSAGE。
 * 同时也排除含「定时任务：」「自动化任务：」「probe.txt」等特征的自动化探针。
 */
export async function isHeadlessFile(file) {
  const head = await readHeadBytes(file, 65536);
  if (!head) return true;
  if (isAutomatedOrHeadlessText(head)) return true;
  for (const line of head.split('\n')) {
    if (!line.trim()) continue;
    let j;
    try { j = JSON.parse(line); } catch { continue; }
    if (j.type === 'SYSTEM_MESSAGE') return true;
    if (j.type === 'USER_INPUT') {
      const content = String(j.content || '');
      if (isAutomatedOrHeadlessText(content)) {
        return true;
      }
      return false;
    }
  }
  return false;
}

/** 从 workspace_uris JSON 字符串解析本地文件系统路径。 */
export function cwdFromWorkspaceUris(urisJson) {
  if (!urisJson) return '';
  try {
    const arr = JSON.parse(urisJson);
    if (!Array.isArray(arr) || !arr.length) return '';
    const first = arr[0];
    if (typeof first !== 'string') return '';
    if (first.startsWith('file://')) {
      return decodeURIComponent(new URL(first).pathname);
    }
    return first;
  } catch {
    return '';
  }
}

/** 读取 conversation_summaries.db 元数据。 */
export function loadAgySummaries(dbPath = DB_PATH) {
  const map = new Map();
  if (!existsSync(dbPath)) return map;
  try {
    const out = execFileSync('sqlite3', [
      dbPath,
      'SELECT conversation_id, title, coalesce(workspace_uris,""), coalesce(parent_conversation_id,""), coalesce(nesting_depth,0), coalesce(last_modified_time,"") FROM conversation_summaries;',
    ], { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
    for (const line of out.split('\n')) {
      if (!line.trim()) continue;
      const [id, title, uris, parentId, depth, mtime] = line.split('|');
      map.set(id, {
        conversation_id: id,
        title: title || '',
        workspace_uris: uris || '[]',
        parent_conversation_id: parentId || '',
        nesting_depth: Number(depth || 0),
        last_modified_time: mtime || '',
      });
    }
  } catch {}
  return map;
}

/** 读取 history.jsonl 中的 workspace 路径作为备用。 */
export async function loadHistoryWorkspaces(historyPath = HISTORY_PATH) {
  const map = new Map();
  if (!existsSync(historyPath)) return map;
  try {
    const text = await readFile(historyPath, 'utf8');
    for (const line of text.split('\n')) {
      if (!line.trim()) continue;
      try {
        const j = JSON.parse(line);
        if (j.conversationId && j.workspace) {
          map.set(j.conversationId, j.workspace);
        }
      } catch {}
    }
  } catch {}
  return map;
}

const INJECT_PREFIXES = [
  '<system-reminder>',
  '<local-command-caveat>',
  '<command-message>',
  '<hindsight_memory>',
  'Automatically retrieved by Hindsight',
];

const SLASH_CMD_RE = /^\/[a-z][a-z-]*$/i;

function cleanUserRequest(content) {
  let text = String(content || '').trim();
  if (!text) return '';
  if (text.includes('<USER_REQUEST>')) {
    const m = text.match(/<USER_REQUEST>([\s\S]*?)<\/USER_REQUEST>/);
    if (m) text = m[1].trim();
  }
  if (!text || SLASH_CMD_RE.test(text)) return '';
  if (INJECT_PREFIXES.some((p) => text.startsWith(p))) return '';
  return text;
}

/**
 * 快扫：只 stat 文件。
 * known 是中央库水位线，键为 agy:<会话id>。
 */
export async function scanSessions({ known = {}, minBytes = EMPTY_AGY_BYTES } = {}) {
  const summaries = loadAgySummaries();
  let dirs;
  try { dirs = await readdir(BRAIN_ROOT, { withFileTypes: true }); } catch { return []; }
  const files = [];
  for (const d of dirs) {
    if (!d.isDirectory()) continue;
    const transcript = join(BRAIN_ROOT, d.name, '.system_generated', 'logs', 'transcript.jsonl');
    files.push({ id: d.name, file: transcript });
  }

  const rows = await mapLimit(files, 24, async ({ id, file }) => {
    let st;
    try { st = await stat(file); } catch { return null; }
    const key = `${META.id}:${id}`;
    const prior = known[key];
    if (!prior && st.size < minBytes) return null;
    let headless = prior?.headless;
    if (headless === undefined) {
      const meta = summaries.get(id);
      if (meta && (meta.nesting_depth > 0 || !!meta.parent_conversation_id)) {
        headless = true;
      } else {
        headless = await isHeadlessFile(file);
      }
    }
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
  const summaries = loadAgySummaries();
  const historyWorkspaces = await loadHistoryWorkspaces();

  const metaItem = summaries.get(entry.id);
  let cwd = cwdFromWorkspaceUris(metaItem?.workspace_uris);
  if (!cwd) {
    cwd = historyWorkspaces.get(entry.id) || '';
  }

  let customTitle = metaItem?.title?.trim() || '';
  let firstTime = 0;
  let lastTime = 0;
  const userMsgs = [];
  const assistantTexts = [];
  const toolNames = [];

  await eachJsonLine(entry.file, (j) => {
    const t = toMs(j.created_at);
    if (t) { if (!firstTime) firstTime = t; lastTime = t; }
    if (j.type === 'USER_INPUT') {
      const u = cleanUserRequest(j.content);
      if (u) userMsgs.push(u);
    } else if (j.type === 'GENERIC' && j.source === 'MODEL') {
      const a = String(j.content || '').trim();
      if (a) assistantTexts.push(a);
    } else if (j.type === 'PLANNER_RESPONSE') {
      for (const tc of j.tool_calls || []) {
        const name = tc.name || tc.function?.name || '';
        if (name) toolNames.push(name);
      }
    }
  });

  return {
    meta: {
      sessionId: entry.id,
      cwd,
      projectKey: cwd ? projectKey(cwd) : '',
      projectLabel: projectLabel(cwd, META.label),
      originator: 'antigravity',
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

/** 回到这个会话的命令。 */
export function resumeCommand(rec) {
  const cmd = `agy --conversation ${rec.id}`;
  return rec.cwd ? `cd ${rec.cwd} && ${cmd}` : cmd;
}
