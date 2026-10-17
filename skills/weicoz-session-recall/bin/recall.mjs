#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { VERSION } from './lib/version.mjs';

export { VERSION };

const args = process.argv.slice(2);
if (args.includes('--version') || args.includes('-v')) {
  console.log(`weicoz-session-recall v${VERSION} (powered by agent-recall)`);
  process.exit(0);
}

function resolveRecallBin() {
  const home = homedir();
  const candidates = [
    process.env.AGENT_RECALL_BIN,
    process.env.RECALL_BIN,
    join(home, '.local', 'bin', 'recall'),
    join(home, 'File', 'git', 'agent-recall', 'bin', 'cli.mjs'),
  ].filter(Boolean);

  for (const c of candidates) {
    if (existsSync(c)) {
      return { isNode: c.endsWith('.mjs') || c.endsWith('.js'), path: c };
    }
  }
  return null;
}

const runner = resolveRecallBin();

if (!runner) {
  const res = spawnSync('npx', ['-y', 'harness-recall', ...args], { stdio: 'inherit' });
  process.exit(res.status ?? 0);
}

if (runner.isNode) {
  const res = spawnSync(process.execPath, [runner.path, ...args], { stdio: 'inherit' });
  process.exit(res.status ?? 0);
} else {
  const res = spawnSync(runner.path, args, { stdio: 'inherit' });
  process.exit(res.status ?? 0);
}
