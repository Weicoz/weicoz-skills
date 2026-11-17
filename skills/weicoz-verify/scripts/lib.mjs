// web-verify 的纯逻辑：参数解析、配置合并、结论行、忽略规则、env 文件解析。不依赖浏览器。
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';

export const DEFAULT_VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1440, height: 900 },
];

export const DEFAULT_CONFIG = {
  baseUrl: 'http://127.0.0.1:3000',
  start: null, // { command, readyPath, timeoutSec, envFile }
  checks: { quick: [], full: [] }, // [{ name, cmd, timeoutSec }]
  viewports: DEFAULT_VIEWPORTS,
  flows: 'tests/e2e/*.flow.mjs',
  quickFlows: [], // 只写流程名，不带 .flow.mjs
  ignore: { console: [], pageerror: [], requests: [] }, // 正则字符串
  flowTimeoutSec: 180, // 单个流程（含全部视口中的一个）整体超时
};

export function parseArgs(argv) {
  const out = { project: null, quick: false, baseUrl: null, scripts: [], noStart: false, envFile: null, noChecks: false, base: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const need = () => {
      const v = argv[++i];
      if (v === undefined || v.startsWith('--')) throw new Error(`参数 ${a} 缺少值`);
      return v;
    };
    if (a === '--project') out.project = need();
    else if (a === '--quick') out.quick = true;
    else if (a === '--base-url') out.baseUrl = need();
    else if (a === '--script') out.scripts.push(need());
    else if (a === '--no-start') out.noStart = true;
    else if (a === '--no-checks') out.noChecks = true;
    else if (a === '--env-file') out.envFile = need();
    else if (a === '--base') out.base = need();
    else throw new Error(`未知参数：${a}`);
  }
  if (!out.project) throw new Error('缺少 --project <目录>');
  return out;
}

// 浅层字段整体覆盖；ignore 与 checks 按子键合并，避免漏写子键时丢默认值。
export function mergeConfig(user = {}, args = {}) {
  const cfg = {
    ...DEFAULT_CONFIG,
    ...user,
    checks: { ...DEFAULT_CONFIG.checks, ...(user.checks || {}) },
    ignore: { ...DEFAULT_CONFIG.ignore, ...(user.ignore || {}) },
  };
  if (!Array.isArray(cfg.viewports) || cfg.viewports.length === 0) cfg.viewports = DEFAULT_VIEWPORTS;
  if (args.baseUrl) cfg.baseUrl = args.baseUrl;
  if (args.noStart) cfg.start = null;
  cfg.baseUrl = cfg.baseUrl.replace(/\/+$/, '');
  return cfg;
}

export function matchIgnore(text, patterns = []) {
  return patterns.some((p) => {
    try {
      return new RegExp(p).test(text);
    } catch {
      return text.includes(p); // 非法正则退化为子串匹配
    }
  });
}

// items: [{ status: 'pass'|'fail'|'unverified', name, missing? }]
export function verdict(items) {
  const fails = items.filter((i) => i.status === 'fail').map((i) => i.name);
  if (fails.length) return { code: 1, line: `结论：不通过（失败：${fails.join('、')}）` };
  const missing = [...new Set(items.filter((i) => i.status === 'unverified').map((i) => i.missing || i.name))];
  if (missing.length) return { code: 3, line: `结论：未验证（缺：${missing.join('、')}）` };
  return { code: 0, line: '结论：通过' };
}

export function parseEnvFile(text) {
  const env = {};
  for (const raw of text.split(/\r?\n/)) {
    const m = raw.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    else v = v.replace(/\s+#.*$/, '');
    env[m[1]] = v;
  }
  return env;
}

export function expandHome(p) {
  return p === '~' || p.startsWith('~/') ? os.homedir() + p.slice(1) : p;
}

export function loadLine(load1 = os.loadavg()[0], cores = os.cpus().length) {
  const high = load1 > cores ? '，高于核数，超时类失败优先怀疑环境' : '';
  return `负载：1 分钟 ${load1.toFixed(2)}，CPU 核数 ${cores}${high}`;
}

export function tailLines(text, n = 5) {
  return text.trim().split(/\r?\n/).slice(-n).join('\n');
}

// 命令失败时的说明：优先取测试运行器的最终失败行（vitest/jest 的 FAIL、node:test 的 not ok、pytest 的 FAILED）；
// 没有时再取逐条标记（× / ✗，可能含重试中途的失败）；都没有时退回末尾 n 行。去重后最多 n 行。
export function failureLines(text, n = 5) {
  const clean = text.replace(/\x1b\[[0-9;]*m/g, '');
  const lines = clean.split(/\r?\n/).map((l) => l.trim());
  let hits = [...new Set(lines.filter((l) => /^(FAIL\s|not ok\s|FAILED\s)/.test(l)))];
  if (!hits.length) hits = [...new Set(lines.filter((l) => /^[×✗]\s/.test(l)))];
  if (!hits.length) return tailLines(clean, n);
  const more = hits.length > n ? `\n（另有 ${hits.length - n} 条失败）` : '';
  return hits.slice(0, n).join('\n') + more;
}

export function safeName(s) {
  return s.replace(/[^\p{L}\p{N}_.-]+/gu, '-').replace(/^-+|-+$/g, '') || 'x';
}

// 单个流程的结论。失败（步骤、problems、流程异常）优先；其次未验证；零 step 记失败。
export function flowStatus({ stepFailed = false, flowError = false, problems = 0, unverifiedWhy = null, stepCount = 0 }) {
  if (stepFailed || flowError || problems > 0) return 'fail';
  if (unverifiedWhy) return 'unverified';
  if (stepCount === 0) return 'zero';
  return 'pass';
}

// 缩小范围的开关。--base-url / --no-start 不算：对部署环境跑是正当全检。
export function partialSwitches(args) {
  return [args.noChecks && '--no-checks', args.scripts?.length && '--script'].filter(Boolean);
}

export function partialItem(args) {
  const sw = partialSwitches(args);
  if (!sw.length) return null;
  return { status: 'unverified', name: '完整档', missing: `完整${args.quick ? '快检' : '全检'}，本次用了 ${sw.join('、')}` };
}

// 能匹配空串的 ignore 模式会吞掉一切（"."、".*" 等），视为配置错误。非法正则按子串，仅空串有害。
// 探针：空串与无意义文本都命中的模式（"."、".*"、"\\w"）会吞掉一切。
const PROBES = ['', 'zq9~', '#@ !'];
export function badIgnorePatterns(ignore = {}) {
  const bad = [];
  for (const [kind, list] of Object.entries(ignore)) {
    for (const p of list || []) {
      let hit;
      try {
        const re = new RegExp(p);
        hit = PROBES.some((t) => re.test(t));
      } catch { hit = p === ''; }
      if (hit) bad.push(`${kind}:${p}`);
    }
  }
  return bad;
}

// 去掉有害模式后的 ignore，供继续跑流程用。
export function cleanIgnore(ignore = {}) {
  const out = {};
  for (const [kind, list] of Object.entries(ignore)) out[kind] = (list || []).filter((p) => badIgnorePatterns({ [kind]: [p] }).length === 0);
  return out;
}

// --script 既可写路径，也可写流程名（smoke -> <flows 目录>/smoke.flow.mjs 或 smoke.mjs）。
export function resolveScript(s, project, flowsDir, exists = fs.existsSync) {
  const direct = path.resolve(project, expandHome(s));
  if (exists(direct) || s.includes('/') || s.endsWith('.mjs')) return direct;
  for (const f of [`${s}.flow.mjs`, `${s}.mjs`]) if (exists(path.join(flowsDir, f))) return path.join(flowsDir, f);
  return direct;
}

// package.json 里 verify:* 脚本相对基线的变化，返回变动的键。
export function verifyScriptsChanged(oldText, newText) {
  const pick = (t) => {
    try { return JSON.parse(t || '{}').scripts || {}; } catch { return {}; }
  };
  const a = pick(oldText);
  const b = pick(newText);
  const keys = new Set([...Object.keys(a), ...Object.keys(b)].filter((k) => k.startsWith('verify:')));
  return [...keys].filter((k) => a[k] !== b[k]).sort();
}

export function withTimeout(promise, sec, label) {
  let t;
  const timeout = new Promise((_, rej) => { t = setTimeout(() => rej(new Error(`${label}超过 ${sec} 秒未结束`)), sec * 1000); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(t));
}
