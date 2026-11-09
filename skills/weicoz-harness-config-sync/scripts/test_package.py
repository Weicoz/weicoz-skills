import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_package', Path(__file__).with_name('package.py'))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def install(output, target, replace=()):
    command = ['node', str(Path(__file__).with_name('install.mjs')), str(output)]
    for rel in replace:
        command += ['--replace', rel]
    env = {**os.environ, 'HOME': str(target)}
    preview = subprocess.run(command, env=env, capture_output=True)
    if preview.returncode:
        return preview
    token = json.loads(preview.stdout)['plan_token']
    return subprocess.run(command + ['--apply', '--plan', token], env=env, capture_output=True)


class PackageSafety(unittest.TestCase):
    def test_windows_home_rewrite_does_not_rewrite_its_own_output(self):
        source = Path('/Users/developer')
        target = 'C:/Users/developer'
        actual = package.rewrite(b'link:/Users/developer/plugin', source, target,
                                 {'/Users/developer/plugin': target + '/portable/plugin'})
        self.assertEqual(actual, b'link:C:/Users/developer/portable/plugin')

    def test_shell_keeps_target_credentials_but_excludes_source_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'source', root / 'target'
            source.mkdir(); target.mkdir()
            (source / '.zshrc').write_text('export API_KEY="source-key-do-not-copy"\nexport ZSH_THEME="ys"\n')
            (target / '.zshrc').write_text('export OPENAI_API_KEY="target-key-retain"\nexport PATH="$HOME/original/bin:$PATH"\n')
            output = root / 'output'
            package.build(source, str(target), os.sys.platform, output, shell=True, config=False)
            result = install(output, target, ['.zshrc'])
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            actual = (target / '.zshrc').read_text()
            self.assertNotIn('source-key-do-not-copy', actual)
            self.assertIn('target-key-retain', actual)
            self.assertIn('original/bin', actual)
            self.assertEqual((target / '.zshrc').stat().st_mode & 0o777, 0o600)

    def test_config_only_install_preserves_target_sessions_and_shared_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'source', root / 'target'
            (source / '.codex').mkdir(parents=True)
            (source / '.agents/skills/demo').mkdir(parents=True)
            (source / '.agents/skills/demo/SKILL.md').write_text('portable source')
            (source / '.codex/skills').mkdir()
            (source / '.codex/skills/demo').symlink_to(source / '.agents/skills/demo')
            (source / '.codex/auth.json').write_text('{"fixture":true}')
            (source / '.codex/config.toml').write_text(
                'model="fixture"\n[mcp_servers."native-app"]\ncommand="/Applications/Demo.app/bin/tool"\n'
                '[mcp_servers."native-app".env]\nKEEP="yes"\n')
            for name in ('sessions', 'memories', 'generated_images'):
                (source / '.codex' / name).mkdir()
                (source / '.codex' / name / 'personal.txt').write_text('never migrate')
            (source / '.codex/state.sqlite').write_text('never migrate')
            (source / '.agents/AGENTS.md').write_text('shared rules')
            (source / '.codex/AGENTS.md').symlink_to(source / '.agents/AGENTS.md')
            (target / '.codex/sessions').mkdir(parents=True)
            (target / '.codex/sessions/existing.json').write_text('existing work')
            output = root / 'output'
            package.build(source, str(target), 'linux', output, include_auth=True)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertTrue(all('personal.txt' not in p and '.sqlite' not in p for p in manifest['files']))
            self.assertEqual(manifest['unavailable'][0]['mcp'], 'native-app')
            config = package.tomllib.loads((output / 'payload/.codex/config.toml').read_text())
            self.assertFalse(config['mcp_servers']['native-app']['enabled'])
            self.assertEqual(config['mcp_servers']['native-app']['env']['KEEP'], 'yes')
            if os.sys.platform != 'linux':
                output = root / 'native-output'
                package.build(source, str(target), os.sys.platform, output, include_auth=True)
            result = install(output, target)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual((target / '.codex/sessions/existing.json').read_text(), 'existing work')
            self.assertEqual((target / '.codex/skills/demo').resolve(), (target / '.agents/skills/demo').resolve())
            self.assertEqual((target / '.codex/AGENTS.md').resolve(), (target / '.agents/AGENTS.md').resolve())

    def test_exclude_dsh_official_deepseek_and_notify_unwrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'source', root / 'target'
            (source / '.codex').mkdir(parents=True)
            (source / '.dsh/profiles/dsh-tui').mkdir(parents=True)
            (source / '.dsh/profiles/web').mkdir(parents=True)
            (source / '.codex/config.toml').write_text(
                'notify = ["' + str(source) + '/SkyComputerUseClient.app", "turn-ended", "--previous-notify", "[\\"' + str(source).replace('/', '\\\\/') + '\\\\/.hermes\\\\/node\\\\/bin\\\\/node\\", \\"' + str(source).replace('/', '\\\\/') + '\\\\/notify.mjs\\"]"]\n')
            (source / '.dsh/.credentials.yaml').write_text(
                'version: 1\nrefs:\n  DEEPSEEK_API_KEY: sk-secret\n  OTHER_KEY: sk-keep\n')
            (source / '.dsh/profiles/dsh-tui/cordis.patch.yml').write_text(
                '- id: dsh-tui\n  config:\n    provider: deepseek-official\n')
            (source / '.dsh/profiles/web/package.json').write_text(
                '{"dependencies": {"dsh-web": "github:test/dsh-web"}}\n')
            output = root / 'output'
            package.build(source, str(target), 'linux', output, include_auth=True,
                          exclude_dsh_official_deepseek=True)
            codex_cfg = (output / 'payload/.codex/config.toml').read_text()
            self.assertIn('notify = ["node", "' + str(target) + '/notify.mjs"]', codex_cfg)
            dsh_cred = (output / 'payload/.dsh/.credentials.yaml').read_text()
            self.assertNotIn('DEEPSEEK_API_KEY', dsh_cred)
            self.assertIn('OTHER_KEY: sk-keep', dsh_cred)
            tui_patch = (output / 'payload/.dsh/profiles/dsh-tui/cordis.patch.yml').read_text()
            self.assertIn('provider: newapi', tui_patch)
            self.assertNotIn('provider: deepseek-official', tui_patch)
            web_pkg = json.loads((output / 'payload/.dsh/profiles/web/package.json').read_text())
            self.assertEqual(web_pkg['dependencies']['dsh-web'], f'link:{target}/.dsh/profiles/web/vendor/dsh-web')

    def test_antigravity_entries_link_to_single_skill_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'source', root / 'target'
            (source / '.agents/skills/demo').mkdir(parents=True)
            (source / '.agents/skills/demo/SKILL.md').write_text('portable source')
            (source / '.gemini/config/skills').mkdir(parents=True)
            (source / '.gemini/config/skills/demo').symlink_to(source / '.agents/skills/demo')
            (source / '.gemini/config/skills/dangling').symlink_to(source / '.skills-manager/skills/dangling')
            (source / '.gemini/antigravity-cli/skills').mkdir(parents=True)
            (source / '.gemini/antigravity-cli/skills/ego-browser').symlink_to(source / '.local/share/ego/ego-skills')
            (source / '.gemini/config/config.json').write_text(
                json.dumps({'plugins': {'demo': {'enabled': True}},
                            'userSettings': {'remoteControlHostname': 'source-host'}}))
            (source / '.gemini/config/mcp_config.json').write_text(
                json.dumps({'mcpServers': {'tool': {'command': str(source) + '/.local/bin/tool'}}}))
            (source / '.gemini/antigravity-cli/settings.json').write_text(
                json.dumps({'model': 'fixture', 'trustedWorkspaces': [str(source)]}))
            (source / '.agents/AGENTS.md').write_text('shared rules')
            (source / '.gemini/AGENTS.md').write_text('shared rules')
            output = root / 'output'
            package.build(source, str(target), 'darwin', output)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['links']['.gemini/config/skills/demo'], '.agents/skills/demo')
            self.assertEqual(manifest['links']['.gemini/antigravity-cli/skills/ego-browser'],
                             '.local/share/ego/ego-skills')
            self.assertEqual(manifest['links']['.gemini/AGENTS.md'], '.agents/AGENTS.md')
            self.assertNotIn('.gemini/config/skills/dangling', manifest['links'])
            self.assertIn('dangling', [item.get('skill') for item in manifest['unavailable']])
            config = json.loads((output / 'payload/.gemini/config/config.json').read_text())
            self.assertNotIn('remoteControlHostname', config['userSettings'])
            self.assertTrue(config['plugins']['demo']['enabled'])
            mcp = json.loads((output / 'payload/.gemini/config/mcp_config.json').read_text())
            self.assertEqual(mcp['mcpServers']['tool']['command'], str(target) + '/.local/bin/tool')
            settings = json.loads((output / 'payload/.gemini/antigravity-cli/settings.json').read_text())
            self.assertEqual(settings['trustedWorkspaces'], [str(target)])

    def test_boundary_and_private_key_rejection(self):
        for bad in ('../outside', '/absolute', '.ssh/id_rsa', '.codex/memories/owner.md'):
            with self.assertRaises(ValueError):
                package.safe_relative(bad)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source/.codex').mkdir(parents=True)
            (root / 'source/.codex/auth.json').write_text('-----' + 'BEGIN PRIVATE ' + 'KEY-----\n' + 'A' * 64)
            with self.assertRaises(ValueError):
                package.build(root / 'source', str(root / 'target'), 'linux', root / 'output', include_auth=True)


if __name__ == '__main__':
    unittest.main()
