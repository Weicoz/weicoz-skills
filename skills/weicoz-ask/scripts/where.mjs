#!/usr/bin/env node
// 只读：读当前仓库状态，判断所处节点，给出下一步该用的 skill。
// 用法：node where.mjs [--repo <目录>] [--base <基础分支>] [--json]
import { existsSync, readFileSync, readdirSync, statSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const git = (dir, ...a) => {
  const r = spawnSync('git', a, { cwd: dir, encoding: 'utf8' });
  return r.status === 0 ? r.stdout.trim() : null;
};
const readOr = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const list = (d) => { try { return readdirSync(d); } catch { return []; } };

export function collect(dir, base) {
  const f = { dir, git: git(dir, 'rev-parse', '--is-inside-work-tree') === 'true' };
  const pj = (() => { try { return JSON.parse(readOr(join(dir, 'package.json'))); } catch { return {}; } })();
  f.cocos = Boolean(pj.creator) || (existsSync(join(dir, 'assets')) && existsSync(join(dir, 'settings')));
  const deps = { ...pj.dependencies, ...pj.devDependencies };
  f.web = !f.cocos && ['next', 'vite', 'react', 'vue', 'svelte', '@sveltejs/kit', 'nuxt', 'astro'].some((d) => d in deps);
  const agents = readOr(join(dir, 'AGENTS.md'));
  f.verifySection = /^##\s*验证约定/m.test(agents);
  f.e2eDir = existsSync(join(dir, 'tests/e2e'));
  f.features = existsSync(join(dir, 'tests/e2e/FEATURES.md'));
  f.pending = existsSync(join(dir, 'docs/PENDING.md'));
  const scratch = list(join(dir, '.scratch'));
  // 只数 Matt 本地票据（.scratch/<功能>/issues/*.md）里未关闭的；docs/tasks 这类没有状态行，判断不了是否已做完
  const closed = /^\*{0,2}Status:?\*{0,2}\s*(resolved|done|closed|wontfix|已完成|完成)/im;
  f.tickets = scratch.reduce((n, s) => n + list(join(dir, '.scratch', s, 'issues'))
    .filter((x) => x.endsWith('.md') && !closed.test(readOr(join(dir, '.scratch', s, 'issues', x)))).length, 0);
  f.spec = existsSync(join(dir, 'docs/spec.md')) || scratch.some((s) => existsSync(join(dir, '.scratch', s, 'spec.md')));
  f.worktrees = list(join(dir, '.worktrees')).length;
  const shots = [join(dir, 'temp/web-verify/contact.png'), ...list(join(dir, 'temp')).filter((x) => /^contact.*\.png$/.test(x)).map((x) => join(dir, 'temp', x))];
  const newest = Math.max(0, ...shots.filter(existsSync).map((p) => statSync(p).mtimeMs));
  f.evidenceHours = newest ? Math.round((Date.now() - newest) / 36e5) : null;
  if (!f.git) return f;
  f.branch = git(dir, 'branch', '--show-current') || '(游离 HEAD)';
  f.base = base || ['develop', 'main', 'master'].find((b) => git(dir, 'rev-parse', '--verify', '-q', b) !== null) || null;
  f.onBase = f.branch === f.base;
  f.dirty = (git(dir, 'status', '--porcelain') || '').split('\n').filter(Boolean).length;
  f.ahead = f.base && !f.onBase ? Number(git(dir, 'rev-list', '--count', `${f.base}..HEAD`) || 0) : 0;
  return f;
}

export function classify(f) {
  const hints = [];
  const out = (node, why, next) => ({ node, why, next, hints });
  if (f.cocos) hints.push('小游戏项目：阶段和人工检查点以 weicoz-game-flow 为准，先读它判断当前阶段' + (f.pending ? '（看 docs/PENDING.md）' : ''));
  if (f.web && !f.e2eDir) hints.push('Web 项目还没有端到端流程：按 weicoz-verify 的 references/e2e-authoring.md 补');
  if (f.e2eDir && !f.features) hints.push('有 tests/e2e 但没有功能地图：按 e2e-authoring.md 第 1 步补 tests/e2e/FEATURES.md');
  if (f.spec && f.tickets === 0) hints.push('有规格没有票据：to-tickets');
  if (f.worktrees > 3) hints.push(`.worktrees 下有 ${f.worktrees} 个目录：weicoz-govern 体检列清理候选`);
  if (f.evidenceHours !== null && f.evidenceHours > 72 && (f.dirty || f.ahead)) hints.push(`最近一次验证证据是 ${f.evidenceHours} 小时前，交付前要重跑`);

  if (!f.git) return out('未建仓', '当前目录不是 git 仓库', ['git init 并做首次提交', f.cocos ? 'weicoz-game-flow 阶段 0' : 'setup-matt-pocock-skills 配置票据与文档位置']);
  if (!f.verifySection) return out('验证未接入', 'AGENTS.md 没有“## 验证约定”', [
    f.cocos ? 'weicoz-game-flow 的 references/project-agents.md 模板' : 'weicoz-verify 第 1 节，模板 references/project-section.md',
    '写完让用户确认快检、全检命令，再开始实现',
  ]);
  const b = f.base || '<基础分支>';
  if (f.dirty > 0) return out('实现中', `工作区有 ${f.dirty} 处未提交改动`, [
    '每轮写完跑快检；按 weicoz-implement-verified 第 2 步走',
    `提交前 weicoz-code-review ${b} --repo <当前目录>（审到工作区，含未跟踪文件）`,
    `收尾跑全检并带 --base ${b}，结论“通过”后再提交`,
  ]);
  if (f.ahead > 0) return out('待合并', `分支 ${f.branch} 比 ${b} 多 ${f.ahead} 个提交，工作区干净`, [
    `全检带 --base ${b}，确认结论行是“结论：通过”`,
    `weicoz-code-review ${b}..HEAD`,
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
  const opt = (k) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : undefined; };
  const known = new Set(['--repo', '--base', '--json']);
  const bad = a.filter((x, i) => x.startsWith('--') && !known.has(x) && !['--repo', '--base'].includes(a[i - 1]));
  if (bad.length) { console.error(`未知参数：${bad.join(' ')}\n用法：node where.mjs [--repo <目录>] [--base <基础分支>] [--json]`); process.exit(2); }
  const f = collect(resolve(opt('--repo') || '.'), opt('--base'));
  const r = classify(f);
  if (a.includes('--json')) { console.log(JSON.stringify({ facts: f, ...r }, null, 2)); return; }
  const yn = (v) => (v ? '有' : '无');
  console.log(`目录：${f.dir}`);
  if (f.git) console.log(`分支：${f.branch}（基础分支 ${f.base || '未找到'}），未提交 ${f.dirty}，领先 ${f.ahead}`);
  console.log(`类型：${f.cocos ? 'Cocos 小游戏' : f.web ? 'Web' : '其他'}；验证约定 ${yn(f.verifySection)}；tests/e2e ${yn(f.e2eDir)}；功能地图 ${yn(f.features)}；票据 ${f.tickets}；规格 ${yn(f.spec)}`);
  console.log(`\n节点：${r.node}（${r.why}）\n下一步：`);
  r.next.forEach((n, i) => console.log(`  ${i + 1}. ${n}`));
  if (r.hints.length) { console.log('另外：'); r.hints.forEach((h) => console.log(`  - ${h}`)); }
  console.log('\n节点是按文件状态推断的，和你实际在做的事不符时以你为准。');
}

// 经软链（分层桩、library）调用时 argv[1] 是链接路径，要比真实路径
if (process.argv[1] && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) main();
