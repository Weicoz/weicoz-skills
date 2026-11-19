#!/usr/bin/env node
// 只读：读当前仓库状态，判断所处节点，给出下一步该用的 skill。
// 用法：node where.mjs [--repo <目录>] [--base <基础分支>] [--json]
import { existsSync, readFileSync, readdirSync, statSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, resolve, relative } from 'node:path';
import { spawnSync } from 'node:child_process';

const git = (dir, ...a) => {
  const r = spawnSync('git', a, { cwd: dir, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  return r.status === 0 ? r.stdout.trim() : null;
};
const readOr = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const list = (d) => { try { return readdirSync(d); } catch { return []; } };

const CLOSED = new Set(['resolved', 'done', 'closed', 'completed', 'wontfix', '已完成', '完成', '已关闭']);
const WEB_DEPS = ['next', 'vite', 'react', 'react-dom', 'preact', 'vue', 'nuxt', 'svelte', '@sveltejs/kit', 'astro', '@angular/core', 'solid-js', 'express', 'koa', 'fastify', 'hono', '@nestjs/core', 'webpack', 'react-scripts'];
const stripQ = (v) => v.replace(/^[\s"'`*_]+/, '').replace(/[\s"'`*_]+$/, '');

// 读前 20 行，取第一处 Status 的第一个词；认 Status: x、**Status:** x、- **Status**: x、status: "x"、状态：x、## Status 标题下一行
export function ticketStatus(text) {
  const lines = text.split(/\r?\n/).slice(0, 20);
  for (let i = 0; i < lines.length; i++) {
    let v = null;
    const m = lines[i].match(/^\s*(?:[-*]\s+)?\**\s*(?:status|状态)\s*\**\s*[:：]\s*\**\s*(.*)$/i);
    if (m) v = m[1];
    else if (/^\s*#+\s*(?:status|状态)\s*$/i.test(lines[i])) v = lines.slice(i + 1).find((l) => l.trim()) ?? '';
    if (v === null) continue;
    // 去掉 ✅ 等前缀符号和撇号，Won't fix 归一成 wontfix
    const w = stripQ(v).replace(/^[^\p{L}\p{N}]+/u, '').replace(/['’]/g, '').split(/[\s,;，；]/)[0];
    const t = stripQ(w).replace(/[.。]+$/, '').toLowerCase();
    return t === 'wont' ? 'wontfix' : t;
  }
  return '';
}
export const isClosed = (text) => { const t = ticketStatus(text); return CLOSED.has(t) || /^closed[-_]/.test(t); };
// wayfinder 决策票：Type 为 research/prototype/grilling
const isDecision = (text) => /^\s*\**\s*type\s*\**\s*[:：]\s*\**\s*(research|prototype|grilling)\b/im.test(text.split(/\r?\n/).slice(0, 20).join('\n'));

const readJson = (f) => { try { const v = JSON.parse(readOr(f)); return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; } catch { return {}; } };

export function collect(dir, base) {
  const top = git(dir, 'rev-parse', '--show-toplevel');
  const root = top || dir;
  const f = { dir: root, git: top !== null };
  if (top) { try { f.sub = relative(realpathSync(top), realpathSync(dir)); } catch { f.sub = ''; } }
  const pjs = [join(root, 'package.json'), ...['apps', 'packages'].flatMap((g) => list(join(root, g)).map((x) => join(root, g, x, 'package.json')))].map(readJson);
  f.cocos = Boolean(pjs[0].creator) || existsSync(join(root, 'settings/v2/packages'));
  const deps = pjs.flatMap((pj) => Object.keys({ ...pj.dependencies, ...pj.devDependencies }));
  f.web = !f.cocos && deps.some((d) => WEB_DEPS.includes(d) || d.startsWith('@remix-run/'));
  const agents = readOr(join(root, 'AGENTS.md'));
  f.verifySection = /^##\s*验证约定/m.test(agents);
  f.e2eDir = existsSync(join(root, 'tests/e2e'));
  f.features = existsSync(join(root, 'tests/e2e/FEATURES.md'));
  f.pending = existsSync(join(root, 'docs/PENDING.md'));
  const scratch = list(join(root, '.scratch'));
  // 只数 Matt 本地票据（.scratch/<功能>/issues/*.md）里未关闭的；有 map.md 的目录是 wayfinder 地图，其票另计为决策票
  f.tickets = 0;
  f.decisions = 0;
  f.humanTickets = 0;
  for (const s of scratch) {
    const isMap = existsSync(join(root, '.scratch', s, 'map.md'));
    for (const x of list(join(root, '.scratch', s, 'issues'))) {
      if (!x.endsWith('.md')) continue;
      const text = readOr(join(root, '.scratch', s, 'issues', x));
      if (isClosed(text)) continue;
      if (isMap || isDecision(text)) f.decisions++;
      else { f.tickets++; if (ticketStatus(text) === 'ready-for-human') f.humanTickets++; }
    }
  }
  f.spec = existsSync(join(root, 'docs/spec.md')) || scratch.some((s) => existsSync(join(root, '.scratch', s, 'spec.md')));
  f.worktrees = list(join(root, '.worktrees')).length;
  const shots = [join(root, 'temp/web-verify/contact.png'), ...list(join(root, 'temp')).filter((x) => /^contact.*\.png$/.test(x)).map((x) => join(root, 'temp', x))];
  const newest = Math.max(0, ...shots.filter(existsSync).map((p) => statSync(p).mtimeMs));
  f.evidenceHours = newest ? Math.round((Date.now() - newest) / 36e5) : null;
  if (!f.git) return f;
  f.noCommits = git(root, 'rev-parse', '--verify', '-q', 'HEAD') === null;
  f.branch = git(root, 'branch', '--show-current') || (f.noCommits ? '(无提交)' : '(游离 HEAD)');
  const has = (b) => git(root, 'rev-parse', '--verify', '-q', `${b}^{commit}`) !== null;
  f.probed = ['develop', 'main', 'master'].filter(has);
  f.baseMissing = Boolean(base) && !has(base);
  f.base = base || f.probed[0] || null;
  f.onBase = f.branch === f.base;
  const st = (git(root, 'status', '--porcelain') || '').split('\n').filter(Boolean);
  f.dirty = st.length;
  f.untrackedOnly = st.length > 0 && st.every((l) => l.startsWith('??'));
  f.ahead = !f.noCommits && f.base && !f.baseMissing && !f.onBase ? Number(git(root, 'rev-list', '--count', `${f.base}..HEAD`) || 0) : 0;
  f.devAheadMain = f.branch === 'develop' && has('main') ? Number(git(root, 'rev-list', '--count', 'main..develop') || 0) : 0;
  return f;
}

export function classify(f) {
  const hints = [];
  const out = (node, why, next) => ({ node, why, next, hints });
  if (f.cocos) hints.push('小游戏项目：阶段和人工检查点以 weicoz-game-flow 为准，先读它判断当前阶段' + (f.pending ? '（看 docs/PENDING.md）' : ''));
  if (f.web && !f.e2eDir) hints.push('Web 项目还没有端到端流程：按 weicoz-verify 的 references/e2e-authoring.md 补');
  if (f.e2eDir && !f.features) hints.push('有 tests/e2e 但没有功能地图：按 e2e-authoring.md 第 1 步补 tests/e2e/FEATURES.md');
  if (f.decisions > 0) hints.push(`wayfinder 地图有 ${f.decisions} 张未决决策票：继续 wayfinder，清完后回 to-spec`);
  if (f.humanTickets > 0) hints.push(`其中 ${f.humanTickets} 张是 ready-for-human：要人去做（真机、现场、授权），agent 不能代做`);
  if (f.devAheadMain > 0) hints.push(`develop 领先 main ${f.devAheadMain} 个提交：发版按项目流程合并到 main（需用户授权）`);
  if (f.spec && f.tickets === 0) hints.push('有规格没有票据：to-tickets');
  if (f.worktrees > 3) hints.push(`.worktrees 下有 ${f.worktrees} 个目录：weicoz-govern 体检列清理候选`);
  if (f.evidenceHours !== null && f.evidenceHours > 72 && (f.dirty || f.ahead)) hints.push(`最近一次验证证据是 ${f.evidenceHours} 小时前，交付前要重跑`);

  if (!f.git) return out('未建仓', '当前目录不是 git 仓库', ['git init 并做首次提交', f.cocos ? 'weicoz-game-flow 阶段 0' : 'setup-matt-pocock-skills 配置票据与文档位置']);
  if (f.noCommits) return out('未建仓', '还没有首次提交', ['做首次提交（先确认 .gitignore），再回来判断节点']);
  if (!f.verifySection) return out('验证未接入', 'AGENTS.md 没有“## 验证约定”', [
    f.cocos ? 'weicoz-game-flow 的 references/project-agents.md 模板' : 'weicoz-verify 第 1 节，模板 references/project-section.md',
    '写完让用户确认快检、全检命令，再开始实现',
  ]);
  const b = f.base || '<基础分支>';
  if (f.dirty > 0) {
    if (f.untrackedOnly) hints.push('改动全是未跟踪文件：确认该提交，还是加进 .gitignore');
    return out('实现中', `工作区有 ${f.dirty} 处未提交改动${f.untrackedOnly ? '，全是未跟踪文件' : ''}`, [
    '每轮写完跑快检；按 weicoz-implement-verified 第 2 步走',
    `提交前 weicoz-code-review ${b} --repo <仓库根>（审到工作区，含未跟踪文件）`,
    `收尾跑全检并带 --base ${b}，结论“通过”后再提交`,
    ]);
  }
  if (f.ahead > 0) return out('待合并', `分支 ${f.branch} 比 ${b} 多 ${f.ahead} 个提交，工作区干净`, [
    `全检带 --base ${b}，确认结论行是“结论：通过”`,
    `weicoz-code-review ${b}..HEAD --repo <仓库根>`,
    '发 PR 用 pr；合并前按项目规则问版本号与 CHANGELOG',
  ]);
  if (f.tickets > 0) return out('待实现', `有 ${f.tickets} 张票据，工作区干净`, [
    '单票：weicoz-implement-verified（每票 /clear 后开新上下文）',
    '整份规格一次跑完：weicoz-implement-verified 的“整份规格”小节（implement-spec）',
    '想交给别的代理做：weicoz-agent-implement / weicoz-agent-implement-spec',
  ]);
  return out('空闲', '工作区干净，没有待合并提交或票据', [
    '新想法：grill-with-docs →（需要时 prototype）→ to-spec → to-tickets',
    '有 bug：diagnosing-bugs；积压 issue：triage',
    '隔一段时间：weicoz-govern 体检；做完一轮：retro',
  ]);
}

function main() {
  const a = process.argv.slice(2);
  const usage = '用法：node where.mjs [--repo <目录>] [--base <基础分支>] [--json]';
  const die = (m) => { console.error(`${m}\n${usage}`); process.exit(2); };
  const opt = (k) => {
    const i = a.indexOf(k);
    if (i < 0) return undefined;
    if (a[i + 1] === undefined || a[i + 1].startsWith('--')) die(`${k} 缺少值`);
    return a[i + 1];
  };
  const bad = a.filter((x, i) => x.startsWith('--') && !['--repo', '--base', '--json'].includes(x) && !['--repo', '--base'].includes(a[i - 1]));
  if (bad.length) die(`未知参数：${bad.join(' ')}`);
  const repo = resolve(opt('--repo') || '.');
  const baseArg = opt('--base');
  if (!existsSync(repo) || !statSync(repo).isDirectory()) die(`--repo 路径不存在或不是目录：${repo}`);
  const f = collect(repo, baseArg);
  if (f.baseMissing) die(`--base 指向的分支不存在：${baseArg}\n探测到的基础分支：${f.probed.length ? f.probed.join('、') : '无（develop/main/master 都不存在）'}`);
  const r = classify(f);
  if (a.includes('--json')) { console.log(JSON.stringify({ facts: f, ...r }, null, 2)); return; }
  const yn = (v) => (v ? '有' : '无');
  console.log(`仓库根：${f.dir}`);
  if (f.sub) console.log(`当前子目录：${f.sub}`);
  if (f.git) console.log(`分支：${f.branch}（基础分支 ${f.base || '未找到'}），未提交 ${f.dirty}，领先 ${f.ahead}`);
  console.log(`类型：${f.cocos ? 'Cocos 小游戏' : f.web ? 'Web' : '其他'}；验证约定 ${yn(f.verifySection)}；tests/e2e ${yn(f.e2eDir)}；功能地图 ${yn(f.features)}；票据 ${f.tickets}；未决决策票 ${f.decisions}；规格 ${yn(f.spec)}`);
  console.log(`\n节点：${r.node}（${r.why}）\n下一步：`);
  r.next.forEach((n, i) => console.log(`  ${i + 1}. ${n}`));
  if (r.hints.length) { console.log('另外：'); r.hints.forEach((h) => console.log(`  - ${h}`)); }
  console.log('\n节点是按文件状态推断的，和你实际在做的事不符时以你为准。');
}

// 经软链（分层桩、library）调用时 argv[1] 是链接路径，要比真实路径
if (process.argv[1] && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) main();
