// DSH 会话源适配器：把 session-source.mjs 里的 DSH 规则
// 包成与 Codex / Claude Code 相同的接口（scanSessions / parseSession / resumeCommand）。
//
// DSH 的会话是"目录 + 多版本压缩文件"，与其他两个 harness 的"单文件 JSONL"不同，
// 但对外暴露的形状必须一致，否则 digest / recall / status 就要为每个源写一套分支。
import { join } from 'node:path';
import { readFileSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';

import {
  SESSIONS_ROOT, EMPTY_SESSION_BYTES, listProjectDirs, listSessionDirs,
  currentSource, sessionDirPath, isActive, zstdDecode, projectLabel, mapLimit,
} from '../session-source.mjs';
import { isAutomatedOrHeadlessText } from '../parse.mjs';

export const META = { id: 'dsh', label: 'DSH' };

let _scheduledIds = null;
/** 读取 DSH 侧栏自动化任务（schedule.json）绑定的所有会话 ID。 */
export function getScheduledSessionIds() {
  if (_scheduledIds) return _scheduledIds;
  try {
    const p = join(homedir(), '.dsh', 'storages', 'schedule.json');
    if (!existsSync(p)) return new Set();
    const d = JSON.parse(readFileSync(p, 'utf8'));
    _scheduledIds = new Set(Object.values(d?.tables?.tasks || {}).map((t) => t.sessionId).filter(Boolean));
  } catch {
    _scheduledIds = new Set();
  }
  return _scheduledIds;
}

// 兼容 v3（message 嵌套在 data 下）与 v4（message 在顶层）
const msgOf = (j) => j.message || j.data?.message || null;

function textOf(content) {
  if (!content) return '';
  return (Array.isArray(content) ? content : [content])
    .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
    .map((c) => c.text)
    .join('\n')
    .trim();
}

/**
 * 只解压文件开头读会话头（不解压整个会话），用来判断无头会话。
 * 实测：187 个有内容的 DSH 会话里，会话头 `origin` 只有两种取值 —— null（172 个，人开的）
 * 和 subagent（15 个，AI 派生的子代理）；后者 `delegationDepth` 为 1，前者为 0。
 * 这些子代理会话的首条 user 消息是 AI 写的任务书（"你是一个只读调研 agent…"），
 * 不是人打的字，所以按 no-head 排除出索引（同 Codex 的 codex_exec、Claude 的 SDK 会话）。
 * 另外 21 个会话有 parentSession 但 origin=null、delegationDepth=0 —— 那是从旧会话
 * 派生/分支出来的新会话，里面是真人对话，不能排除。
 * 同时也排除含「定时任务：」「自动化任务：」「probe.txt」等特征的自动化探针。
 */
export async function isHeadlessFile(file) {
  const text = await zstdDecode(file, 65536);
  if (isAutomatedOrHeadlessText(text)) return true;
  const nl = text.indexOf('\n');
  const first = nl === -1 ? text : text.slice(0, nl);
  let head;
  try { head = JSON.parse(first); } catch { return false; }
  if (!head || head.type !== 'session') return false;
  return head.origin === 'subagent' || Number(head.delegationDepth || 0) > 0;
}

/**
 * 快扫：只 stat 各版本文件，不解压。
 * known 是中央库水位线（键为 dsh:<项目目录>/<会话目录>）。
 * 返回有摘要价值的全部会话，每项自带 cached / headless / active 标记。
 */
export async function scanSessions({ known = {}, minBytes = EMPTY_SESSION_BYTES } = {}) {
  const scheduledIds = getScheduledSessionIds();
  const projects = await listProjectDirs();
  const out = [];
  for (const projectDir of projects) {
    const dirs = await listSessionDirs(projectDir);
    const rows = await mapLimit(dirs, 24, async (name) => {
      const src = await currentSource(projectDir, name);
      if (!src) return null;
      const key = `${META.id}:${projectDir}/${name}`;
      const prior = known[key];
      // 点开过但没说过话的空种子目录不进索引
      if (!prior && src.size < minBytes) return null;
      // 定时任务或无头会话（AI 派生的子代理/自动化任务）：排除出索引
      let headless = prior?.headless;
      if (scheduledIds.has(name)) {
        headless = true;
      } else if (headless === undefined) {
        headless = await isHeadlessFile(src.path);
      }
      const cached = !!prior && (prior.ok || prior.empty || prior.headless)
        && (!prior.headless === !headless)
        && prior.version === src.version
        && prior.bytes === src.size
        && Math.abs((prior.mtime || 0) - src.mtimeMs) <= 1000;
      return {
        key,
        source: META.id,
        id: name,
        file: src.path,
        dir: sessionDirPath(projectDir, name),
        project: projectDir,
        bytes: src.size,
        mtimeMs: src.mtimeMs,
        version: src.version,
        isNew: !prior,
        cached,
        headless,
        active: isActive(src.mtimeMs),
        prior: prior || null,
      };
    });
    for (const r of rows) if (r) out.push(r);
  }
  return out;
}

/** 解出一个会话的摘要素材（DSH 是压缩 JSONL，先解压再逐行解析）。 */
export async function parseSession(entry) {
  const text = await zstdDecode(entry.file);
  const out = {
    meta: null, title: '', userMsgs: [], assistantTexts: [], tools: {},
    firstTime: 0, lastTime: 0, turns: 0,
  };
  for (const line of text.split('\n')) {
    if (!line) continue;
    let j;
    try { j = JSON.parse(line); } catch { continue; }

    if (j.type === 'session') { out.meta = j.data || j; continue; }
    if (j.time) {
      // time 可能是秒或毫秒，混着算会让排序彻底错乱（曾把 8 月的会话排到 10 月前面）
      const t = j.time < 1e12 ? j.time * 1000 : j.time;
      if (!out.firstTime || t < out.firstTime) out.firstTime = t;
      if (!out.lastTime || t > out.lastTime) out.lastTime = t;
    }
    if (j.type === 'turn/start') { out.turns++; continue; }
    if (j.type === 'session/title') {
      const t = j.data?.title || j.title;
      if (t) out.title = t;
      continue;
    }
    if (j.type === 'user/message') {
      // 只认真人输入：source.kind 为 user，其余是系统注入（技能目录、运行时上下文、时间戳等）
      if (j.data?.source?.kind !== 'user') continue;
      const t = textOf(j.data?.content || j.content);
      if (t) out.userMsgs.push(t);
      continue;
    }
    if (j.type === 'assistant/message') {
      const t = textOf(msgOf(j)?.content);
      if (t) out.assistantTexts.push(t);
      continue;
    }
    if (j.type === 'tool/call') {
      const name = j.data?.name || j.name || j.data?.toolName || j.toolName;
      if (name) out.tools[name] = (out.tools[name] || 0) + 1;
    }
  }

  const cwd = out.meta?.cwd || '';
  return {
    meta: {
      sessionId: out.meta?.id || entry.id,
      cwd,
      projectKey: entry.project || '',
      projectLabel: projectLabel(cwd, entry.project || ''),
      originator: out.meta?.agentPreset || '',
      cliVersion: out.meta?.version ? `v${out.meta.version}` : '',
    },
    title: out.title,
    userMsgs: out.userMsgs,
    assistantTexts: out.assistantTexts,
    tools: out.tools,
    turns: out.turns,
    firstTime: out.firstTime,
    lastTime: out.lastTime,
    empty: out.userMsgs.length === 0,
  };
}

/**
 * 回到这个会话。本机装了 dsh-tui（~/.local/bin/dsh-tui），手册写明：
 *   dsh-tui --resume         恢复上次会话
 *   dsh-tui --resume <id>    恢复指定会话（-c / --continue 同义）
 * 这里的 rec.id 就是 DSH 自己的会话 id（= 会话头 `id` 字段 = 会话目录名，实测三者一致）：
 * 老会话形如 `session-<uuid>`（version 0），新会话是裸 `<uuid>`（version 3/4），
 * 两种形态都原样传给 --resume，不要自作主张去掉 session- 前缀。
 * 注意：`dsh sessions` 不是命令、`dsh web` 没有 --resume，别再用它们。
 */
export function resumeCommand(rec) {
  return rec?.id ? `dsh-tui --resume ${rec.id}` : '';
}

/** DSH 会话原始目录（GUI 里靠它对应的项目定位）。 */
export function sessionLocation(rec) {
  return rec.dir || join(SESSIONS_ROOT, rec.project || '', rec.id || '');
}
