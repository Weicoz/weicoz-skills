// 摘要中央库：所有项目的会话摘要都存这里，与任何项目仓库解耦。
// 换项目、换仓库、删掉项目目录，摘要都还在。
//
//   ~/.local/state/weicoz-session-recall/
//     state.json        水位线 + 摘要（键为 <项目目录>/<会话目录>）
//     projects.json     项目目录 → { cwd, label, seen }
//     index.md          总索引（最近活动 + 按项目分组）
//     detail/<项目目录>/<日期>-<会话id>.md
//     lock              防重入锁
import { mkdir, open, readFile, rename, unlink, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { homedir } from 'node:os';
import { projectLabel, projectKey } from './session-source.mjs';
import { resumeCommand, sourceLabel } from './harness.mjs';

export const DATA_DIR = process.env.SESSION_RECALL_DATA_DIR
  || join(homedir(), '.local', 'state', 'weicoz-session-recall');

export const STATE_FILE = join(DATA_DIR, 'state.json');
export const PROJECTS_FILE = join(DATA_DIR, 'projects.json');
export const INDEX_FILE = join(DATA_DIR, 'index.md');
export const DETAIL_DIR = join(DATA_DIR, 'detail');
export const LOCK_FILE = join(DATA_DIR, 'lock');

export const localTime = (ms) => {
  if (!ms) return '';
  const d = new Date(ms);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export const dayOf = (ms) => (ms ? localTime(ms).slice(0, 10) : '0000-00-00');

/** Markdown 表格单元格转义。 */
export const esc = (s) => String(s ?? '').replace(/\|/g, '\\|').replace(/\n+/g, ' ').trim() || '—';

/** 详情文件路径：按项目分目录，避免不同项目的同名会话 id 互相覆盖。 */
export function detailPath(projectDir, id, ms) {
  return join(DETAIL_DIR, projectDir, `${dayOf(ms)}-${id}.md`);
}

/** 索引里指向详情文件的相对链接（项目目录含 ~XXXX 编码，需 encodeURI）。 */
export function detailLink(projectDir, id, ms) {
  return encodeURI(`detail/${projectDir}/${dayOf(ms)}-${id}.md`);
}

export async function readJson(file, dflt = null) {
  try { return JSON.parse(await readFile(file, 'utf8')); } catch { return dflt; }
}

export async function writeAtomic(file, content) {
  await mkdir(dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}`;
  await writeFile(tmp, content, 'utf8');
  await rename(tmp, file);
}

export async function loadState() {
  return (await readJson(STATE_FILE, null)) || { updatedAt: 0, models: [], sessions: {} };
}

/**
 * 项目信息缓存：projectKey 是有损编码，显示名只能从会话头里的 cwd 读一次后记住。
 * 返回 { [项目目录]: { cwd, label, seen } }。
 */
export async function loadProjects() {
  return (await readJson(PROJECTS_FILE, null)) || {};
}

/** 记录/更新一个项目的 cwd 与显示名。 */
export function touchProject(projects, projectDir, cwd) {
  const prev = projects[projectDir] || {};
  const next = {
    cwd: cwd || prev.cwd || '',
    label: projectLabel(cwd, prev.label || projectDir),
    seen: Date.now(),
  };
  projects[projectDir] = next;
  return next;
}

export function projectTitle(projects, projectDir) {
  const p = projects[projectDir];
  return (p && p.label) || projectDir;
}

/** 从会话记录 projectDir 推断它属于哪个项目（迁移旧数据时用）。 */
export function projectOfKey(key) {
  return String(key).split('/')[0];
}

// ---------- 渲染 ----------

export function renderDetail(rec) {
  const L = [];
  L.push(`# ${rec.title || '（无标题会话）'}`);
  L.push('');
  L.push(`- 来源：${sourceLabel(rec.source || rec.key)}`);
  L.push(`- 项目：${rec.projectLabel || rec.project || '—'}`);
  L.push(`- 会话 ID：\`${rec.id}\``);
  L.push(`- 时间：${localTime(rec.firstTime)} → ${localTime(rec.lastTime)}`);
  L.push(`- 用户消息：${rec.userMsgs} 条；轮次：${rec.turns}；会话文件：${rec.bytes} 字节（${rec.version}）`);
  L.push(`- 状态：${rec.status || '未标注'}`);
  L.push(`- 关键词：${(rec.keywords || []).join('、') || '—'}`);
  if (rec.artifacts?.length) L.push(`- 产出物：${rec.artifacts.join('；')}`);
  if (rec.model) L.push(`- 摘要模型：${rec.model}`);
  L.push('');
  L.push('## 摘要');
  L.push('');
  L.push(rec.summary || '（未生成）');
  if (rec.error) { L.push(''); L.push(`> 生成失败：${rec.error}`); }
  L.push('');
  if (rec.orphan) {
    L.push('> 本会话的原始记录已从对应的会话目录中移除（被清理或归档），以下是既有摘要，仅供检索。');
    L.push('');
  } else {
    L.push('## 打开这次会话');
    L.push('');
    const cmd = resumeCommand(rec);
    if (cmd) {
      L.push('```bash');
      L.push(cmd);
      L.push('```');
    } else {
      // DSH 没有命令行恢复入口，只能走 GUI
      L.push(`在 DSH 侧栏把工作区切到 ${rec.projectLabel || rec.project}，再在对话列表里找标题「${rec.title || '（无标题）'}」（列表按最近活动排序，较老的会话需展开「其余 N 个会话」）。`);
    }
    if (rec.sessionPath) {
      L.push('');
      L.push(`会话目录：\`${rec.sessionPath}\``);
    }
    L.push('');
  }
  L.push('## 用户消息（节选）');
  L.push('');
  for (const t of (rec.userTexts || []).slice(0, 20)) {
    L.push(`- ${String(t).replace(/\n+/g, ' ').slice(0, 400)}`);
  }
  L.push('');
  return L.join('\n');
}

const rowOf = (r) => [
  `| ${localTime(r.lastTime).slice(0, 16)} `,
  `| ${sourceLabel(r.source || r.key)} `,
  `| ${esc(r.title)} `,
  `| [${esc(r.summary)}](${detailLink(r.project, r.id, r.lastTime)}) `,
  `| ${esc((r.keywords || []).join('、'))} `,
  `| ${r.status || '—'} `,
  `| ${r.userMsgs} |`,
].join('');

export function renderIndex(sessions, stats = {}) {
  const all = Object.values(sessions);
  // 索引只收录"有摘要且不是无头"的会话：空壳会话与无头会话都算噪音
  const active = all.filter((r) => r.ok && !r.orphan && !r.headless).sort((a, b) => (b.lastTime || 0) - (a.lastTime || 0));
  const orphans = all.filter((r) => r.orphan).sort((a, b) => (b.lastTime || 0) - (a.lastTime || 0));
  const bySource = {};
  for (const r of active) {
    const k = sourceLabel(r.source || r.key);
    bySource[k] = (bySource[k] || 0) + 1;
  }

  const L = [];
  L.push('# 会话索引（全项目 · 多 harness）');
  L.push('');
  L.push('> 由 weicoz-session-recall skill 自动生成，请勿手工编辑（下次采集会覆盖）。');
  L.push(`> 当前 ${active.length} 个有内容会话（${Object.entries(bySource).map(([k, n]) => `${k} ${n}`).join(' / ')}），覆盖 ${new Set(active.map((r) => r.project)).size} 个项目；最近更新 ${localTime(Date.now())}。`);
  if (orphans.length) L.push(`> 另有 ${orphans.length} 个已移除会话的摘要保留在文末。`);
  L.push('');
  L.push('## 怎么用');
  L.push('');
  L.push('- 让 AI 直接检索：说"上次那个 X 怎么做的"，或运行 `node ~/.agents/skills/weicoz-session-recall/bin/recall.mjs <关键词>`。');
  L.push('- 同时覆盖 DSH、Codex、Claude Code 三个 harness 的会话；在任意一个里调用都能查到另外两个。');
  L.push('- 手动翻：按 `Ctrl/Cmd+F` 搜项目名、文件名、技术名（关键词列做了同义词冗余，同一会话的多种叫法都能命中）。');
  L.push('- 摘要不够时打开 `detail/` 下的详情文件，里面有用户消息节选和打开原会话的方式（DSH 走 GUI，Codex / Claude Code 给 resume 命令）。');
  L.push('');

  // 全局时间线：回答"我最近做了什么"
  L.push('## 最近活动（全部项目）');
  L.push('');
  L.push('| 最后活动 | 来源 | 项目 | 标题 | 摘要 | 状态 |');
  L.push('| --- | --- | --- | --- | --- | --- |');
  for (const r of active.slice(0, 40)) {
    L.push(`| ${localTime(r.lastTime).slice(0, 16)} | ${sourceLabel(r.source || r.key)} | ${esc(r.projectLabel || r.project)} | ${esc(r.title)} | [${esc(r.summary)}](${detailLink(r.project, r.id, r.lastTime)}) | ${r.status || '—'} |`);
  }
  L.push('');

  // 总览
  const byProject = new Map();
  for (const r of active) {
    const k = r.project;
    if (!byProject.has(k)) byProject.set(k, { label: r.projectLabel || k, n: 0, msgs: 0, last: 0 });
    const g = byProject.get(k);
    g.n++;
    g.msgs += r.userMsgs || 0;
    g.last = Math.max(g.last, r.lastTime || 0);
  }
  L.push('## 总览（按项目）');
  L.push('');
  L.push('| 项目 | 会话数 | 用户消息数 | 最近活动 |');
  L.push('| --- | ---: | ---: | --- |');
  for (const [k, g] of [...byProject.entries()].sort((a, b) => b[1].last - a[1].last)) {
    L.push(`| ${esc(g.label)} | ${g.n} | ${g.msgs} | ${localTime(g.last).slice(0, 16)} |`);
  }
  L.push('');

  // 分组全表
  L.push('## 按项目');
  L.push('');
  for (const [k, g] of [...byProject.entries()].sort((a, b) => b[1].last - a[1].last)) {
    L.push(`### ${g.label}`);
    L.push('');
    L.push(`\`${k}\`　${g.n} 个会话`);
    L.push('');
    L.push('| 最后活动 | 来源 | 标题 | 摘要 | 关键词 | 状态 | 消息 |');
    L.push('| --- | --- | --- | --- | --- | --- | ---: |');
    for (const r of active.filter((x) => x.project === k)) L.push(rowOf(r));
    L.push('');
  }

  if (orphans.length) {
    L.push('## 会话已移除（摘要保留）');
    L.push('');
    L.push(`以下 ${orphans.length} 个会话的原始记录已不在会话目录中（被清理或归档），既有摘要保留供检索。本工具不会自动删除任何文件。`);
    L.push('');
    L.push('| 最后活动 | 来源 | 项目 | 标题 | 摘要 | 关键词 |');
    L.push('| --- | --- | --- | --- | --- | --- |');
    for (const r of orphans) {
      L.push(`| ${localTime(r.lastTime).slice(0, 16)} | ${sourceLabel(r.source || r.key)} | ${esc(r.projectLabel || r.project)} | ${esc(r.title)} | [${esc(r.summary)}](${detailLink(r.project, r.id, r.lastTime)}) | ${esc((r.keywords || []).join('、'))} |`);
    }
    L.push('');
  }

  if (stats.failed?.length) {
    L.push('## 未生成摘要的会话');
    L.push('');
    for (const f of stats.failed) L.push(`- \`${f.key || f.id}\` ${esc(f.title)} — ${f.error}`);
    L.push('');
  }
  return L.join('\n');
}

// ---------- 防重入锁 ----------

const LOCK_STALE_MS = 2 * 60 * 60 * 1000;

/** 检查后台是否已有存活的采集进程在运行。 */
export async function isLockActive(lockFile = LOCK_FILE) {
  const prev = await readJson(lockFile, null);
  if (!prev?.pid) return false;
  if (Date.now() - (prev.at || 0) >= LOCK_STALE_MS) return false;
  try {
    process.kill(prev.pid, 0);
    return true;
  } catch {
    return false;
  }
}

/**
 * 获取独占排他锁。
 * 使用 open(LOCK_FILE, 'wx') 原子创建，避免多次执行或并发竞争导致重复写入。
 */
export async function acquireLock(lockFile = LOCK_FILE) {
  await mkdir(dirname(lockFile), { recursive: true });
  const prev = await readJson(lockFile, null);
  if (prev?.pid) {
    if (Date.now() - (prev.at || 0) < LOCK_STALE_MS) {
      try {
        process.kill(prev.pid, 0);
        console.error(`已有采集任务在运行（pid ${prev.pid}，启动于 ${localTime(prev.at)}），本次跳过。`);
        return false;
      } catch {
        // 进程已退出，清理陈旧锁
        try { await unlink(lockFile); } catch {}
      }
    } else {
      // 超时陈旧锁
      try { await unlink(lockFile); } catch {}
    }
  }

  try {
    const fh = await open(lockFile, 'wx');
    try {
      await fh.writeFile(JSON.stringify({ pid: process.pid, at: Date.now() }), 'utf8');
    } finally {
      await fh.close();
    }
    return true;
  } catch (err) {
    if (err.code === 'EEXIST') {
      const holder = await readJson(lockFile, null);
      if (holder?.pid) {
        try {
          process.kill(holder.pid, 0);
          console.error(`已有采集任务在运行（pid ${holder.pid}，启动于 ${localTime(holder.at)}），本次跳过。`);
          return false;
        } catch {
          // 抢锁冲突时原持锁进程恰好刚退出，清理后重试
          try { await unlink(lockFile); } catch {}
          return acquireLock(lockFile);
        }
      }
      return false;
    }
    throw err;
  }
}

export async function releaseLock(lockFile = LOCK_FILE) {
  const prev = await readJson(lockFile, null);
  if (!prev || prev.pid === process.pid) {
    try { await unlink(lockFile); } catch { /* 已被清理 */ }
  }
}

/** 收集摘要时用的项目集合（供 recall 过滤）。 */
export function normalizeProjectFilter(value, cwd = process.cwd()) {
  if (!value || value === 'current') return projectKey(cwd);
  if (value === 'all' || value === '*') return null;
  return value;
}
