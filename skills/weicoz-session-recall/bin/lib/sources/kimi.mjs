// Kimi Code 会话源（~/.kimi-code/sessions/wd_<cwd_hash>/session_<uuid>/agents/main/wire.jsonl）。
//
// 实测要点（2026-10，107 个会话）：
//  - 会话目录为 ~/.kimi-code/sessions/wd_<cwd_hash>/session_<uuid>/；
//  - 会话主元数据在 state.json（cwd、createdAt、updatedAt、title 等）；
//  - 备用映射在 ~/.kimi-code/session_index.jsonl（sessionId -> workDir）；
//  - 会话消息流在 agents/main/wire.jsonl；
//  - 消息事件：
//    - type='turn.prompt': input=[{type:'text', text:...}]，用户提问；
//    - type='context.append_loop_event':
//      - event.type='content.part' && part.type='text'：助手文本；
//      - event.type='tool.call' && event.name：工具调用；
//  - 无头判定（isHeadlessFile）：
//    - 首条提示词带 ModLens 解析指示（'You are a vision parsing engine' / 'modlens-work'）、
//      健康探测（'KIMI_NEWAPI_HEADROOM_OK' / '只回复 OK'）或子代理/证据搜索时按无头跳过；
//  - 回到会话：
//    - cd <cwd> && kimi --session <id>
import { readdir, stat, readFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { homedir } from 'node:os';
import { existsSync } from 'node:fs';

import { mapLimit, projectKey, projectLabel, isActive } from '../session-source.mjs';
import { eachJsonLine, countBy, clipTitle, toMs, isAutomatedOrHeadlessText } from '../parse.mjs';

export const META = { id: 'kimi', label: 'Kimi Code' };

export const KIMI_ROOT = process.env.SESSION_RECALL_KIMI_ROOT
  || join(homedir(), '.kimi-code');

export const SESSIONS_ROOT = join(KIMI_ROOT, 'sessions');
export const INDEX_PATH = join(KIMI_ROOT, 'session_index.jsonl');

export const EMPTY_KIMI_BYTES = Number(process.env.SESSION_RECALL_KIMI_MIN_BYTES ?? 1000);

const SLASH_CMD_RE = /^\/[a-z][a-z-]*$/i;

/** 读取 session_index.jsonl 建立 sessionId -> record 映射。 */
export async function loadSessionIndex(indexPath = INDEX_PATH) {
  const map = new Map();
  if (!existsSync(indexPath)) return map;
  try {
    const text = await readFile(indexPath, 'utf8');
    for (const line of text.split('\n')) {
      if (!line.trim()) continue;
      try {
        const j = JSON.parse(line);
        if (j.sessionId) {
          map.set(j.sessionId, j);
        }
      } catch {}
    }
  } catch {}
  return map;
}

/**
 * 这个会话是不是无头（程序驱动，没有人打过字）。
 * 检查首条 turn.prompt 是否命中 headless 模式或自动化/探针模式。
 */
export async function isHeadlessFile(file) {
  let headless = false;
  let checked = false;
  try {
    await eachJsonLine(file, (j) => {
      if (j.type === 'turn.prompt') {
        checked = true;
        const inp = j.input;
        let text = '';
        if (Array.isArray(inp)) {
          text = inp.filter((p) => p && p.type === 'text').map((p) => p.text || '').join('\n');
        } else if (typeof inp === 'string') {
          text = inp;
        }
        if (isAutomatedOrHeadlessText(text)) {
          headless = true;
        }
        return false;
      }
    }, 2_000_000);
  } catch {
    return true;
  }
  return checked ? headless : false;
}

function cleanUserRequest(content) {
  let text = String(content || '').trim();
  if (!text) return '';

  const argBlockMatch = text.match(/ARGUMENTS:\s*([\s\S]*?)<\/(?:kimi-)?skill-loaded>/i);
  if (argBlockMatch) {
    const skillNameMatch = text.match(/<(?:kimi-)?skill-loaded[^>]*name=\"([^\"]+)\"/i);
    const skillPrefix = skillNameMatch ? `/${skillNameMatch[1]} ` : '';
    text = (skillPrefix + argBlockMatch[1].trim()).trim();
  } else {
    const m = text.match(/<(?:kimi-)?skill-loaded[^>]*name=\"([^\"]+)\"[^>]*args=\"([^\"]*)\"/i);
    if (m) {
      const skillName = m[1];
      const args = m[2].trim();
      text = args ? `/${skillName} ${args}` : `/${skillName}`;
    }
  }

  text = text.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '');
  text = text.replace(/<hindsight_knowledge_refresh>[\s\S]*?<\/hindsight_knowledge_refresh>/gi, '');
  text = text.replace(/<hindsight_memory>[\s\S]*?<\/hindsight_memory>/gi, '');
  text = text.replace(/<local-command-caveat>[\s\S]*?<\/local-command-caveat>/gi, '');
  text = text.replace(/<command-message>[\s\S]*?<\/command-message>/gi, '');
  text = text.replace(/User activated the skill[^\n]*\n+/gi, '');
  text = text.replace(/<(?:kimi-)?skill-loaded[\s\S]*?<\/(?:kimi-)?skill-loaded>/gi, '');

  text = text.trim();
  if (!text || SLASH_CMD_RE.test(text)) return '';
  if (HEADLESS_PATTERNS.some((p) => text.includes(p))) return '';
  return text;
}

function cleanAssistantText(content) {
  let text = String(content || '').trim();
  if (!text) return '';
  text = text.replace(/<hindsight_knowledge_refresh>[\s\S]*?<\/hindsight_knowledge_refresh>/gi, '');
  text = text.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '');
  return text.trim();
}

/**
 * 快扫：只 stat 文件。
 * known 是中央库水位线，键为 kimi:<会话id>。
 */
export async function scanSessions({ known = {}, minBytes = EMPTY_KIMI_BYTES } = {}) {
  let wdDirs;
  try {
    wdDirs = await readdir(SESSIONS_ROOT, { withFileTypes: true });
  } catch {
    return [];
  }
  const files = [];
  for (const d of wdDirs) {
    if (!d.isDirectory()) continue;
    const wdPath = join(SESSIONS_ROOT, d.name);
    let sessionDirs;
    try {
      sessionDirs = await readdir(wdPath, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const sd of sessionDirs) {
      if (!sd.isDirectory() || !sd.name.startsWith('session_')) continue;
      const wire = join(wdPath, sd.name, 'agents', 'main', 'wire.jsonl');
      files.push({ id: sd.name, file: wire, sessionDir: join(wdPath, sd.name) });
    }
  }

  const rows = await mapLimit(files, 24, async ({ id, file, sessionDir }) => {
    let st;
    try { st = await stat(file); } catch { return null; }
    const key = `${META.id}:${id}`;
    const prior = known[key];
    if (!prior && st.size < minBytes) return null;
    let headless = prior?.headless;
    if (headless === undefined) {
      let state = null;
      try {
        const text = await readFile(join(sessionDir, 'state.json'), 'utf8');
        state = JSON.parse(text);
      } catch {}
      if (state?.parentSessionId || state?.agents?.main?.parentAgentId || state?.agents?.main?.type === 'sub') {
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
      sessionDir,
      bytes: st.size,
      mtimeMs: st.mtimeMs,
      version: 'wire.jsonl',
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
  const sessionDir = entry.sessionDir || dirname(dirname(entry.file));
  const statePath = join(sessionDir, 'state.json');
  let state = null;
  try {
    const text = await readFile(statePath, 'utf8');
    state = JSON.parse(text);
  } catch {}

  let cwd = state?.cwd || state?.workDir || '';
  if (!cwd) {
    const indexMap = await loadSessionIndex();
    cwd = indexMap.get(entry.id)?.workDir || '';
  }

  let customTitle = (state?.title && state.title !== 'New Session') ? state.title.trim() : '';
  if (customTitle && HEADLESS_PATTERNS.some((p) => customTitle.includes(p))) {
    customTitle = '';
  }

  let firstTime = toMs(state?.createdAt) || 0;
  let lastTime = toMs(state?.updatedAt) || 0;
  const userMsgs = [];
  const assistantTexts = [];
  const toolNames = [];

  await eachJsonLine(entry.file, (j) => {
    if (j.type === 'turn.prompt') {
      const t = toMs(j.time);
      if (t) { if (!firstTime) firstTime = t; lastTime = Math.max(lastTime, t); }
      const inp = j.input;
      let rawText = '';
      if (Array.isArray(inp)) {
        rawText = inp.filter((p) => p && p.type === 'text').map((p) => p.text || '').join('\n');
      } else if (typeof inp === 'string') {
        rawText = inp;
      }
      const u = cleanUserRequest(rawText);
      if (u) userMsgs.push(u);
    } else if (j.type === 'context.append_loop_event') {
      const ev = j.event;
      if (!ev) return;
      const t = toMs(ev.time || j.time);
      if (t) { if (!firstTime) firstTime = t; lastTime = Math.max(lastTime, t); }
      if (ev.type === 'content.part' && ev.part?.type === 'text') {
        const a = cleanAssistantText(ev.part.text);
        if (a) assistantTexts.push(a);
      } else if (ev.type === 'tool.call') {
        if (ev.name) toolNames.push(ev.name);
      }
    }
  });

  return {
    meta: {
      sessionId: entry.id,
      cwd,
      projectKey: cwd ? projectKey(cwd) : '',
      projectLabel: projectLabel(cwd, META.label),
      originator: 'kimi-code',
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
  const cmd = `kimi --session ${rec.id}`;
  return rec.cwd ? `cd ${rec.cwd} && ${cmd}` : cmd;
}
