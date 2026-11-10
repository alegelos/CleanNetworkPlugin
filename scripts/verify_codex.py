#!/usr/bin/env python3
"""Exercise an extracted plugin in Codex without changing the personal profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time

from plugin_tools import ROOT, SKILLS, extract_zip, inventory, validate

PLUGIN_ID = 'cleannetwork@cleannetwork-tools'


def list_skills(binary, env, consumer, log_path):
    messages = queue.Queue()
    with log_path.open('w') as log:
        process = subprocess.Popen([binary, 'app-server', '--stdio'], cwd=consumer,
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=log, text=True)

        def read_output():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)

        threading.Thread(target=read_output, daemon=True).start()

        def send(message):
            process.stdin.write(json.dumps(message) + '\n')
            process.stdin.flush()

        def request(number, method, params):
            send({'id': number, 'method': method, 'params': params})
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                line = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if line is None:
                    raise RuntimeError('Codex app-server exited before responding')
                message = json.loads(line)
                if message.get('id') == number:
                    if 'error' in message:
                        raise RuntimeError(message['error'])
                    return message['result']
            raise TimeoutError(f'Codex did not respond to {method}')

        try:
            request(1, 'initialize', {'clientInfo': {'name': 'cleannetwork-check', 'version': '0.1.0'},
                                      'capabilities': {'experimentalApi': True}})
            send({'method': 'initialized', 'params': {}})
            result = request(2, 'skills/list', {'cwds': [str(consumer)], 'forceReload': True})
            rows = [row for row in result['data'] if row['cwd'] == str(consumer)]
            if len(rows) != 1 or rows[0].get('errors'):
                raise ValueError(f'Unexpected skill discovery result: {result}')
            return [s for s in rows[0]['skills'] if s.get('pluginId') == PLUGIN_ID]
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()


def check(work_dir):
    binary = shutil.which('codex')
    if not binary:
        raise RuntimeError('Install a Codex CLI with plugin commands first')
    manifest = validate()
    archive = ROOT / 'dist' / f'cleannetwork-marketplace-{manifest["version"]}.zip'
    if not archive.is_file():
        raise ValueError('Run scripts/build_plugin.py first')
    work_dir.mkdir(parents=True, exist_ok=True)
    # Place the consumer and marketplace outside the checkout so ancestor
    # discovery cannot fall back to this repository's original catalog.
    work = Path(tempfile.mkdtemp(prefix='cleannetwork-codex-')).resolve()
    if work.is_relative_to(ROOT.resolve()):
        raise ValueError('The runtime check must execute outside the source checkout')
    extracted = work / 'marketplace'
    extract_zip(archive, extracted)
    validate(extracted)
    if inventory(extracted / 'plugins/cleannetwork') != inventory(ROOT / 'plugins/cleannetwork'):
        raise ValueError('Archive is stale; rebuild before checking Codex')
    profile = work / 'codex-profile'
    profile.mkdir()
    consumer = work / 'consumer'
    consumer.mkdir()
    # CODEX_HOME is the documented profile override, scoped to these child
    # processes. Do not alter HOME or the parent process/user configuration.
    env = dict(os.environ, CODEX_HOME=str(profile))
    normal_config = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    original_config = normal_config.read_bytes() if normal_config.exists() else None

    def run(*args):
        result = subprocess.run([binary, *args], cwd=consumer, env=env, text=True,
                                capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(f'Codex command failed: {args}\n{result.stderr}')
        return json.loads(result.stdout)

    catalog = run('plugin', 'marketplace', 'add', str(extracted), '--json')
    if catalog['marketplaceName'] != 'cleannetwork-tools':
        raise ValueError('Wrong marketplace discovered')
    if Path(catalog['installedRoot']).resolve() != extracted.resolve():
        raise ValueError('Codex registered a different marketplace source')
    install = run('plugin', 'add', PLUGIN_ID, '--json')
    installed_path = Path(install['installedPath'])
    if not installed_path.is_relative_to(profile) or install['version'] != manifest['version']:
        raise ValueError('Install escaped the test profile or has the wrong version')
    if inventory(installed_path) != inventory(ROOT / 'plugins/cleannetwork'):
        raise ValueError('Installed plugin content/permissions differ')
    listing = run('plugin', 'list', '--marketplace', 'cleannetwork-tools', '--json')
    entry = next(p for p in listing['installed'] if p['pluginId'] == PLUGIN_ID)
    if not entry['installed'] or not entry['enabled'] or entry['version'] != manifest['version']:
        raise ValueError('Installed plugin is not enabled at the expected version')
    if Path(entry['marketplaceSource']['source']).resolve() != extracted.resolve():
        raise ValueError('Codex discovered the original source instead of the extracted marketplace')
    skills = list_skills(binary, env, consumer, work / 'app-server.log')
    if {s['name'] for s in skills} != {f'cleannetwork:{name}' for name in SKILLS}:
        raise ValueError('Codex did not discover all three namespaced skills')
    for skill in skills:
        path = Path(skill['path'])
        if not skill['enabled'] or not path.is_relative_to(installed_path) or not path.is_file():
            raise ValueError('Skill was not loaded from the installed cache')

    # Prove the documented update flow without first removing the plugin.
    # Only the extracted test marketplace changes; the distributable stays put.
    test_manifest_path = extracted / 'plugins/cleannetwork/plugin.json'
    original_manifest = test_manifest_path.read_bytes()
    updated_manifest = json.loads(original_manifest)
    major, minor, patch = map(int, manifest['version'].split('.'))
    updated_manifest['version'] = f'{major}.{minor}.{patch + 1}'
    test_manifest_path.write_text(json.dumps(updated_manifest, indent=2) + '\n')
    claude_manifest_path = extracted / 'plugins/cleannetwork/.claude-plugin/plugin.json'
    original_claude_manifest = claude_manifest_path.read_bytes()
    updated_claude_manifest = json.loads(original_claude_manifest)
    updated_claude_manifest['version'] = updated_manifest['version']
    claude_manifest_path.write_text(json.dumps(updated_claude_manifest, indent=2) + '\n')
    validate(extracted)
    updated = run('plugin', 'add', PLUGIN_ID, '--json')
    if updated['version'] != updated_manifest['version']:
        raise ValueError('Adding the newer version did not update the installation')
    if inventory(Path(updated['installedPath'])) != inventory(extracted / 'plugins/cleannetwork'):
        raise ValueError('Updated installation does not contain the new package')
    updated_entry = next(p for p in run('plugin', 'list', '--marketplace', 'cleannetwork-tools', '--json')['installed'] if p['pluginId'] == PLUGIN_ID)
    if updated_entry['version'] != updated_manifest['version']:
        raise ValueError('Codex lists a stale version after update')

    # Remove the test update and reinstall the original package. Keep this last
    # install for independent review and executable-example checks.
    run('plugin', 'remove', PLUGIN_ID, '--json')
    if any(p['pluginId'] == PLUGIN_ID for p in run('plugin', 'list', '--marketplace', 'cleannetwork-tools', '--json')['installed']):
        raise ValueError('Plugin removal did not remove the installation')
    test_manifest_path.write_bytes(original_manifest)
    claude_manifest_path.write_bytes(original_claude_manifest)
    reinstall = run('plugin', 'add', PLUGIN_ID, '--json')
    if inventory(Path(reinstall['installedPath'])) != inventory(ROOT / 'plugins/cleannetwork'):
        raise ValueError('Reinstalled plugin differs')
    if (normal_config.read_bytes() if normal_config.exists() else None) != original_config:
        raise ValueError('Personal Codex configuration changed during isolated verification')
    receipt = {'codex_version': subprocess.check_output([binary, '--version'], text=True).strip(),
               'plugin_id': PLUGIN_ID, 'version': manifest['version'],
               'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'installed_path': reinstall['installedPath'], 'skills': skills,
               'work_dir': str(work), 'personal_config_unchanged': True,
               'update_without_uninstall': updated_manifest['version'], 'removal_verified': True}
    (work_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    shutil.copy2(work / 'app-server.log', work_dir / 'app-server.log')
    print(json.dumps({'installed_path': reinstall['installedPath'], 'skills': [s['name'] for s in skills]}, indent=2))
    print('CODEX_PLUGIN_VERIFIED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    check(parser.parse_args().work_dir.resolve())
