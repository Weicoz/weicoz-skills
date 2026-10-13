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
            package.build(source, str(target), 'linux', output, shell=True, config=False)
            result = subprocess.run(['node', str(Path(__file__).with_name('install.mjs')), str(output)],
                                    env={**os.environ, 'HOME': str(target)}, capture_output=True)
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
            result = subprocess.run(['node', str(Path(__file__).with_name('install.mjs')), str(output)],
                                    env={**os.environ, 'HOME': str(target)}, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual((target / '.codex/sessions/existing.json').read_text(), 'existing work')
            self.assertEqual((target / '.codex/skills/demo').resolve(), (target / '.agents/skills/demo').resolve())
            self.assertEqual((target / '.codex/AGENTS.md').resolve(), (target / '.agents/AGENTS.md').resolve())

    def test_boundary_and_private_key_rejection(self):
        for bad in ('../outside', '/absolute', '.ssh/id_rsa', '.codex/memories/owner.md'):
            with self.assertRaises(ValueError):
                package.safe_relative(bad)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source/.codex').mkdir(parents=True)
            (root / 'source/.codex/auth.json').write_text('-----BEGIN PRIVATE KEY-----\n' + 'A' * 64)
            with self.assertRaises(ValueError):
                package.build(root / 'source', str(root / 'target'), 'linux', root / 'output', include_auth=True)


if __name__ == '__main__':
    unittest.main()
