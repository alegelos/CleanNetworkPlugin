#!/usr/bin/env python3
"""Build a dual-client plugin, local marketplace and Claude upload ZIP."""
import hashlib
from pathlib import Path
import tempfile

from claude_upload import MAX_BYTES, create_upload, validate_upload
from plugin_tools import ROOT, extract_zip, files_under, inventory, validate, write_zip


def build(root=ROOT):
    manifest = validate(root)
    plugin = root / 'plugins/cleannetwork'
    dist = root / 'dist'
    dist.mkdir(exist_ok=True)
    version = manifest['version']
    plugin_zip = dist / f'cleannetwork-{version}.zip'
    marketplace_zip = dist / f'cleannetwork-marketplace-{version}.zip'
    claude_zip = dist / f'cleannetwork-claude-{version}.zip'
    files = files_under(plugin)
    write_zip(plugin_zip, files)
    marketplace_files = {f'plugins/cleannetwork/{name}': path for name, path in files.items()}
    for relative in ('.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json',
                     'README.md', 'AGENTS.md', 'LICENSE'):
        marketplace_files[relative] = root / relative
    for directory in ('scripts', 'tests'):
        for path in (root / directory).glob('*.py'):
            marketplace_files[path.relative_to(root).as_posix()] = path
    for path in (root / 'docs').rglob('*.md'):
        marketplace_files[path.relative_to(root).as_posix()] = path
    write_zip(marketplace_zip, marketplace_files)
    with tempfile.TemporaryDirectory(prefix='plugin-bundle-') as temp:
        temp = Path(temp)
        create_upload(plugin, temp / 'claude-staged')
        write_zip(claude_zip, files_under(temp / 'claude-staged'))
        if claude_zip.stat().st_size > MAX_BYTES:
            raise ValueError('Claude upload archive exceeds the size limit')
        extract_zip(plugin_zip, temp / 'plugin')
        extract_zip(marketplace_zip, temp / 'marketplace')
        extract_zip(claude_zip, temp / 'claude')
        if inventory(temp / 'plugin') != inventory(plugin):
            raise ValueError('Plugin ZIP round-trip differs')
        validate(temp / 'marketplace')
        validate_upload(temp / 'claude')
        if inventory(temp / 'claude') != inventory(temp / 'claude-staged'):
            raise ValueError('Claude ZIP round-trip differs')
    artifacts = [plugin_zip, marketplace_zip, claude_zip]
    (dist / 'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in artifacts))
    return artifacts


if __name__ == '__main__':
    for path in build():
        print(path)
    print('PLUGIN_ARCHIVES_READY')
