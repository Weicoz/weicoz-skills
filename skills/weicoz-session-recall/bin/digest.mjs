#!/usr/bin/env node
// 会话采集：扫描本机五个 harness（DSH / Codex / Claude Code / Antigravity / Kimi Code）的会话，
// 给新增或有变更的会话生成中文摘要与关键词，写进中央库。
// 由 skill 自动触发（recall 发现待处理会话时会调它），也可以手动运行。
//
// 用法：
//   node bin/digest.mjs                        # 增量（只处理有变更的）
//   node bin/digest.mjs --force                # 全部重算
//   node bin/digest.mjs --limit 20             # 本次最多处理 20 个
//   node bin/digest.mjs --project <子串>       # 只处理匹配的项目（默认全部）
//   node bin/digest.mjs --source dsh|codex|claude|agy|kimi   # 只处理某个 harness
//   node bin/digest.mjs --only <子串>          # 只处理会话 id 含该子串的
//   node bin/digest.mjs --min 2                # 只处理用户消息数 ≥2 的会话
//   node bin/digest.mjs --render               # 只重渲染索引与详情，不调用模型
//   node bin/digest.mjs --dry                  # 只报告待处理清单，不写任何文件
//   node bin/digest.mjs --include-active       # 连正在写入的会话也采（默认跳过它们）
//   node bin/digest.mjs --migrate-from <file> --project <项目目录>
//                                              # 把旧项目的水位线导入中央库
//
// 产物（都在 ~/.local/state/weicoz-session-recall/，不在任何项目仓库里）：
//   index.md                          总索引
//   detail/<项目>/<日期>-<会话id>.md   单会话摘要
//   state.json                        水位线（增量依据）
import { mkdir } from 'node:fs/promises';

import { SOURCES, migrateLegacyState, parseEntry, scanAll } from './lib/harness.mjs';
import { MODELS, buildPrompt, callModel, loadApiKey } from './lib/llm.mjs';
import {
  DETAIL_DIR, INDEX_FILE, PROJECTS_FILE, STATE_FILE, acquireLock, detailPath, loadProjects,
  loadState, localTime, readJson, releaseLock, renderDetail, renderIndex, touchProject, writeAtomic,
} from './lib/store.mjs';

// 落盘批次：每处理 N 个会话就把状态和索引写一次，任务中断也不丢已完成部分
const FLUSH_EVERY = Number(process.env.SESSION_RECALL_FLUSH || 5);

const argvList = process.argv.slice(2);
const flag = (n) => argvList.includes(n);
const opt = (n, d) => {
  const i = argvList.indexOf(n);
  return i >= 0 && argvList[i + 1] ? argvList[i + 1] : d;
};

const FORCE = flag('--force');
const DRY = flag('--dry');
const RENDER_ONLY = flag('--render');
const QUIET = flag('--quiet');
const INCLUDE_ACTIVE = flag('--include-active');
const LIMIT = Number(opt('--limit', '0')) || 0;
const ONLY = opt('--only', '');
const PROJECT_FILTER = opt('--project', '');
const SOURCE_FILTER = opt('--source', '');
const MIN_MSGS = Number(opt('--min', '1'));
const MIGRATE_FROM = opt('--migrate-from', '');

function log(...a) { if (!QUIET) console.log(...a); }

// 项目显示名兜底：projectKey 有损（分隔符被折叠），但末尾那段通常就是目录名
function guessLabel(projectKey) {
  const raw = String(projectKey || '').replace(/^-+|-+$/g, '');
  if (!raw) return '';
  const parts = raw.split('-').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : raw;
}

// ---------- 扫描 ----------
//
// 扫描只做 stat（不解压、不调用模型），三源并行。取哪些进候选由这里决定：
// 已在库里且没变的复用旧摘要；还在写入的会话（多半正是用户此刻在用的那个）
// 沿用旧摘要，避免"刚生成就过时"的重复劳动，也避免把正在写的文件读坏。

async function scan(state, projects) {
  const all = await scanAll({ known: state.sessions, only: SOURCE_FILTER || null });
  const out = { all, records: {}, candidates: [], counts: {}, activeSkipped: 0 };
  const filter = PROJECT_FILTER.toLowerCase();

  for (const e of all) {
    out.counts[e.source] = (out.counts[e.source] || 0) + 1;
    const key = e.key;
    const prior = e.prior || state.sessions[key];
    const label = projects[e.project]?.label || prior?.projectLabel || '';

    // 任何被扫到的会话都要落进 records：否则主流程会把它误判成"已从磁盘移除"
    const keep = () => {
      if (!prior) return;
      out.records[key] = {
        ...prior,
        key,
        source: e.source,
        project: e.project || prior.project,
        projectLabel: label || prior.projectLabel,
        cached: true,
      };
    };

    if (filter) {
      const hay = `${e.project || ''} ${label} ${key}`.toLowerCase();
      if (!hay.includes(filter)) { keep(); continue; }
    }
    // 无头会话（Codex 的 codex_exec 自动化执行、Claude Code 的 SDK 调用）不进索引：
    // 没有人打过字，摘要出来也没有检索价值。仍然落一条记录，
    // 这样下次扫描不必重新解析文件，也不会被当成"已从磁盘移除"。
    if (e.headless) {
      out.records[key] = {
        ...(prior || {}),
        key,
        source: e.source,
        id: e.id,
        file: e.file,
        version: e.version,
        bytes: e.bytes,
        mtime: e.mtimeMs,
        project: e.project || prior?.project || '_unknown',
        projectLabel: label || prior?.projectLabel || '',
        ok: false,
        headless: true,
        cached: true,
      };
      continue;
    }
    if (e.cached && !FORCE) { keep(); continue; }
    if (e.active && !INCLUDE_ACTIVE) { out.activeSkipped++; keep(); continue; }
    out.candidates.push({ ...e, projectLabel: label });
  }
  return out;
}

// ---------- 迁移旧水位线 ----------

async function migrate(fromFile, projectDir) {
  const old = await readJson(fromFile, null);
  if (!old?.sessions) { console.error(`✗ 读不到旧水位线：${fromFile}`); return 0; }
  if (!projectDir) { console.error('✗ 迁移必须同时给 --project <项目目录名>'); return 0; }
  const state = await loadState();
  let n = 0;
  for (const [oldKey, rec] of Object.entries(old.sessions)) {
    if (!rec?.ok) continue; // 失败的记录不迁，让新库重新算
    const name = rec.dirName || oldKey;
    const key = `dsh:${projectDir}/${name}`;
    state.sessions[key] = {
      ...rec,
      key,
      source: 'dsh',
      id: rec.id || oldKey,
      dirName: name,
      project: projectDir,
      projectLabel: rec.projectLabel || '',
      sessionPath: rec.sessionPath || '',
    };
    n++;
  }
  await writeAtomic(STATE_FILE, JSON.stringify(state, null, 1));
  log(`已从 ${fromFile} 导入 ${n} 条摘要到项目 ${projectDir}`);
  return n;
}

// ---------- 主流程 ----------

async function main() {
  const t0 = Date.now();

  if (MIGRATE_FROM) {
    const n = await migrate(MIGRATE_FROM, PROJECT_FILTER);
    if (!n) return;
  }

  const state = await loadState();
  const projects = await loadProjects();

  // 旧版键是 <项目目录>/<会话目录>（DSH 专用），统一补上 dsh: 前缀，省掉 185 条重算
  const migrated = migrateLegacyState(state);
  if (migrated) log(`已把 ${migrated} 条旧水位线键补上 dsh: 前缀。`);

  const apiKey = DRY || RENDER_ONLY ? '' : await loadApiKey();
  if (!DRY && !RENDER_ONLY && !apiKey) {
    console.error('缺少 API 凭据：请设置 SESSION_RECALL_API_KEY，或确保 ~/.opencodex/config.json 的 providers.newapi.apiKey 可用。');
    process.exit(2);
  }

  const scanStart = Date.now();
  const sc = await scan(state, projects);
  const scanMs = Date.now() - scanStart;
  const bySource = SOURCES
    .map((s) => `${s.META.label} ${sc.counts[s.META.id] || 0}`)
    .join(' / ');
  log(`扫描本机会话（${bySource}）：命中 ${sc.candidates.length} 个待处理，复用已有摘要 ${Object.keys(sc.records).length} 个（${scanMs}ms）。`);
  if (sc.activeSkipped) log(`跳过 ${sc.activeSkipped} 个正在写入的会话（安静下来后下次自动补上）。`);

  const failed = [];
  let processed = 0;

  const buildState = (recs) => {
    const st = { updatedAt: Date.now(), models: MODELS, sessions: {} };
    for (const [k, r] of Object.entries(recs)) st.sessions[k] = r;
    return st;
  };

  // 分批落盘：只写状态与索引（详情在会话处理时单独写，避免每次 flush 重写上百个文件）
  const flush = async () => {
    await writeAtomic(STATE_FILE, JSON.stringify(buildState(sc.records), null, 1));
    await writeAtomic(INDEX_FILE, renderIndex(sc.records));
  };

  // 补上本次没出现在磁盘上的会话：既有摘要保留并标注，绝不删文件
  const scannedKeys = new Set(sc.all.map((e) => e.key));
  let orphanCount = 0;
  for (const [key, old] of Object.entries(state.sessions)) {
    if (sc.records[key]) continue;
    // 本轮没扫到的源（例如 --source / --project 限定），原样保留
    if (!scannedKeys.has(key)) {
      sc.records[key] = { ...old, key, cached: true };
      continue;
    }
    if (!old?.ok) continue;
    sc.records[key] = { ...old, key, orphan: true };
    orphanCount++;
  }
  if (orphanCount) log(`有 ${orphanCount} 个会话已不在磁盘上：既有摘要保留并标注为「会话已移除」，本工具不删除任何文件。`);

  if (DRY) {
    log(`\n--dry：以下 ${sc.candidates.length} 个会话待摘要（不调用模型、不写任何文件）`);
    for (const c of sc.candidates.slice(0, 50)) {
      log(`  · [${c.source}] ${c.projectLabel || c.project || '-'}  ${c.id}  ${c.bytes} 字节`);
    }
    if (sc.candidates.length > 50) log(`  … 其余 ${sc.candidates.length - 50} 个`);
    log(`\n--dry 结束（${((Date.now() - t0) / 1000).toFixed(1)}s）。`);
    return;
  }

  if (RENDER_ONLY) {
    await flush();
    await mkdir(DETAIL_DIR, { recursive: true });
    let n = 0;
    for (const r of Object.values(sc.records)) {
      if (!r.ok || r.orphan) continue;
      await writeAtomic(detailPath(r.project, r.id, r.lastTime), renderDetail(r));
      n++;
    }
    log(`已重渲染索引与 ${n} 个详情文件。`);
    return;
  }

  if (!(await acquireLock())) return;
  try {
    for (const c of sc.candidates) {
      if (LIMIT && processed >= LIMIT) { log(`达到 --limit ${LIMIT}，剩余下次处理。`); break; }

      let p;
      try {
        p = await parseEntry(c);
      } catch (err) {
        // 单个会话读坏（文件被截断、JSON 行损坏）不能拖死整批
        const msg = `读取失败：${String(err?.message || err).slice(0, 120)}`;
        const rec = {
          key: c.key, source: c.source, project: c.project || '', projectLabel: c.projectLabel || '',
          id: c.id, file: c.file, version: c.version, bytes: c.bytes, mtime: c.mtimeMs,
          title: '', turns: 0, userMsgs: 0, lastTime: 0, tools: {}, ok: false, error: msg,
        };
        sc.records[rec.key] = rec;
        failed.push({ key: rec.key, title: '', error: msg });
        log(`✗ [${c.source}] ${c.id.slice(0, 24)} ${msg}`);
        processed++;
        continue;
      }
      if (p.userMsgs.length < MIN_MSGS) {
        // 没有人工对话（Codex 的 codex_exec 自动化执行最常见）：摘要它没有意义。
        // 但不能就此略过 —— 不写记录的话，每次扫描都会把它重新算成"待摘要"，
        // --status 里就永远挂着一批清不掉的待办，定时任务每次也白扫一遍。
        // 记一条 empty 记录（不是失败），只有文件真的变了才会再看。
        sc.records[c.key] = {
          key: c.key, source: c.source, project: c.project || '_unknown',
          projectLabel: c.projectLabel || '', id: c.id, file: c.file, version: c.version,
          bytes: c.bytes, mtime: c.mtimeMs, title: p.title || '', turns: p.turns || 0,
          userMsgs: 0, firstTime: p.firstTime || 0, lastTime: p.lastTime || 0,
          tools: p.tools || {}, ok: false, empty: true,
        };
        continue;
      }

      const project = p.meta?.projectKey || c.project || '_unknown';
      let label = c.projectLabel || p.meta?.projectLabel || projects[project]?.label || guessLabel(project);
      if (project && p.meta?.cwd && !projects[project]?.cwd) {
        const info = touchProject(projects, project, p.meta.cwd);
        label = info.label || label;
      }

      const rec = {
        key: c.key,
        source: c.source,
        project,
        projectLabel: label || project,
        id: c.id,
        dirName: c.id,
        file: c.file,
        dir: c.dir || '',
        sessionPath: c.dir || '',
        cwd: p.meta?.cwd || '',
        version: c.version,
        bytes: c.bytes,
        mtime: c.mtimeMs,
        title: p.title,
        turns: p.turns,
        userMsgs: p.userMsgs.length,
        firstTime: p.firstTime,
        lastTime: p.lastTime,
        tools: p.tools,
        userTexts: p.userMsgs.map((t) => t.replace(/\n+/g, ' ').slice(0, 400)),
        summary: '',
        keywords: [],
        status: '',
        artifacts: [],
        ok: false,
      };

      const r = await callModel(buildPrompt(p, rec.projectLabel), apiKey);
      processed++;
      if (r.error) {
        rec.error = r.error;
        failed.push({ key: rec.key, title: rec.title, error: r.error });
        log(`✗ [${c.source}] ${String(rec.projectLabel).slice(0, 14)} ${c.id.slice(0, 20)} ${r.error.slice(0, 80)}`);
      } else {
        rec.summary = r.summary || '';
        rec.keywords = Array.isArray(r.keywords) ? r.keywords.filter(Boolean).slice(0, 10) : [];
        rec.status = r.status || '';
        rec.artifacts = Array.isArray(r.artifacts) ? r.artifacts.filter(Boolean).slice(0, 8) : [];
        rec.model = r.modelUsed || '';
        rec.ok = true;
        log(`✓ ${localTime(rec.lastTime).slice(0, 16)} [${c.source}/${String(rec.projectLabel).slice(0, 12)}] ${String(rec.userMsgs).padStart(2)}条 ${(rec.title || '').slice(0, 30)} → ${(rec.summary || '').slice(0, 60)}`);
      }
      sc.records[rec.key] = rec;
      if (rec.ok) await writeAtomic(detailPath(rec.project, rec.id, rec.lastTime), renderDetail(rec));
      if (processed > 0 && processed % FLUSH_EVERY === 0) { await flush(); log(`  · 已落盘（累计 ${processed} 个）`); }
    }

    await mkdir(DETAIL_DIR, { recursive: true });
    await flush();

    const live = Object.values(sc.records).filter((r) => r.ok && !r.orphan);
    const okCount = live.length;
    const projectCount = new Set(live.map((r) => r.project)).size;
    log('');
    log(`完成：索引 ${okCount} 个会话（${projectCount} 个项目），本次新处理 ${processed} 个，失败 ${failed.length} 个，耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    log(`索引：${INDEX_FILE}`);
  } finally {
    await releaseLock();
    await writeAtomic(PROJECTS_FILE, JSON.stringify(projects, null, 1));
    // 把失败清单写进索引，便于下次排查（成功时索引已在 flush 里写过）
    if (failed.length) await writeAtomic(INDEX_FILE, renderIndex(sc.records, { failed }));
  }
}

process.on('SIGINT', async () => { await releaseLock(); process.exit(130); });
process.on('SIGTERM', async () => { await releaseLock(); process.exit(143); });

main().catch((e) => { console.error('致命错误:', e); process.exit(1); });
