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
//   recall.mjs --version / -v           # 显示版本号
//   recall.mjs --no-collect             # 只读，跳过自动采集
import { spawn } from 'node:child_process';
import { openSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { resumeCommand, scanAll, sourceLabel } from './lib/harness.mjs';
import { currentProjectKey } from './lib/session-source.mjs';
import { DATA_DIR, detailPath, isLockActive, loadState, localTime } from './lib/store.mjs';
import { VERSION } from './lib/version.mjs';

export { VERSION };

const HERE = dirname(fileURLToPath(import.meta.url));
const DIGEST = join(HERE, 'digest.mjs');

const args = process.argv.slice(2);
const has = (n) => args.includes(n);

if (has('--version') || has('-v')) {
  console.log(`weicoz-session-recall v${VERSION}`);
  process.exit(0);
}

const kvOpt = (n) => {
  const p = args.find((a) => a.startsWith(`--${n}=`));
  return p ? p.slice(n.length + 3) : '';
};
const terms = args.filter((a) => !a.startsWith('--')).map((t) => t.toLowerCase());
const wantStatus = has('--status');
const wantDetail = has('--detail');
const wantJson = has('--json');
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

/** 自动采集：无感后台异步派生，前台零阻塞；已有采集任务时直接跳过。 */
async function triggerBackgroundDigest() {
  if (noCollect) return { mode: 'off' };
  // 锁检查前置：后台已有存活的采集进程时直接复用，不重复拉起
  if (await isLockActive()) {
    return { mode: 'running' };
  }
  try {
    const fd = openSync(join(DATA_DIR, 'digest.log'), 'a');
    const child = spawn(process.execPath, [DIGEST, ...DIGEST_ARGS], { detached: true, stdio: ['ignore', fd, fd] });
    child.unref();
    return { mode: 'background', pid: child.pid };
  } catch {
    return { mode: 'failed' };
  }
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
  console.log(`weicoz-session-recall v${VERSION}`);
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
    console.log('后台将自动完成增量采集，无需手动等待。');
  }
  return recs.length;
}

async function main() {
  const state = await loadState();

  if (wantStatus) {
    await reportStatus(state);
    return;
  }

  const recs = Object.values(state.sessions || {}).filter((r) => r.ok && !r.orphan && !r.headless);
  if (!recs.length) {
    console.log('还没有任何会话摘要。');
    if (!noCollect) {
      await triggerBackgroundDigest();
      console.log('后台已启动首次会话采集任务（日志 ~/.local/state/weicoz-session-recall/digest.log）。');
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
    if (wantJson) {
      console.log(JSON.stringify([], null, 2));
      await triggerBackgroundDigest();
      return;
    }
    console.log(`没有会话同时命中：${terms.join(' ')}　${scopeNote}`);
    console.log('建议：换更短或更独特的词（项目名、客户名、文件名、技术名）；确认要跨全部项目时加 --all。');
    if (await isLockActive()) {
      console.log('\n（注：后台正在静默采集新会话，完成后自动进入索引）');
    }
    await triggerBackgroundDigest();
    return;
  }

  const top = ranked.slice(0, LIMIT);

  if (wantJson) {
    const jsonItems = top.map(({ rec, total, hits }) => ({
      id: rec.id,
      source: rec.source || 'dsh',
      sourceLabel: sourceLabel(rec.source || rec.key),
      project: rec.project,
      projectLabel: rec.projectLabel || rec.project,
      title: rec.title || '（无标题）',
      summary: rec.summary || '',
      artifacts: rec.artifacts || [],
      status: rec.status || '—',
      lastTime: rec.lastTime,
      lastTimeFormatted: localTime(rec.lastTime),
      score: total,
      hits: hits,
      detailPath: detailPath(rec.project, rec.id, rec.lastTime),
      resumeCommand: resumeCommand(rec) || guiHint(rec),
    }));
    console.log(JSON.stringify(jsonItems, null, 2));
    await triggerBackgroundDigest();
    return;
  }

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
      await triggerBackgroundDigest();
      return;
    }
    console.log(`（只命中一个，直接读：${file}）`);
  } else {
    console.log('多个候选时先看摘要分辨，再打开最像的那个详情；每条结果末尾都写着回到那次会话的方式。');
  }

  // 检索结果输出完毕后，静默触发一次增量采集（有存活任务时会自动防并发跳过）
  await triggerBackgroundDigest();
}

main().catch((e) => { console.error('检索失败:', e.message); process.exitCode = 1; });
