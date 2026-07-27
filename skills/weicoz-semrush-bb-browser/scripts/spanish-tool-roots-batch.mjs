#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mappings = [
  ['Translator', 'traductor'], ['Generator', 'generador'], ['Example', 'ejemplo'], ['Convert', 'convertidor'], ['Online', 'en linea'],
  ['Downloader', 'descargador'], ['Maker', 'creador'], ['Creator', 'creador'], ['Editor', 'editor'], ['Processor', 'procesador'],
  ['Designer', 'diseñador'], ['Compiler', 'compilador'], ['Analyzer', 'analizador'], ['Evaluator', 'evaluador'], ['Sender', 'remitente'],
  ['Receiver', 'receptor'], ['Interpreter', 'intérprete'], ['Uploader', 'cargador'], ['Calculator', 'calculadora'], ['Sample', 'muestra'],
  ['Template', 'plantilla'], ['Format', 'formato'], ['Builder', 'constructor'], ['Scheme', 'esquema'], ['Pattern', 'patrón'],
  ['Checker', 'comprobador'], ['Detector', 'detector'], ['Scraper', 'raspador'], ['Manager', 'gestor'], ['Explorer', 'explorador'],
  ['Dashboard', 'panel de control'], ['Planner', 'planificador'], ['Tracker', 'rastreador'], ['Recorder', 'grabador'], ['Optimizer', 'optimizador'],
  ['Scheduler', 'programador'], ['Converter', 'convertidor'], ['Viewer', 'visor'], ['Extractor', 'extractor'], ['Monitor', 'monitor'],
  ['Notifier', 'notificador'], ['Verifier', 'verificador'], ['Simulator', 'simulador'], ['Assistant', 'asistente'], ['Constructor', 'constructor'],
  ['Comparator', 'comparador'], ['Navigator', 'navegador'], ['Syncer', 'sincronizador'], ['Connector', 'conector'], ['Cataloger', 'catalogador'], ['Responder', 'respondedor']
];

function option(name, fallback = '') {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] ?? fallback : fallback;
}
function run(query, db, options) {
  const args = [
    new URL('./keywordmagic-filter-runner.mjs', import.meta.url).pathname,
    '--query', query, '--db', db, '--fid', options.fid,
    '--tab', options.tab, '--seedTab', options.seedTab,
    '--maxKd', options.maxKd, '--minCpc', options.minCpc, '--limit', options.limit
  ];
  return JSON.parse(execFileSync('node', args, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }));
}

const options = {
  fid: option('fid', process.env.WEICOZ_SEMRUSH_FID || ''), tab: option('tab'), seedTab: option('seedTab'),
  maxKd: option('maxKd', '40'), minCpc: option('minCpc', '0.1'), limit: option('limit', '20')
};
if (!options.tab || !options.seedTab) throw new Error('Usage: --tab <temporary-tab> --seedTab <verified-filter-tab>');

const unique = [...new Map(mappings.map(([, spanish]) => [spanish, spanish])).values()];
const resumePath = option('resume');
const results = resumePath ? JSON.parse(readFileSync(resumePath, 'utf8')).results : [];
const completed = new Set(results.filter((item) => item.success).map((item) => `${item.db}:${item.query}`));
const outputDir = resolve(process.cwd(), 'outputs');
mkdirSync(outputDir, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const jsonPath = resolve(outputDir, `${stamp}-semrush-es-mx-spanish-tool-roots.json`);
const checkpoint = () => writeFileSync(jsonPath, JSON.stringify({ mappings, filters: options, results }, null, 2));
for (const db of ['es', 'mx']) {
  for (const query of unique) {
    if (completed.has(`${db}:${query}`)) continue;
    try {
      const response = run(query, db, options);
      results.push({ db, query, success: true, data: response.data });
      console.error(`[${db}] ${query}: ${response.data.row_count} rows`);
    } catch (error) {
      results.push({ db, query, success: false, error: String(error.message || error) });
      console.error(`[${db}] ${query}: FAILED`);
    }
    checkpoint();
  }
}

const mdPath = resolve(outputDir, `${stamp}-semrush-es-mx-spanish-tool-roots.md`);

const lines = [
  '# 西班牙与墨西哥西语工具词根 Keyword Magic 数据', '',
  `筛选：KD < ${options.maxKd}；CPC > ${options.minCpc} USD。`, '',
  '## 翻译映射', '', '| 英文词根 | 西语查询 |', '| --- | --- |',
  ...mappings.map(([english, spanish]) => `| ${english} | ${spanish} |`), '',
  '## 查询摘要', '', '| 市场 | 查询词 | 返回行 | 前三条关键词 |', '| --- | --- | ---: | --- |'
];
for (const item of results) {
  if (!item.success) lines.push(`| ${item.db} | ${item.query} | 失败 | ${item.error.replaceAll('|', '/')} |`);
  else lines.push(`| ${item.db} | ${item.query} | ${item.data.row_count} | ${item.data.rows.slice(0, 3).map((row) => `${row.keyword} (${row.volume}, KD ${row.kd}, $${row.cpc_usd})`).join('<br>')} |`);
}
writeFileSync(mdPath, `${lines.join('\n')}\n`);
console.log(JSON.stringify({ jsonPath, mdPath, successful: results.filter((item) => item.success).length, failed: results.filter((item) => !item.success).length }));
