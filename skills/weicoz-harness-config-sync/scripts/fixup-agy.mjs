#!/usr/bin/env node
// 目标端只读检查；修正项通过设备覆盖层重新打包，保持同步基线一致。
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const home = os.homedir();
const reportPath = process.argv[2] ? path.resolve(process.argv[2]) : null;
const result = { mode: 'read-only', recommendations_only: true, platform: process.platform, home, mcp_disabled: [], hooks_disabled: [],
  trusted_workspaces_dropped: [], links_broken: [] };

const which = command => {
  if (!command) return false;
  if (path.isAbsolute(command)) return fs.existsSync(command);
  const found = spawnSync(process.platform === 'win32' ? 'where' : 'which', [command], { encoding: 'utf8' });
  return found.status === 0;
};

// Hook 命令里既有可执行文件，也有脚本参数；两者都要在目标存在。
const commandParts = command => {
  const parts = [];
  const tokens = command.match(/"[^"]+"|'[^']+'|\S+/g) ?? [];
  for (const token of tokens) {
    const value = token.replace(/^["']|["']$/g, '');
    if (value.startsWith('-')) continue;
    // 相对脚本名依赖运行时工作目录，无法在安装阶段判定；只核对绝对路径。
    if (path.isAbsolute(value)) parts.push(value);
  }
  return parts;
};

const mcpPath = path.join(home, '.gemini', 'config', 'mcp_config.json');
if (fs.existsSync(mcpPath)) {
  const config = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
  for (const [name, server] of Object.entries(config.mcpServers ?? {})) {
    if (server.disabled) continue;
    const args = (server.args ?? []).filter(a => typeof a === 'string').join(' ');
    const missing = [server.command ?? '', ...commandParts(args)].filter(part => part && !which(part));
    if (!missing.length) continue;
    server.disabled = true;
    result.mcp_disabled.push({ name, missing });
  }
}

const hooksPath = path.join(home, '.gemini', 'config', 'hooks.json');
if (fs.existsSync(hooksPath)) {
  const hooks = JSON.parse(fs.readFileSync(hooksPath, 'utf8'));
  for (const [group, events] of Object.entries(hooks)) {
    const entry = events && typeof events === 'object' ? events : {};
    const missing = new Set();
    for (const list of Object.values(entry)) {
      if (!Array.isArray(list)) continue;
      for (const hook of list) {
        for (const part of commandParts(hook.command ?? '')) {
          if (!which(part)) missing.add(part);
        }
      }
    }
    if (!missing.size) continue;
    entry.enabled = false;
    result.hooks_disabled.push({ group, missing: [...missing] });
  }
}

const settingsPath = path.join(home, '.gemini', 'antigravity-cli', 'settings.json');
if (fs.existsSync(settingsPath)) {
  const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
  if (Array.isArray(settings.trustedWorkspaces)) {
    for (const dir of settings.trustedWorkspaces) {
      if (!fs.existsSync(dir)) result.trusted_workspaces_dropped.push(dir);
    }
  }
}

const agentsLink = path.join(home, '.gemini', 'AGENTS.md');
if (!fs.existsSync(agentsLink)) result.links_broken.push('.gemini/AGENTS.md');
const skillsDir = path.join(home, '.gemini', 'config', 'skills');
if (fs.existsSync(skillsDir)) {
  for (const name of fs.readdirSync(skillsDir)) {
    if (!fs.existsSync(path.join(skillsDir, name))) result.links_broken.push('.gemini/config/skills/' + name);
  }
}

if (reportPath) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true, mode: 0o700 });
  fs.writeFileSync(reportPath, JSON.stringify(result, null, 2) + '\n', { mode: 0o600 });
}
console.log(JSON.stringify(result));
