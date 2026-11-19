import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseFrontmatter, parseGroups, rank } from '../scripts/ask.mjs';

test('frontmatter 去引号', () => {
  const fm = parseFrontmatter('---\nname: a\ndescription: "说明 x"\nversion: 1.0.0\n---\n正文');
  assert.deepEqual(fm, { name: 'a', description: '说明 x', version: '1.0.0' });
});

test('README 分组只取 #### 下的表格行，遇 ## 停止', () => {
  const g = parseGroups('## Skill 清单\n#### 小游戏\n| [`weicoz-game-flow`](skills/weicoz-game-flow/) | 1 | x |\n## 其他节\n| [`ext`](x) | 1 | y |');
  assert.deepEqual(g, { 'weicoz-game-flow': '小游戏' });
});

test('名称命中排在描述命中前，零命中不返回', () => {
  const skills = [
    { name: 'weicoz-a', group: '其他', description: '小游戏 相关' },
    { name: 'weicoz-game-flow', group: '小游戏', description: '流程' },
    { name: 'weicoz-z', group: '其他', description: '无关' },
  ];
  const r = rank(skills, ['game']);
  assert.deepEqual(r.map(s => s.name), ['weicoz-game-flow']);
  assert.deepEqual(rank(skills, ['小游戏']).map(s => s.name), ['weicoz-game-flow', 'weicoz-a']);
});
