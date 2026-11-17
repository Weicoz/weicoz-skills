// web-verify 的纯逻辑：参数解析、配置合并、结论行、忽略规则、env 文件解析。不依赖浏览器。
import os from 'node:os';

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
};

export function parseArgs(argv) {
  const out = { project: null, quick: false, baseUrl: null, scripts: [], noStart: false, envFile: null };
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
    else if (a === '--env-file') out.envFile = need();
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
