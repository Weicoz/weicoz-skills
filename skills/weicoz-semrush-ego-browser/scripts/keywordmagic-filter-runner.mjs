#!/usr/bin/env node
import { spawnSync } from 'node:child_process';

let activeTaskId = '';

function option(...names) {
  for (const name of names) {
    const index = process.argv.indexOf(`--${name}`);
    if (index >= 0) return process.argv[index + 1] ?? '';
  }
  return '';
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, redact(item)]));
  if (typeof value !== 'string') return value;
  try {
    const url = new URL(value);
    if (url.searchParams.has('__gmitm')) url.searchParams.set('__gmitm', '[redacted]');
    return url.toString();
  } catch {
    return value.replace(/([?&]__gmitm=)[^&\s"']+/g, '$1[redacted]');
  }
}

function fail(message, details = {}) {
  cleanupTask();
  console.error(JSON.stringify(redact({ success: false, error: message, ...details })));
  process.exit(1);
}

function cleanupTask() {
  if (!activeTaskId) return null;
  const taskId = activeTaskId;
  activeTaskId = '';
  return spawnSync('ego-browser', ['nodejs'], {
    input: `const result = await completeTaskSpace(${JSON.stringify(taskId)}, { keep: false })\ncliLog(JSON.stringify(result))\n`,
    encoding: 'utf8',
  });
}

function runEgo(source) {
  const result = spawnSync('ego-browser', ['nodejs'], {
    input: source,
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.error) fail('ego-browser unavailable', { detail: result.error.message });
  if (result.status !== 0) fail('ego-browser failed', { detail: (result.stderr || result.stdout).trim() });
  return result.stdout.trim();
}

function lastJson(output) {
  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean).reverse();
  for (const line of lines) {
    try { return JSON.parse(line); } catch {}
  }
  fail('ego-browser returned no JSON result', { output });
}

const query = option('query');
const db = option('db') || 'us';
const fid = option('fid') || process.env.WEICOZ_SEMRUSH_FID || '';
const seedUrlValue = option('seed-url', 'seedUrl');
const minVolume = option('minVolume');
const maxKd = option('maxKd');
const minCpc = option('minCpc');
const limit = Math.min(Math.max(Number(option('limit') || 20), 1), 100);
const taskName = option('task') || 'semrush keyword research';
const proxyHost = process.env.WEICOZ_SEMRUSH_PROXY_HOST;

if (!query || !seedUrlValue || !maxKd || !minCpc) {
  fail('Usage: --query --seed-url --maxKd --minCpc are required');
}
if (!proxyHost) fail('WEICOZ_SEMRUSH_PROXY_HOST is required');

let seedUrl;
try { seedUrl = new URL(seedUrlValue); } catch { fail('--seed-url must be an absolute URL'); }
const filter = seedUrl.searchParams.get('filter');
if (!filter) fail('The verified seed URL has no Semrush filter state');

const target = new URL(`https://${proxyHost}/analytics/keywordmagic/`);
target.searchParams.set('q', query);
target.searchParams.set('db', db);
if (fid) target.searchParams.set('fid', fid);
target.searchParams.set('filter', filter);
const gmitm = seedUrl.searchParams.get('__gmitm');
if (gmitm) target.searchParams.set('__gmitm', gmitm);

const pageScript = String.raw`(() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector('.sm-kmt-table__table');
  const headers = root ? [...root.querySelectorAll('.sm-table-layout__header-row .sm-table-cell-head[role="columnheader"]')].map((el) => clean(el.innerText)).filter(Boolean) : [];
  const rows = root ? [...root.querySelectorAll('.sm-table-layout__row.sm-table-row-layout')].slice(0, ${limit}).map((row) => {
    const cells = [...row.querySelectorAll('.sm-table-layout__cell')].map((el) => clean(el.innerText));
    const raw = Object.fromEntries(cells.map((value, index) => [headers[index] || 'col_' + (index + 1), value]));
    return {
      keyword: clean(row.querySelector('.sm-cell-phrase__link')?.textContent || cells[1] || cells[0]),
      intent: raw['意图'] || null,
      volume: raw['搜索量'] || null,
      kd: raw['KD'] || null,
      cpc_usd: raw['CPC (USD)'] || null,
      sf: raw['SF'] || null,
      updated: raw['已更新'] || null,
      _raw: raw,
    };
  }).filter((row) => row.keyword && row.keyword !== '取消全选' && row.keyword !== '复制') : [];
  const label = (testId) => {
    const wrapper = document.querySelector('[data-testid="' + testId + '"]');
    const trigger = wrapper?.querySelector('button[role="combobox"]');
    return clean(trigger?.getAttribute('aria-label') || wrapper?.innerText || '');
  };
  return {
    href: location.href,
    title: document.title,
    heading: clean(document.querySelector('h1')?.innerText),
    filters: { volume: label('volume'), kd: label('kd'), cpc: label('cpc') },
    headers,
    rowCount: rows.length,
    rows,
  };
})()`;

const source = `
const task = await useOrCreateTaskSpace(${JSON.stringify(taskName)})
await openOrReuseTab(${JSON.stringify(target.toString())}, { wait: true, timeout: 30 })
let state = null
for (let attempt = 0; attempt < 25; attempt++) {
  state = await js(${JSON.stringify(pageScript)})
  if (state.title.includes('Keyword Magic Tool') && state.rowCount > 0) break
  await wait(1)
}
cliLog(JSON.stringify({ taskId: task.id, state }))
`;

const payload = lastJson(runEgo(source));
activeTaskId = payload.taskId;
const state = payload.state || {};

function metric(value) {
  let text = String(value || '').replace(/[$,%\s,]/g, '');
  let multiplier = 1;
  if (/k$/i.test(text)) { multiplier = 1e3; text = text.slice(0, -1); }
  else if (/m$/i.test(text)) { multiplier = 1e6; text = text.slice(0, -1); }
  else if (/b$/i.test(text)) { multiplier = 1e9; text = text.slice(0, -1); }
  const valueNumber = Number.parseFloat(text);
  return Number.isFinite(valueNumber) ? valueNumber * multiplier : null;
}

function range(label) {
  return String(label || '').replaceAll(',', '').match(/\d+(?:\.\d+)?/g)?.map(Number) || [];
}

let current;
try { current = new URL(state.href); } catch { fail('Semrush returned an invalid page URL', { state }); }
if (!state.title?.includes('Keyword Magic Tool')) fail('Semrush did not render Keyword Magic Tool', { state });
if (current.searchParams.get('q') !== query || current.searchParams.get('db') !== db) fail('Semrush rendered a stale query', { state });
if (fid && current.searchParams.get('fid') !== fid) fail('Semrush rendered the wrong fid', { state });
if (!state.rowCount) fail('Semrush rendered no keyword rows', { state });

const expectedKd = [0, Math.ceil(Number(maxKd)) - 1];
const expectedCpc = [Number((Number(minCpc) + 0.01).toFixed(2)), 1000000];
const actualKd = range(state.filters?.kd);
const actualCpc = range(state.filters?.cpc);
if (actualKd[0] !== expectedKd[0] || actualKd[1] !== expectedKd[1]) fail('KD UI filter mismatch', { expectedKd, actualKd, state });
if (actualCpc[0] !== expectedCpc[0] || actualCpc[1] !== expectedCpc[1]) fail('CPC UI filter mismatch', { expectedCpc, actualCpc, state });
if (minVolume) {
  const expectedVolume = Math.floor(Number(minVolume)) + 1;
  const actualVolume = range(state.filters?.volume);
  if (actualVolume[0] !== expectedVolume) fail('Volume UI filter mismatch', { expectedVolume, actualVolume, state });
}

const violations = state.rows.filter((row) =>
  (minVolume && !(metric(row.volume) > Number(minVolume))) ||
  !(metric(row.kd) < Number(maxKd)) ||
  !(metric(row.cpc_usd) > Number(minCpc))
);
if (violations.length) fail('Rendered rows violate requested thresholds', { violations: violations.slice(0, 3) });

const result = {
  success: true,
  source: 'ego-browser-live-dom',
  url: redact(state.href),
  query,
  db,
  fid: fid || null,
  filters: { minVolume: minVolume ? Number(minVolume) : null, maxKd: Number(maxKd), minCpc: Number(minCpc) },
  row_count: state.rowCount,
  rows: state.rows,
};

const cleanup = cleanupTask();
if (cleanup && cleanup.status !== 0) result.cleanup_error = (cleanup.stderr || cleanup.stdout).trim();

process.stdout.write(`${JSON.stringify(result)}\n`);
