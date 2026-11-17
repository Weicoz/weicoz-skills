#!/usr/bin/env node
// 项目体检：只读，只用 Node 内置模块与 git。结论行见最后一行；始终退出码 0，脚本自身出错退出码 2。
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve, dirname, basename, sep } from 'node:path';
import { homedir } from 'node:os';

const SIZE_HIGH = 10 * 1024;
const SIZE_LOW = 8 * 1024;
const SKIP_DIRS = new Set(['node_modules', '.git', '.worktrees', 'dist', 'build', 'coverage', '.next', 'library', 'temp', 'local']);
const ARCHIVE_RE = /(^|\/)(archive|archived|归档|history|changelog|CHANGELOG|\.scratch|tmp)[^/]*(\/|$|\.)/i;
const LEVELS = { 高: 0, 中: 1, 低: 2 };

export function parseArgs(argv) {
  const o = { project: null, json: false, staleDays: 90, base: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--project') o.project = argv[++i];
    else if (argv[i] === '--json') o.json = true;
    else if (argv[i] === '--stale-days') o.staleDays = Number(argv[++i]);
    else if (argv[i] === '--base') o.base = argv[++i];
    else throw new Error(`未知参数: ${argv[i]}`);
  }
  if (!o.project) throw new Error('用法: node govern-audit.mjs --project <目录> [--json] [--stale-days N] [--base <集成分支>]');
  return o;
}

function git(cwd, args, ok = false) {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 64 << 20 });
  } catch (e) {
    if (ok) return null;
    throw e;
  }
}

function listFiles(root) {
  const out = git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], true);
  let files;
  if (out !== null) files = out.split('\0').filter(Boolean);
  else {
    files = [];
    const walk = (d) => {
      for (const e of readdirSync(d, { withFileTypes: true })) {
        if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) walk(join(d, e.name)); }
        else files.push(relative(root, join(d, e.name)).split(sep).join('/'));
      }
    };
    walk(root);
  }
  return files.filter((f) => !f.split('/').some((p) => p === 'node_modules' || p === '.worktrees') && existsSync(join(root, f)));
}

const read = (p) => { try { return readFileSync(p, 'utf8'); } catch { return ''; } };

// ---------- 检查 1：AGENTS.md / CLAUDE.md ----------
function checkAgents(root, add) {
  const a = join(root, 'AGENTS.md');
  if (!existsSync(a)) add('中', 'AGENTS.md:1', '缺少 AGENTS.md（项目地图与任务路由）', '新建，4–8 KB，写地图与按任务路由');
  else {
    const size = statSync(a).size;
    const kb = (size / 1024).toFixed(1);
    if (size > SIZE_HIGH) add('高', 'AGENTS.md:1', `体积 ${kb} KB，超过 10 KB`, '必须拆分：细节移入按任务读取的子文档');
    else if (size > SIZE_LOW) add('低', 'AGENTS.md:1', `体积 ${kb} KB，接近 10 KB 上限`, '建议 4–8 KB，提前拆分');
  }
  const c = join(root, 'CLAUDE.md');
  if (existsSync(c)) {
    const t = read(c).trim();
    if (t !== '@AGENTS.md') add('中', 'CLAUDE.md:1', 'CLAUDE.md 不是单行 `@AGENTS.md`', '内容并入 AGENTS.md，CLAUDE.md 只留 `@AGENTS.md`');
  } else if (existsSync(a)) add('低', 'CLAUDE.md:1', '缺少 CLAUDE.md 入口', '新建，内容只写 `@AGENTS.md`');
}

// ---------- 检查 2、3：文档死链与疑似过期 ----------
function mdLines(text) {
  // 返回 [{n, s, fence}]，围栏代码块内 fence=true
  let fence = false;
  return text.split('\n').map((s, i) => {
    if (/^\s*(```|~~~)/.test(s)) { fence = !fence; return { n: i + 1, s, fence: true }; }
    return { n: i + 1, s, fence };
  });
}

function checkDocs(root, files, add, staleDays) {
  const docs = files.filter((f) => /\.md$/i.test(f) && !ARCHIVE_RE.test(f));
  const fileSet = new Set(files);
  const now = Date.now() / 1000;
  for (const doc of docs) {
    const lines = mdLines(read(join(root, doc)));
    const dir = dirname(doc);
    // 死链
    for (const { n, s, fence } of lines) {
      if (fence) continue;
      const text = s.replace(/`[^`]*`/g, '');
      for (const m of text.matchAll(/\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/g)) {
        let t = m[1];
        if (/^([a-z][a-z0-9+.-]*:|#|\/\/)/i.test(t)) continue;
        t = t.split('#')[0].split('?')[0].replace(/:\d+(-\d+)?$/, ''); // 去掉 path:行号 后缀
        if (!t || /[<>{}*]|\.\.\.|\b(NN|XX|YYYY)\b/.test(t)) continue; // 占位符链接
        try { t = decodeURIComponent(t); } catch { /* 保持原样 */ }
        if (t.startsWith(root + '/')) t = t.slice(root.length + 1); // 指向本项目的绝对路径
        if (t.startsWith('.worktrees/')) continue; // 临时 worktree 里的路径，随 worktree 清理而消失
        else if (/^\/(Users|home|private|opt|var|tmp|etc)\//.test(t)) continue; // 本机其他位置，属环境
        const abs = t.startsWith('/') ? join(root, t) : resolve(root, dir, t);
        if (!existsSync(abs)) add('中', `${doc}:${n}`, `死链 ${m[1]}`, '修正链接或删除该引用');
      }
    }
    // 疑似过期
    const ct = git(root, ['log', '-1', '--format=%ct', '--', doc], true)?.trim();
    if (!ct) continue;
    const age = Math.floor((now - Number(ct)) / 86400);
    if (age < staleDays) continue;
    const missing = [];
    for (const { n, s, fence } of lines) {
      if (fence) continue;
      for (const m of s.matchAll(/`([^`\n]+)`/g)) {
        const p = pathLike(m[1]);
        if (!p) continue;
        const top = p.split('/')[0];
        if (!existsSync(join(root, top)) && !existsSync(resolve(root, dir, top))) continue; // 首段目录不存在：多半是别的仓库或 API 路径，不判定
        const cands = [join(root, p), resolve(root, dir, p)];
        const hit = cands.some((c) => existsSync(c)) || fileSet.has(p) || [...fileSet].some((f) => f.startsWith(p.replace(/\/$/, '') + '/'));
        if (!hit && !missing.some((x) => x.p === p)) missing.push({ p, n });
      }
    }
    if (missing.length) {
      const list = missing.slice(0, 3).map((x) => x.p).join('、');
      add('中', `${doc}:${missing[0].n}`, `疑似过期：${age} 天未改，引用的 ${missing.length} 个路径已不存在（${list}）`, '核对后更新，或确认是一次性过程文档后归档');
    }
  }
}

function pathLike(s) {
  s = s.trim();
  if (!s || /[\s<>{}*$|=:()\[\]"',;!?]/.test(s) || /^(~|\.\.?$|https?|\/)/.test(s) && !/^\.\.?\//.test(s) && !/^\//.test(s)) return null;
  if (/^(~|\/)/.test(s)) return null; // 绝对路径与家目录路径属环境，不判定
  s = s.replace(/^\.\//, '');
  if (/^(node_modules|dist|build|coverage|\.env|\.git|library|temp|local|out)(\/|$)/.test(s)) return null;
  if (/\/$/.test(s) && /^[\w.@-]+(\/[\w.@-]+)*\/$/.test(s)) return s.length > 3 && s.includes('/') ? s : null;
  if (/^[\w.@-]+(\/[\w.@-]+)+$/.test(s)) return /\.[A-Za-z][A-Za-z0-9]{0,7}$/.test(s) ? s : null; // 无扩展名的多段路径多是 API 路由，不判定
  return null;
}

// ---------- 检查 4：测试清单与孤儿测试 ----------
const TEST_NAME = /(\.(test|spec)\.[cm]?[jt]sx?$)|(\/__tests__\/.+\.[cm]?[jt]sx?$)|(^__tests__\/.+\.[cm]?[jt]sx?$)/;

export function globToRe(g) {
  let r = '', i = 0;
  while (i < g.length) {
    const c = g[i];
    if (c === '*' && g[i + 1] === '*') { if (g[i + 2] === '/') { r += '(?:.*/)?'; i += 3; } else { r += '.*'; i += 2; } }
    else if (c === '*') { r += '[^/]*'; i++; }
    else if (c === '?') { r += '[^/]'; i++; }
    else if (c === '{') { const e = g.indexOf('}', i); r += '(?:' + g.slice(i + 1, e).split(',').map((x) => globToRe(x).source.slice(1, -1)).join('|') + ')'; i = e + 1; }
    else { r += c.replace(/[.+^$()|[\]\\]/g, '\\$&'); i++; }
  }
  return new RegExp('^' + r + '$');
}

const DEFAULTS = {
  vitest: [/^(?:.*\/)?[^/]*\.(?:test|spec)\.[cm]?[jt]sx?$/],
  jest: [/^(?:.*\/)?__tests__\/.*\.[jt]sx?$/, /^(?:.*\/)?(?:[^/]*\.)?(?:spec|test)\.[jt]sx?$/],
};

function findRunners(root, files) {
  const runners = []; // {dir, kind, patterns, unknown}
  let rootPj = null;
  for (const f of files) {
    const b = basename(f);
    const dir = dirname(f) === '.' ? '' : dirname(f);
    let kind = null;
    if (/^vitest(\.workspace)?\.config\.[cm]?[jt]s$/.test(b) || /^vitest\.config\./.test(b)) kind = 'vitest';
    else if (/^vite\.config\.[cm]?[jt]s$/.test(b) && /\btest\s*:/.test(read(join(root, f)))) kind = 'vitest';
    else if (/^jest\.config\.[cm]?[jt]s$|^jest\.config\.json$/.test(b)) kind = 'jest';
    else if (b === 'package.json') {
      try {
        const pj = JSON.parse(read(join(root, f)));
        if (pj.jest) { runners.push({ dir, kind: 'jest', patterns: pj.jest.testMatch ? pj.jest.testMatch.map(globToRe) : DEFAULTS.jest, unknown: !!pj.jest.testRegex, base: dir }); }
        else if (dir === '') rootPj = pj;
      } catch { /* 忽略损坏的 package.json */ }
      continue;
    } else continue;
    const src = read(join(root, f));
    let patterns = kind === 'vitest' ? DEFAULTS.vitest : DEFAULTS.jest;
    let unknown = false;
    const key = kind === 'vitest' ? 'include' : 'testMatch';
    const km = src.match(new RegExp(`\\b${key}\\s*:\\s*\\[([^\\]]*)\\]`));
    if (km) {
      const strs = [...km[1].matchAll(/(['"`])([^'"`]+)\1/g)].map((x) => x[2]);
      if (strs.length) patterns = strs.map((x) => globToRe(x.replace(/^\.\//, '')));
      else unknown = true;
    } else if (new RegExp(`\\b${key}\\s*:`).test(src) || /testRegex\s*:/.test(src)) unknown = true;
    runners.push({ dir, kind, patterns, unknown, base: dir });
  }
  if (rootPj && !runners.some((r) => r.dir === '')) { // 没有配置文件时按依赖推断默认规则
    const deps = { ...rootPj.dependencies, ...rootPj.devDependencies };
    if (deps.vitest) runners.push({ dir: '', kind: 'vitest', patterns: DEFAULTS.vitest, unknown: false, base: '' });
    else if (deps.jest) runners.push({ dir: '', kind: 'jest', patterns: DEFAULTS.jest, unknown: false, base: '' });
  }
  return runners.sort((a, b) => b.dir.length - a.dir.length);
}

function lineOf(text, re) {
  const i = text.search(re);
  return i < 0 ? 1 : text.slice(0, i).split('\n').length;
}

function checkTests(root, files, add) {
  const tests = files.filter((f) => TEST_NAME.test(f) && /\.[cm]?[jt]sx?$/.test(f));
  const info = { total: tests.length, byRunner: {} };
  const pj = (() => { try { return JSON.parse(read(join(root, 'package.json'))); } catch { return {}; } })();
  const scripts = Object.entries(pj.scripts || {});
  // 快慢分层：快检脚本混入重测
  for (const [k, v] of scripts) {
    if (/^(test|test:fast|test:quick|check|verify:fast)$/.test(k) && /\b(e2e|playwright|cypress|integration)\b/i.test(v) && !/--(grep-invert|exclude)/.test(v))
      add('中', `package.json:${lineOf(read(join(root, 'package.json')), new RegExp(`"${k}"`))}`, `脚本 ${k} 混入重测（${v.slice(0, 60)}）`, '重测拆到单独脚本，快检只留秒级与相关单测');
  }

  if (!tests.length) return info;
  const runners = findRunners(root, files);
  const corpusFiles = files.filter((f) => /^(package\.json|Makefile|justfile)$|^(\.github|\.gitlab|scripts|\.githooks|\.husky)\//.test(f) || /^\.gitlab-ci\.yml$/.test(f));
  const corpus = corpusFiles.map((f) => read(join(root, f))).join('\n');
  const nodeTestScripts = scripts.map(([, v]) => v).filter((v) => /node\s+(\S+\s+)*--test/.test(v));

  for (const f of tests) {
    const src = read(join(root, f));
    let kind;
    const usesNodeTest = /from\s+['"]node:test['"]|require\(['"]node:test['"]\)/.test(src);
    if (usesNodeTest) {
      kind = 'node:test';
      const d = dirname(f);
      const covered = nodeTestScripts.some((v) => { const m = v.match(/--test\S*\s+(.*)$/); const args = m ? m[1].trim() : ''; return !args || args.split(/\s+/).some((a) => !a.startsWith('-') && (f.startsWith(a.replace(/^\.\//, '')) || d.startsWith(a.replace(/^\.\//, '').replace(/\/$/, '')))); });
      info.byRunner[kind] = (info.byRunner[kind] || 0) + 1;
      if (!covered && !referenced(f, corpus)) add('中', `${f}:1`, '孤儿测试：用 node:test 但无 `node --test` 脚本覆盖，也没被任何脚本引用', '接入测试脚本，或确认作废后删除（须先征得确认）');
      continue;
    }
    const r = runners.find((x) => x.dir === '' || f.startsWith(x.dir + '/'));
    if (!r) {
      kind = '未识别';
      info.byRunner[kind] = (info.byRunner[kind] || 0) + 1;
      if (!referenced(f, corpus)) add('低', `${f}:1`, '待确认：未找到 vitest/jest 配置，也没被任何脚本引用，无法判断由谁运行', '确认测试运行器；无人运行则接入或删除');
      continue;
    }
    kind = r.kind;
    info.byRunner[kind] = (info.byRunner[kind] || 0) + 1;
    const rel = r.dir ? f.slice(r.dir.length + 1) : f;
    if (r.patterns.some((p) => p.test(rel))) continue;
    if (r.unknown) { add('低', `${f}:1`, `待确认：${kind} 配置的匹配规则无法静态解析`, '人工核对该文件是否被运行'); continue; }
    if (referenced(f, corpus)) continue;
    add('中', `${f}:1`, `孤儿测试：不在 ${kind} 的匹配范围内，也没被任何脚本引用`, '改配置纳入、接入脚本，或确认作废后删除（须先征得确认）');
  }

  // 假测试
  for (const f of tests) {
    const src = read(join(root, f));
    const lines = src.split('\n');
    lines.forEach((s, i) => {
      const n = i + 1;
      if (/\b(it|test|describe)\.only\s*\(/.test(s)) add('高', `${f}:${n}`, '遗留 .only：其他用例被静默跳过', '删除 .only');
      else if (/\b(it|test|describe)\.skip\s*\(|\b(xit|xtest|xdescribe)\s*\(/.test(s)) add('低', `${f}:${n}`, '遗留 skip 的测试', '修复启用，或确认作废后删除');
      if (/expect\(\s*(true|false|1|0|null|undefined|(['"`])[^'"`]*\2)\s*\)\s*\.(toBe|toEqual|toStrictEqual)\(\s*(true|false|1|0|null|undefined|(['"`])[^'"`]*\4)\s*\)/.test(s) || /\bassert(\.ok|\.equal)?\(\s*true\s*[,)]/.test(s) || /\bassert\.(strictEqual|equal)\(\s*(\d+|true|false)\s*,\s*\1\s*\)/.test(s))
        add('中', `${f}:${n}`, '断言常量：不依赖被测代码，永远通过', '改成断言被测代码的真实输出');
      const m = s.match(/(?:setTimeout\([^,]*,|sleep\(|waitForTimeout\(|delay\()\s*(\d[\d_]*)/);
      if (m && Number(m[1].replace(/_/g, '')) >= 1000) add('低', `${f}:${n}`, `固定长等待 ${m[1]} ms：慢且易抖`, '改为等待条件成立（轮询或事件）');
    });
    // 零断言用例：同文件内含断言的辅助函数，调用它也算断言
    const helpers = [];
    lines.forEach((s, i) => {
      const m = s.match(/^\s*(?:async\s+)?function\s+(\w+)/) || s.match(/^\s*(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:function|\()/);
      if (m && /\b(expect|assert)\b/.test(lines.slice(i, i + 15).join('\n'))) helpers.push(m[1]);
    });
    const helperRe = helpers.length ? new RegExp(`\\b(${helpers.join('|')})\\s*\\(`) : null;
    const starts = [];
    lines.forEach((s, i) => { const m = s.match(/^\s*(?:it|test)(?:\.each\([^)]*\))?\s*\(\s*(['"`])/); if (m) starts.push(i); });
    starts.forEach((st, k) => {
      const end = k + 1 < starts.length ? starts[k + 1] : lines.length;
      const body = lines.slice(st, end).join('\n');
      if (!(helperRe && helperRe.test(body)) && !/\b(expect|assert|should|toMatch|toThrow|t\.(ok|equal|deepEqual|is|truthy|throws|match|rejects)|verify\w*|check\w*|ok)\s*[(.]/.test(body) && !/\.only|skip/.test(lines[st]))
        add('中', `${f}:${st + 1}`, '可疑零断言用例：块内未见 expect/assert（辅助函数里断言则为误报）', '补断言；若断言在辅助函数里，确认后忽略');
    });
  }
  return info;
}

function referenced(f, corpus) {
  return corpus.includes(f) || corpus.includes(basename(f));
}

// ---------- 检查 5：worktree ----------
// 基线：--base 优先；否则 origin/HEAD，再否则 main / master。集成分支不是默认分支的项目（如 develop）必须传 --base。
function pickBase(root, base) {
  if (base) return git(root, ['rev-parse', '--verify', '-q', base], true) !== null ? base : null;
  return git(root, ['symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], true)?.trim()
    || ['main', 'master'].find((b) => git(root, ['rev-parse', '--verify', '-q', b], true) !== null) || null;
}

function checkWorktrees(root, add, base) {
  const out = git(root, ['worktree', 'list', '--porcelain'], true);
  if (!out) return;
  const wts = out.trim().split('\n\n').map((b) => {
    const o = {};
    for (const l of b.split('\n')) { const [k, ...v] = l.split(' '); o[k] = v.join(' '); }
    return o;
  });
  if (wts.length < 2) return;
  const main = wts[0];
  if (!base) return;
  const baseShort = base.replace(/^origin\//, '');
  const home = homedir();
  for (const w of wts.slice(1)) {
    const shown = w.worktree.startsWith(home) ? '~' + w.worktree.slice(home.length) : w.worktree;
    const tip = w.HEAD;
    const branch = (w.branch || '').replace('refs/heads/', '') || '(游离 HEAD)';
    if (branch === baseShort) continue;
    const where = `${shown}:1`;
    if (w.prunable !== undefined) { add('低', where, `目录已丢失，worktree 记录残留（${branch}）`, '候选：`git worktree prune`（须先征得确认）'); continue; }
    const dirty = (git(w.worktree, ['status', '--porcelain'], true) || '').trim();
    let state, advice;
    const isAnc = git(root, ['merge-base', '--is-ancestor', tip, base], true) !== null;
    const reflog = w.branch ? (git(root, ['reflog', 'show', '--format=%H', w.branch], true) || '').trim().split('\n').filter(Boolean) : [];
    if (isAnc && reflog.length && reflog[reflog.length - 1] === tip && reflog.length <= 1) { state = '没有独立提交'; advice = '分支尚无自己的提交；确认不再需要后可清理'; }
    else if (isAnc) { state = '已合并（普通合并或快进）'; advice = '内容已在 ' + base + '，可作清理候选'; }
    else {
      const cherry = (git(root, ['cherry', base, tip], true) || '').trim().split('\n').filter(Boolean);
      const mt = git(root, ['merge-tree', '--write-tree', base, tip], true);
      const baseTree = git(root, ['rev-parse', base + '^{tree}'], true)?.trim();
      if (cherry.length && cherry.every((l) => l.startsWith('-'))) { state = '已合并（变基合并，补丁等价）'; advice = '内容已在 ' + base + '，可作清理候选'; }
      else if (mt && mt.trim().split('\n')[0] === baseTree) { state = '已合并（squash 合并，树内容一致）'; advice = '内容已在 ' + base + '，可作清理候选；分支需 `git branch -D`'; }
      else { state = '未合入'; advice = '有未合入的提交，不得清理；先决定合并或放弃'; }
    }
    const merged = state !== '未合入' && state !== '没有独立提交';
    const lvl = dirty ? '中' : '低';
    add(lvl, where, `worktree ${branch}：${state}${dirty ? '，且有未提交改动' : ''}`, dirty ? '先处理未提交改动；' + advice : advice + (merged || state === '没有独立提交' ? '（只列候选，须先征得确认）' : ''));
  }
  void main;
}

// ---------- 主流程 ----------
export function audit(project, { staleDays = 90, base = null } = {}) {
  const root = resolve(project.replace(/^~(?=$|\/)/, homedir()));
  if (!existsSync(root) || !statSync(root).isDirectory()) throw new Error(`目录不存在: ${project}`);
  const findings = [];
  const add = (level, loc, msg, advice) => findings.push({ level, path: loc, message: msg, advice });
  const files = listFiles(root);
  checkAgents(root, add);
  checkDocs(root, files, add, staleDays);
  const tests = checkTests(root, files, add);
  const usedBase = pickBase(root, base);
  if (base && !usedBase) throw new Error(`基线分支不存在: ${base}`);
  checkWorktrees(root, add, usedBase);
  findings.sort((a, b) => LEVELS[a.level] - LEVELS[b.level]);
  const c = { 高: 0, 中: 0, 低: 0 };
  findings.forEach((f) => c[f.level]++);
  const conclusion = `结论：${findings.length} 项待处理（高 ${c.高}、中 ${c.中}、低 ${c.低}）`;
  return { project: root, base: usedBase, tests, findings, conclusion };
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith('govern-audit.mjs')) {
  try {
    const o = parseArgs(process.argv.slice(2));
    const r = audit(o.project, { staleDays: o.staleDays, base: o.base });
    if (o.json) console.log(JSON.stringify(r, null, 2));
    else {
      const rn = Object.entries(r.tests.byRunner).map(([k, v]) => `${k} ${v}`).join('、');
      console.log(`基线分支：${r.base || '（未找到，跳过 worktree 检查）'}（集成分支不是默认分支时用 --base 指定）`);
      console.log(`测试清单：共 ${r.tests.total} 个测试文件${rn ? `（${rn}）` : ''}`);
      for (const f of r.findings) console.log(`${f.level} ${f.path} ${f.message} 建议：${f.advice}`);
      console.log(r.conclusion);
    }
    process.exit(0);
  } catch (e) {
    console.error(`govern-audit 出错：${e.message}`);
    process.exit(2);
  }
}
