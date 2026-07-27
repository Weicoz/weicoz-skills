#!/usr/bin/env node
import { execFileSync } from 'node:child_process';

function option(name, fallback = '') {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] ?? fallback : fallback;
}

function run(args) {
  return execFileSync('bb-browser', args, { encoding: 'utf8' }).trim();
}

function fail(message) {
  console.error(JSON.stringify({ success: false, error: message }));
  process.exit(1);
}

const query = option('query');
const db = option('db');
const fid = option('fid');
const tab = option('tab');
const seedTab = option('seedTab');
const maxKd = option('maxKd');
const minCpc = option('minCpc');
const minVolume = option('minVolume');
const limit = option('limit', '20');

if (!query || !db || !tab || !seedTab || !maxKd || !minCpc) {
  fail('Usage: --query --db --tab --seedTab --maxKd --minCpc are required');
}

let seedUrl;
try {
  seedUrl = new URL(run(['get', 'url', '--tab', seedTab]));
} catch {
  fail(`Cannot read the verified seed tab: ${seedTab}`);
}
const filter = seedUrl.searchParams.get('filter');
if (!filter) fail('The seed tab has no Semrush filter state');

const proxyHost = process.env.WEICOZ_SEMRUSH_PROXY_HOST;
if (!proxyHost) fail('WEICOZ_SEMRUSH_PROXY_HOST is required');
const target = new URL(`https://${proxyHost}/analytics/keywordmagic/`);
target.searchParams.set('q', query);
target.searchParams.set('db', db);
if (fid) target.searchParams.set('fid', fid);
target.searchParams.set('filter', filter);
const gmitm = seedUrl.searchParams.get('__gmitm');
if (gmitm) target.searchParams.set('__gmitm', gmitm);

const stateScript = "JSON.stringify({href:location.href,title:document.title,heading:document.querySelector('h1')?.innerText||'',kd:document.querySelector('[data-testid=kd] button[role=combobox]')?.getAttribute('aria-label')||'',cpc:document.querySelector('[data-testid=cpc] button[role=combobox]')?.getAttribute('aria-label')||'',firstKeyword:document.querySelector('.sm-kmt-table__table .sm-table-layout__row.sm-table-row-layout .sm-cell-phrase__link')?.textContent?.trim()||'',rowCount:document.querySelectorAll('.sm-kmt-table__table .sm-table-layout__row.sm-table-row-layout').length})";
let previous = {};
try { previous = JSON.parse(run(['eval', stateScript, '--tab', tab])); } catch {}
let previousQuery = '';
try { previousQuery = new URL(previous.href).searchParams.get('q') || ''; } catch {}
run(['eval', `location.href=${JSON.stringify(target.toString())}; undefined`, '--tab', tab]);
const expectedKd = `KD: 0\u2013${Math.ceil(Number(maxKd)) - 1}%`;
const expectedCpc = `CPC: ${(Number(minCpc) + 0.01).toFixed(2)}\u20131,000,000 (USD)`;
let ready = false;
for (let attempt = 0; attempt < 20; attempt++) {
  run(['wait', '500', '--tab', tab]);
  const state = run(['eval', stateScript, '--tab', tab]);
  try {
    const parsed = JSON.parse(state);
    if (
      parsed.title.includes('Keyword Magic Tool') &&
      new URL(parsed.href).searchParams.get('q') === query &&
      parsed.heading.includes(query) &&
      parsed.kd === expectedKd &&
      parsed.cpc === expectedCpc &&
      parsed.rowCount > 0 &&
      parsed.firstKeyword &&
      (previousQuery === query || parsed.firstKeyword !== previous.firstKeyword)
    ) {
      ready = true;
      break;
    }
  } catch {}
}
if (!ready) fail(`Semrush did not render the requested UI filters: ${expectedKd}; ${expectedCpc}`);
run(['wait', '2000', '--tab', tab]);
const settled = JSON.parse(run(['eval', stateScript, '--tab', tab]));
if (settled.rowCount === 0 || !settled.firstKeyword || !settled.heading.includes(query)) {
  fail(`Semrush table did not settle for query: ${query}`);
}

const args = ['site', 'sem3ue/keywordmagic', query, db];
if (fid) args.push(fid);
if (minVolume) args.push('--minVolume', minVolume);
args.push('--maxKd', maxKd, '--minCpc', minCpc, '--limit', limit, '--json', '--tab', tab);
process.stdout.write(`${run(args)}\n`);
