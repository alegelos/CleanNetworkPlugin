#!/usr/bin/env python3
"""Export the locked Git revisions without copying local build output or edits."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from plugin_tools import PLUGIN, inventory, read_json, safe_relative


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def export_source(repo, source, destination):
    commit = source['commit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or source['path'] != f'skills/{source["skill"]}':
        raise ValueError('Invalid source commit or skill path')
    resolved = git(repo, 'rev-parse', f'refs/tags/{source["tag"]}^{{commit}}').decode().strip()
    if resolved != commit:
        raise ValueError(f'Tag does not match the pinned commit: {source["skill"]}')
    prefix = safe_relative(source['path'])
    records = git(repo, 'ls-tree', '-rz', '--full-tree', commit, '--', str(prefix)).split(b'\0')
    destination.mkdir()
    for record in filter(None, records):
        header, raw_path = record.split(b'\t', 1)
        mode, kind, object_id = header.decode().split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Only regular source files can be bundled')
        relative = safe_relative(raw_path.decode()).relative_to(prefix)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(repo, 'cat-file', 'blob', object_id))
        target.chmod(0o755 if mode == '100755' else 0o644)
    if not (destination / 'SKILL.md').is_file():
        raise ValueError('Source commit has no skill entrypoint')
    if git(repo, 'show', f'{commit}:LICENSE') != (PLUGIN / 'LICENSE').read_bytes():
        raise ValueError('Upstream license differs; review before bundling')
    return inventory(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ios-checkout', type=Path, required=True)
    parser.add_argument('--android-checkout', type=Path, required=True)
    args = parser.parse_args()
    repos = {'ioscleannetwork': args.ios_checkout, 'androidcleannetwork': args.android_checkout}
    lock_path = PLUGIN / 'sources.lock.json'
    lock = read_json(lock_path)
    with tempfile.TemporaryDirectory(prefix='sync-skills-') as temp:
        staging = Path(temp)
        for source in lock['sources']:
            name = source['skill']
            if name not in repos:
                raise ValueError(f'Unknown SDK skill: {name}')
            target = PLUGIN / 'skills' / name
            if target.exists() and inventory(target) != source['files']:
                raise ValueError(f'Bundled {name} has local changes; refusing to overwrite')
            source['files'] = export_source(repos[name], source, staging / name)
        for source in lock['sources']:
            target = PLUGIN / 'skills' / source['skill']
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(staging / source['skill'], target)
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + '\n')
    for source in lock['sources']:
        print(f'{source["skill"]}: {source["tag"]} at {source["commit"]}, {len(source["files"])} files')


if __name__ == '__main__':
    main()
