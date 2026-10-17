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

function resolveDigestRunner() {
  const home = homedir();
  // 1. Check direct digest script in agent-recall
  const digestScript = join(home, 'File', 'git', 'agent-recall', 'bin', 'digest.mjs');
  if (existsSync(digestScript)) {
    return { isNode: true, path: digestScript, prepend: [] };
  }

  // 2. Check recall CLI
  const candidates = [
    process.env.AGENT_RECALL_BIN,
    process.env.RECALL_BIN,
    join(home, '.local', 'bin', 'recall'),
    join(home, 'File', 'git', 'agent-recall', 'bin', 'cli.mjs'),
  ].filter(Boolean);

  for (const c of candidates) {
    if (existsSync(c)) {
      const isNode = c.endsWith('.mjs') || c.endsWith('.js');
      return { isNode, path: c, prepend: ['digest'] };
    }
  }
  return null;
}

const runner = resolveDigestRunner();

if (!runner) {
  const res = spawnSync('npx', ['-y', 'harness-recall', 'digest', ...args], { stdio: 'inherit' });
  process.exit(res.status ?? 0);
}

const finalArgs = [...runner.prepend, ...args];
if (runner.isNode) {
  const res = spawnSync(process.execPath, [runner.path, ...finalArgs], { stdio: 'inherit' });
  process.exit(res.status ?? 0);
} else {
  const res = spawnSync(runner.path, finalArgs, { stdio: 'inherit' });
  process.exit(res.status ?? 0);
}
