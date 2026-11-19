#!/usr/bin/env node
// weicoz-ask：在 weicoz-skills 仓库的全部 skill 里按关键词找该用哪个。
// 数据源：仓库 README.md 的“Skill 清单”分组 + 各 skills/<name>/SKILL.md 的 frontmatter。
import { readFileSync, readdirSync, existsSync, realpathSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export function parseFrontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  const out = {};
  if (!m) return out;
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (kv) out[kv[1]] = kv[2].replace(/^["']|["']$/g, '');
  }
  return out;
}

// README 里 “#### 分组” 下的表格行 → { skill: 分组 }
export function parseGroups(readme) {
  const groups = {};
  let cur = null;
  for (const line of readme.split('\n')) {
    if (/^## /.test(line)) cur = null;
    const h = line.match(/^#### (.+)/);
    if (h) { cur = h[1].trim(); continue; }
    const row = cur && line.match(/^\| \[`([^`]+)`\]/);
    if (row) groups[row[1]] = cur;
  }
  return groups;
}

export function loadSkills(repo) {
  const dir = join(repo, 'skills');
  const readmePath = join(repo, 'README.md');
  const groups = existsSync(readmePath) ? parseGroups(readFileSync(readmePath, 'utf8')) : {};
  return readdirSync(dir).filter(n => existsSync(join(dir, n, 'SKILL.md'))).map(n => {
    const fm = parseFrontmatter(readFileSync(join(dir, n, 'SKILL.md'), 'utf8'));
    return { name: fm.name || n, dir: n, version: fm.version || '-', description: fm.description || '', group: groups[n] || '未分组' };
  });
}

// 每个关键词在名称、分组、描述里命中各计分；全部关键词都没命中的不返回
export function rank(skills, words) {
  const ws = words.map(w => w.toLowerCase()).filter(Boolean);
  return skills.map(s => {
    let score = 0, hit = 0;
    for (const w of ws) {
      let k = 0;
      if (s.name.toLowerCase().includes(w)) k += 3;
      if (s.group.toLowerCase().includes(w)) k += 2;
      if (s.description.toLowerCase().includes(w)) k += 1;
      if (k) hit++;
      score += k;
    }
    return { ...s, score: score + hit * 2 };
  }).filter(s => s.score > 0).sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
}

function main(argv) {
  const here = dirname(realpathSync(fileURLToPath(import.meta.url)));
  const repo = process.env.WEICOZ_SKILLS_REPO || join(here, '..', '..', '..');
  if (!existsSync(join(repo, 'skills'))) {
    console.error('错误：找不到 weicoz-skills 仓库的 skills/ 目录。\n请设置环境变量：export WEICOZ_SKILLS_REPO="<仓库根目录>"');
    process.exit(2);
  }
  const skills = loadSkills(repo);
  if (argv[0] === '--check') {
    const miss = skills.filter(s => s.group === '未分组').map(s => s.name);
    console.log(miss.length ? `README 未分组：${miss.join(', ')}` : `CHECK OK — ${skills.length} 个 skill 均已分组`);
    process.exit(miss.length ? 1 : 0);
  }
  if (!argv.length) {
    const by = {};
    for (const s of skills) (by[s.group] ||= []).push(s.name);
    for (const [g, ns] of Object.entries(by)) console.log(`## ${g}（${ns.length}）\n${ns.sort().join('  ')}\n`);
    console.log(`共 ${skills.length} 个。用法：ask.mjs <关键词...> 查找；ask.mjs --check 查 README 漏分组`);
    return;
  }
  const top = rank(skills, argv).slice(0, 8);
  if (!top.length) { console.log('无匹配：换个说法，或用 skill_tiers.py find 查第三方 skill'); return; }
  for (const s of top) console.log(`${s.name}  [${s.group}] v${s.version}\n  ${s.description.slice(0, 160)}\n  skills/${s.dir}/SKILL.md\n`);
}

if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) main(process.argv.slice(2));
