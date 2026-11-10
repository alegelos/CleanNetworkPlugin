import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from plugin_tools import ROOT, extract_zip, inventory, validate
from build_plugin import build
from claude_upload import validate_upload
import sync_skills


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cleannetwork-test-')
        self.root = Path(self.temp.name) / 'project'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '.unlazy', 'dist', '__pycache__'))
        self.plugin = self.root / 'plugins/cleannetwork'
        validate(self.root)  # Positive control for every negative test.

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_round_trip_is_reproducible_and_executable(self):
        first = build(self.root)
        digests = [hashlib.sha256(path.read_bytes()).digest() for path in first]
        second = build(self.root)
        self.assertEqual(digests, [hashlib.sha256(path.read_bytes()).digest() for path in second])
        extracted = Path(self.temp.name) / 'extracted'
        extract_zip(second[1], extracted)
        validate(extracted)
        self.assertEqual(inventory(self.plugin), inventory(extracted / 'plugins/cleannetwork'))
        wrapper = extracted / 'plugins/cleannetwork/skills/androidcleannetwork/assets/UserExample/gradlew'
        self.assertTrue(wrapper.stat().st_mode & 0o111)
        for path in ('README.md', 'AGENTS.md', 'scripts/verify_codex.py',
                     'scripts/verify_claude.py', '.claude-plugin/marketplace.json',
                     'docs/PUBLISHING.md', 'tests/test_plugin.py'):
            self.assertTrue((extracted / path).is_file(), path)
        claude = Path(self.temp.name) / 'claude'
        extract_zip(second[2], claude)
        validate_upload(claude)
        self.assertEqual((self.plugin / 'sources.lock.json').read_bytes(),
                         (claude / 'sources.lock.json').read_bytes())
        self.assertEqual(['.claude-plugin/plugin.json'],
                         [path.relative_to(claude).as_posix() for path in claude.rglob('plugin.json')])

    def test_claude_metadata_mismatch_is_rejected(self):
        manifest = self.plugin / '.claude-plugin/plugin.json'
        original = manifest.read_text()
        for key, value in (('version', '9.9.9'), ('name', 'wrong'), ('hooks', {})):
            data = json.loads(original)
            data[key] = value
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Claude manifest differs'):
                validate(self.root)
        manifest.write_text(original)

    def test_public_listing_rejects_long_subtitle_and_invalid_icon(self):
        manifest = self.plugin / 'plugin.json'
        original = manifest.read_text()
        data = json.loads(original)
        data['extensions']['com.openai']['interface']['shortDescription'] = 'x' * 31
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'public listing field'):
            validate(self.root)
        manifest.write_text(original)
        (self.plugin / 'assets/icon.png').write_bytes(b'not a PNG')
        with self.assertRaisesRegex(ValueError, '512px PNG'):
            validate(self.root)

    def test_claude_catalog_escape_is_rejected(self):
        catalog = self.root / '.claude-plugin/marketplace.json'
        data = json.loads(catalog.read_text())
        data['plugins'][0]['source'] = '../elsewhere'
        catalog.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Claude marketplace does not point'):
            validate(self.root)

    def test_modified_upstream_file_is_rejected(self):
        guide = self.plugin / 'skills/ioscleannetwork/references/integration.md'
        guide.write_text(guide.read_text() + '\nLocal edit\n')
        with self.assertRaisesRegex(ValueError, 'differs from pinned source'):
            validate(self.root)

    def test_sync_refuses_to_overwrite_local_edits(self):
        guide = self.plugin / 'skills/ioscleannetwork/SKILL.md'
        changed = guide.read_bytes() + b'\nlocal change\n'
        guide.write_bytes(changed)
        argv = ['sync_skills.py', '--ios-checkout', self.temp.name, '--android-checkout', self.temp.name]
        with patch.object(sync_skills, 'PLUGIN', self.plugin), patch.object(sys, 'argv', argv):
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                sync_skills.main()
        self.assertEqual(changed, guide.read_bytes())

    def test_broken_router_reference_is_rejected(self):
        router = self.plugin / 'skills/cleannetwork/SKILL.md'
        router.write_text(router.read_text() + '\n[missing](missing.md)\n')
        with self.assertRaisesRegex(ValueError, 'Broken or external'):
            validate(self.root)

    def test_marketplace_escape_is_rejected(self):
        catalog = self.root / '.agents/plugins/marketplace.json'
        data = json.loads(catalog.read_text())
        data['plugins'][0]['source']['path'] = '../elsewhere'
        catalog.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Marketplace does not point'):
            validate(self.root)

    def test_caches_and_symlinks_are_rejected(self):
        cache = self.plugin / '.build'
        cache.mkdir()
        (cache / 'output').write_text('generated')
        with self.assertRaisesRegex(ValueError, 'Generated or local'):
            validate(self.root)
        shutil.rmtree(cache)
        (self.plugin / 'outside').symlink_to(self.root / 'LICENSE')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            validate(self.root)

    def test_zip_rejects_traversal_duplicates_and_symlinks(self):
        archive = Path(self.temp.name) / 'unsafe.zip'
        for mode in ('traversal', 'duplicate', 'symlink'):
            with zipfile.ZipFile(archive, 'w') as z:
                if mode == 'traversal':
                    z.writestr('../escape', 'bad')
                elif mode == 'symlink':
                    info = zipfile.ZipInfo('link')
                    info.external_attr = 0o120777 << 16
                    z.writestr(info, '../escape')
                else:
                    z.writestr('same', 'first')
                    z.writestr('./same', 'second')
            with self.assertRaises(ValueError):
                extract_zip(archive, Path(self.temp.name) / mode)
            self.assertFalse((Path(self.temp.name) / 'escape').exists())

    def test_zip_refuses_existing_file(self):
        archive = Path(self.temp.name) / 'overwrite.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('existing', 'replacement')
        destination = Path(self.temp.name) / 'output'
        destination.mkdir()
        existing = destination / 'existing'
        existing.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            extract_zip(archive, destination)
        self.assertEqual('keep', existing.read_text())

    def test_source_export_uses_pinned_git_objects_and_checks_tag(self):
        repo = Path(self.temp.name) / 'sdk'
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)
        git('init', '-q')
        skill = repo / 'skills/ioscleannetwork'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('committed guide\n')
        (repo / 'LICENSE').write_bytes((self.plugin / 'LICENSE').read_bytes())
        git('add', '.')
        git('-c', 'user.name=User', '-c', 'user.email=user@example.com', 'commit', '-qm', 'fixture')
        commit = git('rev-parse', 'HEAD').decode().strip()
        git('tag', '1.0.4')
        (skill / 'SKILL.md').write_text('uncommitted change\n')
        (skill / '.build').mkdir()
        (skill / '.build/cache').write_text('ignored by Git object export')
        source = {'skill': 'ioscleannetwork', 'path': 'skills/ioscleannetwork', 'tag': '1.0.4', 'commit': commit}
        target = Path(self.temp.name) / 'export'
        with patch.object(sync_skills, 'PLUGIN', self.plugin):
            result = sync_skills.export_source(repo, source, target)
            self.assertEqual({'SKILL.md'}, set(result))
            self.assertEqual('committed guide\n', (target / 'SKILL.md').read_text())
            source['commit'] = '0' * 40
            with self.assertRaisesRegex(ValueError, 'Tag does not match'):
                sync_skills.export_source(repo, source, Path(self.temp.name) / 'invalid')


if __name__ == '__main__':
    unittest.main()
