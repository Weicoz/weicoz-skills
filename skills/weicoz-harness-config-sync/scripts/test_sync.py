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
INSTALL = Path(__file__).with_name('install.mjs')


class DeviceSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.target = self.root / 'source', self.root / 'target'
        self.source.mkdir(); self.target.mkdir()
        self.put(self.source, '.codex/config.toml', 'model="one"\n')
        self.put(self.source, '.kimi-code/config.toml', 'default_model="one"\n')
        self.put(self.source, '.kimi-code/mcp.json', '{"mcpServers":{}}')
        self.count = 0

    def put(self, home, rel, data):
        p = home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    def build(self, **kwargs):
        self.count += 1
        output = self.root / f'package-{self.count}'
        package.build(self.source, str(self.target), os.sys.platform, output,
                      source_id='shared', device_id='test-device', **kwargs)
        return output

    def run_cli(self, args, ok=True, preload=None):
        command = ['node'] + (['--import', str(preload)] if preload else []) + [str(INSTALL)] + [str(x) for x in args]
        result = subprocess.run(command, env={**os.environ, 'HOME': str(self.target)}, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def apply(self, output, replace=()):
        flags = [v for rel in replace for v in ('--replace', rel)]
        plan = self.run_cli([output, *flags])
        return self.run_cli([output, *flags, '--apply', '--plan', plan['plan_token']])

    def test_preview_is_read_only_and_apply_repeat_is_unchanged(self):
        output = self.build()
        plan = self.run_cli([output])
        self.assertEqual(len(plan['changes']), 3)
        self.assertEqual(list(self.target.iterdir()), [])
        self.apply(output)
        state = self.target / '.local/state/harness-config-sync/state.json'
        before = state.read_bytes()
        self.assertTrue(self.apply(output)['unchanged'])
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(self.run_cli(['--status'])['drift'], [])

    def test_conflict_and_expired_preview_never_overwrite(self):
        output = self.build()
        self.apply(output)
        self.put(self.source, '.codex/config.toml', 'model="two"\n')
        update = self.build()
        plan = self.run_cli([update])
        original = self.put(self.target, '.codex/config.toml', 'model="device-edit"\n')
        self.run_cli([update, '--apply', '--plan', plan['plan_token']], ok=False)
        new_plan = self.run_cli([update])
        self.assertEqual(new_plan['conflicts'], ['.codex/config.toml'])
        self.run_cli([update, '--apply', '--plan', new_plan['plan_token']], ok=False)
        self.assertIn('device-edit', original.read_text())
        self.apply(update, ['.codex/config.toml'])
        self.assertIn('two', original.read_text())

    def test_overlay_and_keep_preserve_device_values(self):
        self.put(self.source, '.kimi-code/config.toml', 'api_key="' + 'fixture-secret' + '"\n')
        overlay = self.root / 'overlay'
        self.put(overlay, '.kimi-code/config.toml', 'default_model="device-model"\n')
        device_config = self.put(self.target, '.codex/config.toml', 'model="local"\n')
        output = self.build(overlays=[overlay], keep=['.codex/config.toml'])
        self.apply(output)
        self.assertIn('local', device_config.read_text())
        self.assertIn('device-model', (self.target / '.kimi-code/config.toml').read_text())

    def test_inline_credentials_fail_closed_and_never_echo(self):
        value = 'fixture-' + 'x' * 24
        self.put(self.source, '.kimi-code/config.toml', f'[providers.demo]\napi_key="{value}"\n')
        with self.assertRaises(ValueError) as error:
            self.build()
        self.assertNotIn(value, str(error.exception))
        output = self.build(include_auth=True)
        self.apply(output)
        self.assertIn(value, (self.target / '.kimi-code/config.toml').read_text())
        self.put(self.source, '.kimi-code/config.toml', 'default_model="public"\n')
        clean = self.build()
        result = self.run_cli([clean], ok=False)
        self.assertNotIn(value, result.stderr)
        self.assertIn('凭据', result.stderr)

    def test_rollback_restores_previous_files_links_and_baseline(self):
        self.put(self.source, '.agents/AGENTS.md', 'shared rules one\n')
        self.put(self.source, '.kimi-code/AGENTS.md', 'shared rules one\n')
        first = self.build()
        self.apply(first)
        original_state = (self.target / '.local/state/harness-config-sync/state.json').read_bytes()
        self.put(self.source, '.agents/AGENTS.md', 'shared rules two\n')
        self.put(self.source, '.kimi-code/config.toml', 'default_model="two"\n')
        updated = self.build()
        installed = self.apply(updated)
        self.run_cli(['--rollback', installed['transaction']])
        self.assertEqual((self.target / '.local/state/harness-config-sync/state.json').read_bytes(), original_state)
        self.assertIn('one', (self.target / '.kimi-code/config.toml').read_text())
        self.assertEqual((self.target / '.kimi-code/AGENTS.md').resolve(), (self.target / '.agents/AGENTS.md').resolve())
        self.assertEqual(self.run_cli(['--status'])['drift'], [])

    def test_io_failure_rolls_back_all_written_files(self):
        self.apply(self.build())
        before = {p: (self.target / p).read_bytes() for p in ['.codex/config.toml', '.kimi-code/config.toml', '.kimi-code/mcp.json']}
        self.put(self.source, '.codex/config.toml', 'model="two"\n')
        self.put(self.source, '.kimi-code/mcp.json', '{"mcpServers":{"new":{}}}')
        output = self.build()
        plan = self.run_cli([output])
        preload = self.root / 'io-failure.mjs'
        preload.write_text("import fs from 'node:fs'; const original = fs.renameSync; fs.renameSync = (a,b) => { if (b.endsWith('/.kimi-code/mcp.json') && a.includes('.sync-')) { const e=new Error();e.code='EIO';throw e; } return original(a,b); };\n")
        result = self.run_cli([output, '--apply', '--plan', plan['plan_token']], ok=False, preload=preload)
        self.assertIn('自动回滚', result.stderr)
        for rel, data in before.items():
            self.assertEqual((self.target / rel).read_bytes(), data)
        self.assertEqual(self.run_cli(['--status'])['drift'], [])

    def test_tampered_package_and_symlink_parent_are_rejected(self):
        output = self.build()
        (output / 'payload/.codex/config.toml').write_text('model="tampered"\n')
        self.run_cli([output], ok=False)
        self.assertEqual(list(self.target.iterdir()), [])
        fresh = self.build()
        outside = self.root / 'outside'; outside.mkdir()
        (self.target / '.codex').symlink_to(outside)
        self.run_cli([fresh], ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_retired_paths_are_reported_and_never_deleted(self):
        self.apply(self.build())
        (self.source / '.kimi-code/mcp.json').unlink()
        updated = self.build()
        plan = self.run_cli([updated])
        self.assertIn('.kimi-code/mcp.json', plan['retained'])
        self.apply(updated)
        self.assertTrue((self.target / '.kimi-code/mcp.json').exists())

    def test_claude_and_personal_history_are_excluded(self):
        for rel in ['.claude/settings.json', '.kimi-code/sessions/private.json', '.kimi-code/oauth/private.json', '.kimi-code/credentials/private.json']:
            self.put(self.source, rel, '{"personal":true}')
        output = self.build()
        paths = json.loads((output / 'manifest.json').read_text())['files']
        self.assertEqual(set(paths), {'.codex/config.toml', '.kimi-code/config.toml', '.kimi-code/mcp.json'})
        with self.assertRaises(ValueError):
            package.safe_relative('.claude/settings.json')

    def test_shell_keep_and_overlay_are_respected_and_repeat_is_stable(self):
        self.put(self.source, '.zshrc', 'alias origin=source\n')
        overlay = self.root / 'overlay'
        self.put(overlay, '.zshrc', 'alias origin=device\n')
        output = self.build(shell=True, overlays=[overlay], keep=['.zshenv'])
        paths = json.loads((output / 'manifest.json').read_text())['files']
        self.assertNotIn('.zshenv', paths)
        self.assertIn('origin=device', (output / 'payload/.zshrc').read_text())
        self.apply(output)
        self.assertTrue(self.apply(output)['unchanged'])
        kept = self.build(shell=True, overlays=[overlay], keep=['.zshrc', '.zshenv'])
        self.assertNotIn('.zshrc', json.loads((kept / 'manifest.json').read_text())['files'])

    def test_same_public_revision_updates_changed_device_management_scope(self):
        self.apply(self.build(revision='v1'))
        package = self.build(revision='v1', keep=['.kimi-code/mcp.json'])
        result = self.apply(package)
        self.assertNotIn('unchanged', result)
        status = self.run_cli(['--status'])
        self.assertEqual(status['managed'], 2)
        self.assertIn('.kimi-code/mcp.json', status['retained'])

    def test_original_hardlink_updates_and_rolls_back_as_hardlink(self):
        self.put(self.source, '.agents/AGENTS.md', 'new rules\n')
        self.put(self.source, '.kimi-code/AGENTS.md', 'new rules\n')
        canonical = self.put(self.target, '.agents/AGENTS.md', 'old rules\n')
        (self.target / '.kimi-code').mkdir()
        os.link(canonical, self.target / '.kimi-code/AGENTS.md')
        output = self.build()
        installed = self.apply(output, ['.agents/AGENTS.md'])
        self.assertEqual(self.run_cli(['--status'])['drift'], [])
        self.run_cli(['--rollback', installed['transaction']])
        self.assertEqual(canonical.read_text(), 'old rules\n')
        self.assertTrue(os.path.samefile(canonical, self.target / '.kimi-code/AGENTS.md'))

    def test_yaml_flow_and_camel_case_secrets_fail_closed(self):
        for suffix, data in [('.yml', 'config: {apiKey: fixture-sensitive}'),
                             ('.json', '{"clientSecret":"fixture-sensitive"}'),
                             ('.toml', 'refreshToken="fixture-sensitive"')]:
            self.assertTrue(package.embedded_credentials(data.encode(), suffix))
        self.assertTrue(package.embedded_credentials(b'{"password":12345}', '.json'))
        disguised = self.put(self.root, 'disguised.txt', 'api_key="fixture-secret"\n')
        with self.assertRaises(ValueError):
            self.build(extras=[str(disguised) + '=.kimi-code/extra.toml'])

    def test_target_yaml_flow_secrets_are_preserved(self):
        rel = '.dsh/profiles/dsh-tui/cordis.patch.yml'
        self.put(self.source, rel, 'config: {}\n')
        target = self.put(self.target, rel, 'config: {apiKey: fixture-sensitive}\n')
        output = self.build()
        self.run_cli([output], ok=False)
        self.assertIn('fixture-sensitive', target.read_text())

    def test_pending_transaction_blocks_new_apply_and_is_visible(self):
        self.apply(self.build())
        self.put(self.source, '.codex/config.toml', 'model="two"\n')
        output = self.build()
        plan = self.run_cli([output])
        pending = self.target / '.local/state/harness-config-sync/transactions/incomplete/journal.json'
        self.put(self.target, str(pending.relative_to(self.target)), '{"status":"applying"}')
        result = self.run_cli([output, '--apply', '--plan', plan['plan_token']], ok=False)
        self.assertIn('未完成事务', result.stderr)
        self.assertEqual(self.run_cli(['--status'])['pending'], ['incomplete'])

    def test_verify_and_collect_use_fixed_cli_probes(self):
        self.put(self.source, '.dsh/cordis.patch.yml', 'config: {}\n')
        self.put(self.source, '.gemini/config/config.json', '{}')
        self.apply(self.build(versions={name: '9.9.9' for name in ('codex', 'dsh', 'agy', 'kimi')}))
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        for name in ('codex', 'dsh', 'agy', 'kimi'):
            p = bin_dir / name
            p.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo 9.9.9; fi\nexit 0\n')
            p.chmod(0o700)
        result = subprocess.run(['node', str(INSTALL), '--verify'],
            env={**os.environ, 'HOME': str(self.target), 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['version_parity'], '已验证')
        self.assertEqual(report['model_requests'], '未验证')
        report_path = self.root / 'report.json'; report_path.write_text(result.stdout)
        self.assertEqual(self.run_cli(['--collect', report_path])['devices'][0]['device_id'], 'test-device')

    def test_verify_without_cli_checks_does_not_claim_version_parity(self):
        for p in self.source.rglob('*'):
            if p.is_file(): p.unlink()
        self.put(self.source, '.agents/AGENTS.md', 'rules\n')
        self.apply(self.build())
        self.assertEqual(self.run_cli(['--verify'])['version_parity'], '未验证')

    def test_failed_journal_write_still_attempts_rollback(self):
        self.apply(self.build())
        self.put(self.source, '.codex/config.toml', 'model="two"\n')
        self.put(self.source, '.kimi-code/mcp.json', '{"new":true}')
        output = self.build()
        plan = self.run_cli([output])
        preload = self.root / 'disk-failure.mjs'
        preload.write_text("import fs from 'node:fs'; const original=fs.renameSync; let broken=false; fs.renameSync=(a,b)=>{ if(b.endsWith('/.kimi-code/mcp.json')&&a.includes('.sync-')){broken=true; const e=new Error();e.code='EIO';throw e;} if(broken&&b.endsWith('/journal.json')){const e=new Error();e.code='ENOSPC';throw e;} return original(a,b); };\n")
        result = self.run_cli([output, '--apply', '--plan', plan['plan_token']], ok=False, preload=preload)
        self.assertIn('--rollback', result.stderr)
        self.assertIn('model="one"', (self.target / '.codex/config.toml').read_text())

    def test_old_incomplete_transaction_cannot_restore_over_new_baseline(self):
        old = self.apply(self.build())
        self.put(self.source, '.codex/config.toml', 'model="two"\n')
        self.apply(self.build())
        journal_path = self.target / '.local/state/harness-config-sync/transactions' / old['transaction'] / 'journal.json'
        journal = json.loads(journal_path.read_text()); journal['status'] = 'applying'
        journal_path.write_text(json.dumps(journal))
        self.run_cli(['--rollback', old['transaction']], ok=False)
        self.assertIn('model="two"', (self.target / '.codex/config.toml').read_text())

    def test_windows_cli_shim_and_v_prefixed_versions(self):
        self.apply(self.build(versions={'codex': '9.9.9', 'kimi': '9.9.9'}))
        preload = self.root / 'windows-probes.mjs'
        preload.write_text("import cp from 'node:child_process'; import {syncBuiltinESMExports} from 'node:module'; Object.defineProperty(process,'platform',{value:'win32'}); cp.spawnSync=(command,args)=>{if(command!=='cmd.exe'||!['codex --version','kimi --version','kimi doctor'].includes(args.at(-1)))throw new Error('unexpected probe');return {status:0,stdout:'tool v9.9.9\\n'};};syncBuiltinESMExports();\n")
        result = self.run_cli(['--verify'], preload=preload)
        self.assertEqual(result['version_parity'], '已验证')

    def test_duplicate_config_keys_cannot_hide_credentials(self):
        for suffix, data in [('.json', '{"api_key":"fixture", "api_key":""}'),
                             ('.yaml', 'api_key: fixture\napi_key: ""\n')]:
            with self.assertRaises(ValueError):
                package.embedded_credentials(data.encode(), suffix)
        self.put(self.target, '.kimi-code/mcp.json', '{"token":"fixture", "token":""}')
        output = self.build()
        self.run_cli([output, '--replace', '.kimi-code/mcp.json'], ok=False)

    def test_protected_case_aliases_and_nonportable_names_are_rejected(self):
        for rel in ['.SSH/config', '.Claude/settings.json', '.kimi-code/OAUTH/token',
                    '.LOCAL/state/harness-config-sync/state.json', '.ssh./config', 'nul.txt']:
            with self.assertRaises(ValueError, msg=rel):
                package.safe_relative(rel)
        output = self.build()
        manifest = json.loads((output / 'manifest.json').read_text())
        manifest['files']['.SSH/config'] = manifest['files'].pop('.kimi-code/config.toml')
        p = output / 'payload/.SSH'; p.mkdir()
        (output / 'payload/.kimi-code/config.toml').rename(p / 'config')
        (output / 'manifest.json').write_text(json.dumps(manifest))
        self.run_cli([output], ok=False)
        self.assertFalse((self.target / '.ssh').exists())

    def test_collect_preserves_pending_and_checked_at(self):
        self.apply(self.build())
        self.put(self.target, '.local/state/harness-config-sync/transactions/incomplete/journal.json', '{"status":"applying"}')
        status = self.run_cli(['--status'])
        report = self.root / 'pending-status.json'; report.write_text(json.dumps(status))
        summary = self.run_cli(['--collect', report])['devices'][0]
        self.assertEqual(summary['pending'], ['incomplete'])
        self.assertEqual(summary['checked_at'], status['checked_at'])


if __name__ == '__main__':
    unittest.main()
