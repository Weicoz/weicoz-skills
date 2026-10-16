#!/usr/bin/env python3
"""生成仅含配置和插件源码的跨平台迁移包；不连接或修改目标机器。"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tomllib

CONFIG_FILES = (
    '.codex/config.toml', '.codex/auth.json', '.codex/hooks.json',
    '.codex/keybindings.json', '.codex/herdr-agent-state.sh',
    '.dsh/cordis.patch.yml', '.dsh/.credentials.yaml',
    '.hindsight/coding-agent.json', '.config/harness-notify/config.json',
)
CONFIG_DIRS = (
    '.codex/hooks', '.codex/rules', '.codex/prompts', '.codex/agents',
    '.codex/model-catalog-overrides', '.codex/plugins/cache',
    '.dsh/.agent-presets', '.dsh/bin',
    '.hindsight/coding-agents', '.skills-manager/hooks', '.quicktui/bin',
)
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                 'sessions', 'memories', 'memories_v2', 'generated_images',
                 'attachments', 'backups', 'migration-backups', 'automations'}


def excluded(name):
    return (name in EXCLUDED_DIRS or name == '.DS_Store' or name.startswith('.env')
            or name.endswith(('.log', '.pyc', '.sqlite', '.sqlite-wal', '.sqlite-shm', '.pem', '.key'))
            or re.search(r'(?i)(\.bak(?:-|\.|$)|-backup|\.backup)', name))


def safe_relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('目标路径必须位于用户目录内')
    if any(part in EXCLUDED_DIRS | {'.ssh'} for part in p.parts):
        raise ValueError('路径包含个人数据或密钥目录')
    return p


def rewrite(data, source, target, replacements):
    # 二进制原样保留；原生依赖由目标端安装，不由本脚本复制。
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    mapping = {str(source): target, **replacements}
    pattern = re.compile('|'.join(re.escape(old) for old in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match.group()], text).encode('utf-8')


def portable_codex(text, platform, source=None, target=None):
    config = tomllib.loads(text)
    unavailable = []
    sections = list(re.finditer(r'(?m)^\[[^\n]+\]\s*$', text))
    edits = []
    if platform != 'darwin':
        notify_match = re.search(r'(?m)^notify\s*=\s*\[.*\]\s*$', text)
        if notify_match:
            notify_str = notify_match.group()
            if 'SkyComputerUseClient' in notify_str and '--previous-notify' in notify_str:
                try:
                    raw_val = notify_str.split('=', 1)[1].strip()
                    arr = json.loads(raw_val)
                    if '--previous-notify' in arr:
                        idx = arr.index('--previous-notify')
                        inner = json.loads(arr[idx + 1])
                        inner = ['node' if ('node' in p and '.hermes' in p) else p for p in inner]
                        if source and target:
                            s_variants = {str(source), str(Path(source).resolve())}
                            for s in list(s_variants):
                                if s.startswith('/private/'):
                                    s_variants.add(s[len('/private'):])
                            for s in sorted(s_variants, key=len, reverse=True):
                                inner = [p.replace(s, target) for p in inner]
                        text = text[:notify_match.start()] + 'notify = ' + json.dumps(inner) + text[notify_match.end():]
                except Exception:
                    pass
        for i, section in enumerate(sections):
            try:
                table = tomllib.loads(section.group()).get('mcp_servers', {})
            except tomllib.TOMLDecodeError:
                continue
            if len(table) != 1:
                continue
            name = next(iter(table))
            if any(table[name]):  # 子表（如 .env）不是服务入口。
                continue
            command = config.get('mcp_servers', {}).get(name, {}).get('command', '')
            if '.app/' not in command:
                continue
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            block = text[section.end():end]
            block = re.sub(r'(?m)^enabled\s*=.*\n?', '', block)
            edits.append((section.end(), end, '\nenabled = false' + block))
            unavailable.append({'mcp': name, 'reason': 'source desktop application requires macOS'})
        for start, end, block in reversed(edits):
            text = text[:start] + block + text[end:]
    return text, unavailable


def build(source, target, platform, output, shell=False, config=True, extras=(), include_auth=False,
          exclude_dsh_official_deepseek=False):
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError('输出目录已存在；选择新的私有目录')
    output.mkdir(parents=True, mode=0o700)
    stage = output / 'payload'
    stage.mkdir(mode=0o700)
    replacements = {}
    local_plugins = {}
    if config:
        for profile in ('web', 'web-safe', 'headless', 'dsh-tui', 'desktop'):
            pkg = source / '.dsh/profiles' / profile / 'package.json'
            if not pkg.exists():
                continue
            for name, value in json.loads(pkg.read_text()).get('dependencies', {}).items():
                if value.startswith(('link:', 'file:')):
                    candidate = Path(value.split(':', 1)[1])
                    src = (candidate if candidate.is_absolute() else pkg.parent / candidate).resolve()
                    if not src.is_dir():
                        raise ValueError(f'本地插件不存在: {name}')
                    rel = '.local/share/harness-config-sync/plugins/' + name.replace('/', '__')
                    replacements[str(src)] = target + '/' + rel
                    local_plugins[rel] = src

    def copy(src, rel, active=()):
        if not src.exists() or excluded(src.name):
            return
        rel = str(safe_relative(rel))
        real = src.resolve()
        if real in active:
            raise ValueError('配置软链形成循环')
        if src.is_dir():
            for child in sorted(src.iterdir()):
                copy(child, rel + '/' + child.name, active + (real,))
        elif src.is_file():
            data = src.read_bytes()
            header_pattern = rb'(?m)^-----' + rb'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{32,}'
            if re.search(header_pattern, data):
                raise ValueError(f'拒绝私钥正文: {rel}')
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(rewrite(data, source, target, replacements))
            dst.chmod(src.stat().st_mode & 0o777)

    links = {}
    unavailable = []
    if config:
        for rel in CONFIG_FILES + CONFIG_DIRS:
            if rel in {'.codex/auth.json', '.dsh/.credentials.yaml'} and not include_auth:
                continue
            copy(source / rel, rel)
        for rel, src in local_plugins.items():
            copy(src, rel)
        # 每个 Harness 入口指向同一技能源；插件缓存软链在包内物化。
        for root in ('.agents/skills', '.codex/skills', '.dsh/skills'):
            folder = source / root
            if not folder.is_dir():
                continue
            for item in sorted(folder.iterdir()):
                if item.name.startswith('.') and item.name != '.system':
                    continue
                if not (item / 'SKILL.md').is_file() and item.name != '.system':
                    continue
                canonical = '.agents/skills/' + item.name
                if not (stage / canonical).exists():
                    copy(item, canonical)
                if root != '.agents/skills':
                    links[root + '/' + item.name] = canonical
        for profile in ('web', 'web-safe', 'headless', 'dsh-tui', 'desktop'):
            for name in ('package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'cordis.yml', 'cordis.patch.yml'):
                rel = f'.dsh/profiles/{profile}/{name}'
                copy(source / rel, rel)
        # 全局 AGENTS 正文只有一个源；迁移后保留入口关系。
        for root in ('.agents', '.codex', '.dsh'):
            src = source / root / 'AGENTS.md'
            if src.exists():
                if not (stage / '.agents/AGENTS.md').exists():
                    copy(src, '.agents/AGENTS.md')
                if root != '.agents':
                    links[root + '/AGENTS.md'] = '.agents/AGENTS.md'
        cp = stage / '.codex/config.toml'
        if cp.exists():
            text, unavailable = portable_codex(cp.read_text(), platform, source=source, target=target)
            cp.write_text(text)
            tomllib.loads(text)
        if exclude_dsh_official_deepseek:
            cred = stage / '.dsh/.credentials.yaml'
            if cred.exists():
                lines = [l for l in cred.read_text().splitlines() if not re.match(r'^\s*DEEPSEEK_API_KEY\s*:', l)]
                cred.write_text('\n'.join(lines) + '\n')
            for patch_file in (stage / '.dsh').rglob('*.patch.yml'):
                t = patch_file.read_text()
                if 'deepseek-official' in t:
                    t = re.sub(r'(?m)^\s*provider:\s*deepseek-official\s*$', '    provider: newapi', t)
                    patch_file.write_text(t)
        web_pkg = stage / '.dsh/profiles/web/package.json'
        if web_pkg.exists() and platform == 'linux':
            try:
                pkg_data = json.loads(web_pkg.read_text())
                vendor_names = [
                    '@smalltailqwq/dsh-client-ui-skin-maid-atelier',
                    'dsh-at-file',
                    'dsh-deep-whale',
                    'dsh-models-dev-reasoning',
                    'dsh-skin-manager',
                    'dsh-usage-stats',
                    'dsh-web'
                ]
                deps = pkg_data.get('dependencies', {})
                for vname in vendor_names:
                    if vname in deps and not deps[vname].startswith(('link:', 'file:')):
                        deps[vname] = f'link:{target}/.dsh/profiles/web/vendor/{vname}'
                web_pkg.write_text(json.dumps(pkg_data, ensure_ascii=False, indent=2) + '\n')
            except Exception:
                pass
    for spec in extras:
        src, rel = spec.split('=', 1)
        copy(Path(src).expanduser(), rel)
    if shell:
        allowed = {'PATH', 'ZSH', 'ZSH_CUSTOM', 'ZSH_THEME', 'EDITOR', 'VISUAL', 'LANG',
                   'MANPATH', 'HISTFILE', 'HISTSIZE', 'SAVEHIST', 'BUN_INSTALL', 'PNPM_HOME', 'HEADROOM_SH_DIR'}
        secret = re.compile(r'(?i)(API_?KEY|ACCESS_TOKEN|AUTH_TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_KEY|SSH_KEY|AUTHORIZATION|claude-env\.sh)')
        for name in ('.zshenv', '.zprofile', '.zshrc', '.p10k.zsh'):
            src = source / name
            if not src.exists():
                continue
            result = []
            for line in src.read_text().splitlines():
                assignment = re.match(r'\s*export\s+(\w+)\s*=', line)
                if secret.search(line) or (assignment and assignment[1] not in allowed and not assignment[1].startswith('LC_')):
                    continue
                if '/opt/homebrew/' in line or '/Applications/' in line or '.x-cmd.root/X' in line:
                    continue
                result.append(line.replace(str(source), target))
            (stage / name).write_text('\n'.join(result) + '\n')
        for rel in ('.oh-my-zsh', '.autojump', '.zsh/completions', '.bun/_bun', 'File/sh'):
            copy(source / rel, rel)
        ze = stage / '.zshenv'
        data = ze.read_text() if ze.exists() else ''
        if '.local/bin' not in data:
            ze.write_text(data + '\nexport PATH="$HOME/.local/bin:$PATH"\n')
    manifest = {}
    for file in sorted(stage.rglob('*')):
        if file.is_file():
            rel = str(file.relative_to(stage))
            safe_relative(rel)
            manifest[rel] = {'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'mode': file.stat().st_mode & 0o777}
    metadata = {'files': manifest, 'links': links, 'platform': platform, 'target_home': target,
                'unavailable': unavailable, 'includes_personal_history': False,
                'includes_login_files': bool(config and include_auth)}
    (output / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    (output / 'manifest.json').chmod(0o600)
    with tarfile.open(output / 'payload.tgz', 'w:gz') as archive:
        archive.add(stage, arcname='payload')
    (output / 'payload.tgz').chmod(0o600)
    print(json.dumps({'files': len(manifest), 'links': len(links), 'unavailable': unavailable}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-home', type=Path, default=Path.home())
    p.add_argument('--target-home', required=True)
    p.add_argument('--platform', choices=('linux', 'darwin', 'win32'), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--shell', action='store_true')
    p.add_argument('--shell-only', action='store_true')
    p.add_argument('--include-auth', action='store_true', help='用户已要求同步登录及模型凭据时使用')
    p.add_argument('--exclude-dsh-official-deepseek', action='store_true',
                   help='用户要求不同步 DSH 官方 DeepSeek 模型凭据与配置时使用')
    p.add_argument('--extra', action='append', default=[], metavar='SOURCE=HOME_RELATIVE_DEST')
    a = p.parse_args()
    try:
        build(a.source_home, a.target_home.replace('\\', '/').rstrip('/'), a.platform,
              a.output, a.shell or a.shell_only, not a.shell_only, a.extra, a.include_auth,
              a.exclude_dsh_official_deepseek)
    except (ValueError, OSError) as error:
        p.exit(1, f'错误：{error}\n')


if __name__ == '__main__':
    main()

