// 三个 harness 的会话源注册表。
//
// 支持范围：DSH（~/.dsh/sessions）、Codex（~/.codex/sessions）、
// Claude Code（~/.claude/projects）。三者共用同一份水位线、同一套摘要与检索，
// 所以索引里任意一条记录都能回答"这是哪个 harness 的会话、怎么回到它"。
//
// 水位线键一律带源前缀（dsh: / codex: / claude:），旧格式（<项目目录>/<会话目录>）
// 由 migrateLegacyState 补上 dsh: 前缀，保证 185 条历史摘要不用重算。
import * as dsh from './sources/dsh.mjs';
import * as codex from './sources/codex.mjs';
import * as claude from './sources/claude.mjs';
import * as agy from './sources/agy.mjs';
import * as kimi from './sources/kimi.mjs';

export const SOURCES = [dsh, codex, claude, agy, kimi];

const BY_ID = new Map(SOURCES.map((s) => [s.META.id, s]));

/** 按源 id 取源实现；未知 id 退回 DSH。 */
export function sourceById(id) {
  return BY_ID.get(String(id || '')) || dsh;
}

/** 从水位线键（<源>:<...>）取出对应的源。 */
export function sourceOfKey(key) {
  return sourceById(String(key || '').split(':')[0]);
}

/** 源的中文显示名（索引与检索结果里用）。 */
export function sourceLabel(idOrKey) {
  const raw = String(idOrKey || '');
  const id = raw.includes(':') ? raw.split(':')[0] : raw;
  return sourceById(id).META.label;
}

/**
 * 旧水位线的键是 <项目目录>/<会话目录>（DSH 专用，不含冒号），
 * 现在统一加源前缀。就地改成新键并返回迁移条数。
 */
export function migrateLegacyState(state) {
  if (!state?.sessions) return 0;
  let moved = 0;
  for (const [key, rec] of Object.entries(state.sessions)) {
    if (key.includes(':') || !rec || typeof rec !== 'object') continue;
    const next = `${dsh.META.id}:${key}`;
    state.sessions[next] = { ...rec, key: next, source: dsh.META.id };
    delete state.sessions[key];
    moved++;
  }
  return moved;
}

/**
 * 三源一起快扫（各自只 stat，不解析、不调用模型）。
 * only 可限定单个源（如 'dsh'），用于排查某个 harness 的问题。
 */
export async function scanAll({ known = {}, only = null } = {}) {
  const picked = only ? [sourceById(only)] : SOURCES;
  const results = await Promise.all(picked.map((s) => s.scanSessions({ known }).catch(() => [])));
  return results.flat();
}

/** 解析一条会话（按键里的源前缀分派）。 */
export async function parseEntry(entry) {
  return sourceOfKey(entry.key).parseSession(entry);
}

/** 回到该会话的命令；返回空串表示该 harness 没有命令行入口。 */
export function resumeCommand(rec) {
  return sourceOfKey(rec.key).resumeCommand(rec);
}
