#!/usr/bin/env python3
"""Check extracted distributions in Claude Code using a temporary profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from claude_upload import create_upload, validate_upload
from plugin_tools import ROOT, SKILLS, extract_zip, inventory, validate

PLUGIN_ID = 'cleannetwork@cleannetwork-tools'


def check(work_dir, claude_bin=None):
    binary = str(claude_bin.resolve()) if claude_bin else shutil.which('claude')
    if not binary or not Path(binary).is_file():
        raise RuntimeError('Install Claude Code or supply --claude-bin /path/to/claude')
    manifest = validate()
    archive = ROOT / 'dist' / f'cleannetwork-marketplace-{manifest["version"]}.zip'
    upload_archive = ROOT / 'dist' / f'cleannetwork-claude-{manifest["version"]}.zip'
    work_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='cleannetwork-claude-')).resolve()
    if work.is_relative_to(ROOT.resolve()):
        raise ValueError('Runtime verification must run outside the source checkout')
    extracted, consumer, profile = (work / name for name in ('marketplace', 'consumer', 'profile'))
    consumer.mkdir()
    profile.mkdir()
    extract_zip(archive, extracted)
    validate(extracted)
    source_plugin = extracted / 'plugins/cleannetwork'
    if inventory(source_plugin) != inventory(ROOT / 'plugins/cleannetwork'):
        raise ValueError('Marketplace archive is stale; rebuild first')
    upload_marketplace = work / 'upload-marketplace'
    upload_plugin = upload_marketplace / 'plugins/cleannetwork'
    extract_zip(upload_archive, upload_plugin)
    validate_upload(upload_plugin)
    expected_upload = create_upload(source_plugin, work / 'expected-upload')
    if inventory(upload_plugin) != inventory(expected_upload):
        raise ValueError('Upload archive is stale; rebuild first')

    # CLAUDE_CONFIG_DIR is the documented profile override, scoped to children.
    # The consumer is outside this checkout and contains no project settings.
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(profile))
    normal_profile = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude')))
    normal_paths = [Path.home() / '.claude.json', normal_profile / '.claude.json',
                    normal_profile / 'settings.json', normal_profile / 'plugins/installed_plugins.json',
                    normal_profile / 'plugins/known_marketplaces.json']

    def personal_fingerprints():
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                for path in normal_paths}

    before = personal_fingerprints()
    commands = []

    def run(*args, as_json=False):
        result = subprocess.run([binary, *args], cwd=consumer, env=env,
                                text=True, capture_output=True, timeout=60)
        commands.append({'args': list(args), 'exit_code': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError(f'Claude command failed: {args}\n{result.stdout}\n{result.stderr}')
        return json.loads(result.stdout) if as_json else result.stdout

    def installed(plugin_id, expected_source, expected_version):
        listing = run('plugin', 'list', '--json', as_json=True)
        rows = [row for row in listing if row['id'] == plugin_id]
        if len(rows) != 1:
            raise ValueError('Claude did not list exactly one expected installation')
        row = rows[0]
        if row['scope'] != 'user' or not row['enabled'] or row['version'] != expected_version:
            raise ValueError('Unexpected installed plugin scope/status/version')
        cache = Path(row['installPath']).resolve()
        if not cache.is_relative_to(profile) or inventory(cache) != inventory(expected_source):
            raise ValueError('Installed cache escaped the test profile or differs from its source')
        # Claude may load local marketplaces directly; verify the actual source
        # it reports rather than claiming cache loading when it reads the folder.
        loaded = Path(row.get('readFromFolder', row['installPath'])).resolve()
        if loaded not in (cache, expected_source.resolve()) or inventory(loaded) != inventory(expected_source):
            raise ValueError('Claude reads an unexpected plugin folder')
        details = run('plugin', 'details', plugin_id)
        match = re.search(r'^\s*Skills \((\d+)\)\s+(.+)$', details, re.M)
        if not match or int(match[1]) != len(SKILLS) or set(match[2].split(', ')) != SKILLS:
            raise ValueError('Claude did not discover exactly the three expected skills')
        for kind in ('Agents', 'Hooks', 'MCP servers', 'LSP servers'):
            if not re.search(rf'^\s*{kind} \(0\)\s*$', details, re.M):
                raise ValueError(f'Unexpected executable component: {kind}')
        return row

    try:
        cli_version = run('--version').strip()
        for target in (source_plugin, extracted, upload_plugin):
            report = run('plugin', 'validate', str(target), '--strict', '--json', as_json=True)
            if not report['success']:
                raise ValueError('Claude reported invalid metadata')
        run('plugin', 'marketplace', 'add', str(extracted))
        catalogs = run('plugin', 'marketplace', 'list', '--json', as_json=True)
        catalog = next(c for c in catalogs if c['name'] == 'cleannetwork-tools')
        if catalog['source'] != 'directory' or Path(catalog['path']).resolve() != extracted:
            raise ValueError('Claude registered the wrong marketplace')
        run('plugin', 'install', PLUGIN_ID, '--scope', 'user', '--json', as_json=True)
        original_install = installed(PLUGIN_ID, source_plugin, manifest['version'])

        # Change only temporary manifests; exercise update without uninstalling.
        major, minor, patch = map(int, manifest['version'].split('.'))
        next_version = f'{major}.{minor}.{patch + 1}'
        originals = {}
        for relative in ('plugin.json', '.claude-plugin/plugin.json'):
            path = source_plugin / relative
            originals[path] = path.read_bytes()
            data = json.loads(originals[path])
            data['version'] = next_version
            path.write_text(json.dumps(data, indent=2) + '\n')
        validate(extracted)
        run('plugin', 'marketplace', 'update', 'cleannetwork-tools')
        run('plugin', 'update', PLUGIN_ID, '--scope', 'user', '--json', as_json=True)
        installed(PLUGIN_ID, source_plugin, next_version)
        run('plugin', 'uninstall', PLUGIN_ID, '--scope', 'user', '--json', as_json=True)
        if any(row['id'] == PLUGIN_ID for row in run('plugin', 'list', '--json', as_json=True)):
            raise ValueError('Claude still lists the removed plugin')
        run('plugin', 'marketplace', 'remove', 'cleannetwork-tools')
        if any(c['name'] == 'cleannetwork-tools' for c in run('plugin', 'marketplace', 'list', '--json', as_json=True)):
            raise ValueError('Claude still lists the removed marketplace')
        for path, original in originals.items():
            path.write_bytes(original)

        # Exercise the Claude-only upload bytes locally as well. This does not
        # upload anything to the account or prove server acceptance/sync.
        catalog_dir = upload_marketplace / '.claude-plugin'
        catalog_dir.mkdir()
        (catalog_dir / 'marketplace.json').write_text(json.dumps({
            'name': 'cleannetwork-upload-check', 'description': 'Temporary upload verification',
            'owner': {'name': 'User'}, 'plugins': [{'name': 'cleannetwork', 'source': './plugins/cleannetwork'}]
        }) + '\n')
        run('plugin', 'marketplace', 'add', str(upload_marketplace))
        upload_id = 'cleannetwork@cleannetwork-upload-check'
        run('plugin', 'install', upload_id, '--scope', 'user', '--json', as_json=True)
        upload_install = installed(upload_id, upload_plugin, manifest['version'])
        run('plugin', 'uninstall', upload_id, '--scope', 'user', '--json', as_json=True)
        run('plugin', 'marketplace', 'remove', 'cleannetwork-upload-check')
        if run('plugin', 'list', '--json', as_json=True) or run('plugin', 'marketplace', 'list', '--json', as_json=True):
            raise ValueError('Temporary Claude profile still contains an installation')
    finally:
        (work_dir / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if personal_fingerprints() != before:
            raise ValueError('Personal Claude configuration changed during isolated verification')

    receipt = {'claude_version': cli_version, 'plugin_id': PLUGIN_ID, 'version': manifest['version'],
               'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'upload_sha256': hashlib.sha256(upload_archive.read_bytes()).hexdigest(),
               'work_dir': str(work), 'install': original_install, 'upload_install': upload_install,
               'skills': sorted(SKILLS), 'update_without_uninstall': next_version,
               'removal_verified': True, 'personal_config_unchanged': True,
               'account_upload_performed': False}
    (work_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'claude_version': cli_version, 'skills': sorted(SKILLS), 'work_dir': str(work)}))
    print('CLAUDE_PLUGIN_VERIFIED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--claude-bin', type=Path)
    args = parser.parse_args()
    check(args.work_dir.resolve(), args.claude_bin)
