#!/usr/bin/env node
// 历史会话检索：把"我以前做过什么"变成可点开的会话窗口。
// 覆盖五个 harness：DSH（~/.dsh/sessions）、Codex（~/.codex/sessions）、
// Claude Code（~/.claude/projects）、Antigravity（~/.gemini/antigravity-cli/brain）、
// Kimi Code（~/.kimi-code/sessions）——在任意一个 harness 里调用都能查到其他 harness 的会话。
//
// 调用时会顺手采集：发现待摘要的会话就自动补上（后台异步 + 防并发排他锁），
// 所以不需要记任何定时任务——想起来找东西的时候，它自己会保持最新。
//
// 用法：
//   recall.mjs <关键词...>              # 检索（默认先看当前项目，没命中再跨全部项目）
//   recall.mjs <关键词...> --all        # 直接跨全部项目检索
//   recall.mjs <关键词...> --project=X  # 只在指定项目检索（子串匹配项目目录名）
//   recall.mjs <关键词...> --source=kimi     # 只看某个 harness（dsh / codex / claude / agy / kimi）
//   recall.mjs <关键词...> --detail     # 命中唯一时直接展开详情原文
//   recall.mjs <关键词...> --limit=10   # 展示条数（默认 5）
//   recall.mjs --status                 # 索引规模 + 待采集数量（按 harness 分）
//   recall.mjs --status --list          # 外加待采集会话明细
//   recall.mjs --no-collect             # 只读，跳过自动采集
import { spawn } from 'node:child_process';
import { openSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { resumeCommand, scanAll, sourceLabel } from './lib/harness.mjs';
import { currentProjectKey } from './lib/session-source.mjs';
import { DATA_DIR, detailPath, isLockActive, loadState, localTime } from './lib/store.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DIGEST = join(HERE, 'digest.mjs');

const args = process.argv.slice(2);
const has = (n) => args.includes(n);
const kvOpt = (n) => {
  const p = args.find((a) => a.startsWith(`--${n}=`));
  return p ? p.slice(n.length + 3) : '';
};
const terms = args.filter((a) => !a.startsWith('--')).map((t) => t.toLowerCase());
const wantStatus = has('--status');
const wantDetail = has('--detail');
const noCollect = has('--no-collect');
const wantList = has('--list');
const LIMIT = Number(kvOpt('limit')) || 5;
const PROJECT_ARG = kvOpt('project');
const SOURCE_ARG = kvOpt('source');
const DIGEST_ARGS = ['--quiet', ...(SOURCE_ARG ? ['--source', SOURCE_ARG] : [])];

/** 打分：命中越靠前的字段分越高，一个词只计一次（取最好的字段）。 */
function score(rec, list) {
  const hay = {
    title: (rec.title || '').toLowerCase(),
    keywords: (rec.keywords || []).join(' ').toLowerCase(),
    artifacts: (rec.artifacts || []).join(' ').toLowerCase(),
    summary: (rec.summary || '').toLowerCase(),
    user: (rec.userTexts || []).join(' ').toLowerCase(),
    status: (rec.status || '').toLowerCase(),
  };
  let total = 0;
  const hits = [];
  for (const t of list) {
    let best = 0;
    let where = '';
    if (hay.title.includes(t)) { best = 6; where = '标题'; }
    else if (hay.keywords.includes(t)) { best = 5; where = '关键词'; }
    else if (hay.artifacts.includes(t)) { best = 4; where = '产出物'; }
    else if (hay.summary.includes(t)) { best = 3; where = '摘要'; }
    else if (hay.user.includes(t)) { best = 2; where = '提问原文'; }
    else if (hay.status.includes(t)) { best = 1; where = '状态'; }
    if (best) { total += best; hits.push(`${t}(${where})`); }
  }
  return { total, hits };
}

/** DSH 没有命令行恢复入口，只能给 GUI 指引。 */
function guiHint(rec) {
  const label = rec.projectLabel || rec.project || '对应项目';
  return `在 DSH 侧栏把工作区切到「${label}」，再从对话列表按标题找（列表按最近活动排序，较老的需展开「其余 N 个会话」）`;
}

/** 自动采集：无变更直接返回；有待采会话一律后台异步拉起，前台绝不阻塞；已有任务运行时防并发跳过。 */
async function collect(state) {
  if (noCollect) return { pending: 0, mode: 'off' };
  const all = await scanAll({ known: state.sessions || {}, only: SOURCE_ARG || null });
  const fresh = all.filter((e) => !e.cached);
  if (!fresh.length) return { pending: 0, mode: 'none' };
  // 还在写入的会话不采：摘要生成完就过时，而且它往往正是你此刻正在用的那个会话。
  // 这一条是"调用即采集"能从十几秒回到一秒的关键。
  const active = fresh.filter((e) => e.active);
  const quiet = fresh.filter((e) => !e.active);
  if (!quiet.length) return { pending: 0, mode: 'none', active: active.length, bySourceLine: '', bySource: {} };

  const bySource = {};
  for (const q of quiet) {
    const k = q.source || 'dsh';
    bySource[k] = (bySource[k] || 0) + 1;
  }
  const bySourceLine = Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${sourceLabel(k)} ${n}`)
    .join(' / ');

  // 防并发：检查后台是否已有存活的采集进程在运行，避免多次调用并发重复拉起
  if (await isLockActive()) {
    return {
      pending: quiet.length,
      mode: 'running',
      active: active.length,
      bySource,
      bySourceLine,
    };
  }

  // 一律全后台异步拉起，前台绝不阻塞，优先给用户秒级返回结果
  const fd = openSync(join(DATA_DIR, 'digest.log'), 'a');
  const child = spawn(process.execPath, [DIGEST, ...DIGEST_ARGS], { detached: true, stdio: ['ignore', fd, fd] });
  child.unref();
  return {
    pending: quiet.length,
    mode: 'background',
    pid: child.pid,
    active: active.length,
    bySource,
    bySourceLine,
  };
}

function countLine(records) {
  const by = {};
  for (const r of records) {
    const k = r.source || 'dsh';
    by[k] = (by[k] || 0) + 1;
  }
  return Object.entries(by).map(([k, n]) => `${sourceLabel(k)} ${n}`).join(' / ');
}

async function reportStatus(state) {
  const recs = Object.values(state.sessions || {}).filter((r) => r.ok && !r.orphan && !r.headless);
  const projects = new Set(recs.map((r) => r.project));
  console.log(`索引：${recs.length} 个会话（${countLine(recs) || '空'}），覆盖 ${projects.size} 个项目；最近更新 ${localTime(state.updatedAt) || '（从未）'}`);
  const pending = (await scanAll({ known: state.sessions || {} })).filter((e) => !e.cached);
  if (!pending.length) {
    console.log('待采集：0 个 —— 索引已是最新。');
  } else {
    const bySource = {};
    for (const p of pending) bySource[p.source] = (bySource[p.source] || 0) + 1;
    console.log(`待采集：${pending.length} 个会话（${Object.entries(bySource).map(([k, n]) => `${sourceLabel(k)} ${n}`).join(' / ')}，其中 ${pending.filter((p) => p.isNew).length} 个是索引里还没有的新会话）`);
    if (wantList) {
      console.log('待办明细（最近活动在前）：');
      for (const p of [...pending].sort((a, b) => (b.mtimeMs || 0) - (a.mtimeMs || 0))) {
        console.log(`  [${sourceLabel(p.source)}] ${localTime(p.mtimeMs)}  ${p.isNew ? '新' : '变'}  ${Math.round((p.bytes || 0) / 1024)}K  ${p.key}`);
      }
    }
    console.log('再调用一次 skill（不带 --no-collect）即可自动补上。');
  }
  return recs.length;
}

async function main() {
  const state = await loadState();

  if (wantStatus && noCollect) { await reportStatus(state); return; }

  const collectResult = await collect(state);
  const fresh = state;

  if (wantStatus) { await reportStatus(fresh); return; }

  const recs = Object.values(fresh.sessions || {}).filter((r) => r.ok && !r.orphan && !r.headless);
  if (!recs.length) {
    console.log('还没有任何会话摘要。');
    if (collectResult.pending) {
      const hint = collectResult.mode === 'running' ? '后台已有采集任务在运行' : '后台已启动会话采集任务';
      const harnessText = collectResult.bySourceLine ? `（${collectResult.bySourceLine}）` : '';
      console.log(`提示：${hint}，当前有 ${collectResult.pending} 个会话正在采集${harnessText}。`);
      console.log('请等待后台采集完成后再重新查找，无需阻塞等待，也不用在采集中反复重复执行。');
      console.log('（可通过 recall.mjs --status 查看采集进度）');
    } else if (collectResult.mode === 'off') {
      console.log('（--no-collect 模式，未触发采集）');
    }
    process.exitCode = terms.length ? 1 : 0;
    return;
  }
  if (!terms.length) {
    console.log('给几个关键词才能检索。例如：recall.mjs 竞拍 页面\n（只想看进度：recall.mjs --status）');
    return;
  }

  // 作用域：默认先看当前项目，没命中再跨项目
  const currentKey = currentProjectKey();
  let pool = recs;
  let scopeNote = '';
  if (SOURCE_ARG) {
    pool = pool.filter((r) => (r.source || 'dsh') === SOURCE_ARG);
    scopeNote = `（限定来源：${sourceLabel(SOURCE_ARG)}）`;
  }
  if (PROJECT_ARG) {
    pool = pool.filter((r) => String(r.project).includes(PROJECT_ARG));
    scopeNote += `（限定项目：${PROJECT_ARG}）`;
  } else if (!has('--all')) {
    const mine = recs.filter((r) => r.project === currentKey);
    const mineHits = mine.some((r) => score(r, terms).total > 0);
    if (mineHits) {
      pool = pool.filter((r) => r.project === currentKey && (!SOURCE_ARG || (r.source || 'dsh') === SOURCE_ARG));
      scopeNote += `（当前项目：${mine[0]?.projectLabel || currentKey}）`;
    } else {
      scopeNote += `（当前项目 ${mine[0]?.projectLabel || currentKey} 没有命中，已跨全部项目检索）`;
    }
  }

  const ranked = pool
    .map((rec) => ({ rec, ...score(rec, terms) }))
    .filter((x) => x.total > 0)
    .sort((a, b) => b.total - a.total || (b.rec.lastTime || 0) - (a.rec.lastTime || 0));

  if (!ranked.length) {
    console.log(`没有会话同时命中：${terms.join(' ')}　${scopeNote}`);
    if (collectResult.pending) {
      const hint = collectResult.mode === 'running' ? '后台已有采集任务在运行' : '后台已启动会话采集任务';
      const harnessText = collectResult.bySourceLine ? `（${collectResult.bySourceLine}）` : '';
      console.log(`\n提示：${hint}，当前有 ${collectResult.pending} 个会话正在采集${harnessText}。`);
      console.log('未找到结果可能是目标会话尚未采集完成；请等待后台采集完成后再重新查找，无需阻塞等待，也不用在采集中反复重复执行。');
      console.log('（可通过 recall.mjs --status 查看采集进度）');
    } else {
      console.log('建议：换更短或更独特的词（项目名、客户名、文件名、技术名）；确认要跨全部项目时加 --all。');
    }
    return;
  }

  const top = ranked.slice(0, LIMIT);
  console.log(`命中 ${ranked.length} 个会话，展示前 ${top.length} 个（按匹配度）${scopeNote}\n`);
  for (const { rec, total, hits } of top) {
    console.log(`▸ ${localTime(rec.lastTime)}  [${sourceLabel(rec.source || rec.key)}]  ${rec.status || '—'}  [${total} 分]  ${rec.projectLabel || rec.project}`);
    console.log(`  ${rec.title || '（无标题）'}`);
    console.log(`  ${rec.summary || '（无摘要）'}`);
    if (rec.artifacts?.length) console.log(`  产出：${rec.artifacts.join('；')}`);
    console.log(`  匹配：${hits.join('、')}`);
    console.log(`  详情：${detailPath(rec.project, rec.id, rec.lastTime)}`);
    const cmd = resumeCommand(rec);
    console.log(`  回到会话：${cmd || guiHint(rec)}`);
    console.log('');
  }

  const single = top.length === 1 ? top[0] : null;
  if (single) {
    const file = detailPath(single.rec.project, single.rec.id, single.rec.lastTime);
    if (wantDetail) {
      console.log('--- 详情原文 ---');
      console.log(await readFile(file, 'utf8'));
      return;
    }
    console.log(`（只命中一个，直接读：${file}）`);
  } else {
    console.log('多个候选时先看摘要分辨，再打开最像的那个详情；每条结果末尾都写着回到那次会话的方式。');
  }

  const harnessText = collectResult.bySourceLine ? `（${collectResult.bySourceLine}）` : '';
  if (collectResult.mode === 'background') {
    console.log(`\n注：后台正在采集 ${collectResult.pending} 个会话${harnessText}（日志 ~/.local/state/weicoz-session-recall/digest.log），采集完成后重新检索结果会更全，无需手动等待。`);
  } else if (collectResult.mode === 'running') {
    console.log(`\n注：后台已有采集任务在运行，当前有 ${collectResult.pending} 个会话正在采集${harnessText}，完成后重新检索结果会更全，无需手动等待。`);
  }
  if (collectResult.active) {
    console.log(`\n注：另有 ${collectResult.active} 个会话正在进行中（活跃写入中，暂不采集），等它安静下来后下次会自动补上。`);
  }
}

main().catch((e) => { console.error('检索失败:', e.message); process.exitCode = 1; });
