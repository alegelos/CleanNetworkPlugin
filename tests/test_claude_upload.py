import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import claude_upload
from claude_upload import (LAYOUT, SOURCE_LOCK, SWIFT_FIXTURE, SWIFT_GUIDE,
                           SWIFT_LINK, UPLOAD_FIXTURE, UPLOAD_LINK,
                           create_upload, validate_upload)
from plugin_tools import PLUGIN, extract_zip, files_under, inventory, write_zip


class ClaudeUploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='claude-upload-test-')
        self.root = Path(self.temporary.name)
        self.plugin = self.root / 'canonical'
        shutil.copytree(PLUGIN, self.plugin)
        self.destination = self.root / 'upload'

    def tearDown(self):
        self.temporary.cleanup()

    def upload(self):
        result = create_upload(self.plugin, self.destination)
        self.assertEqual(self.destination, result)
        validate_upload(result)
        return result

    def change_json(self, path, change):
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_naive_manifest_filter_fails_but_projection_passes(self):
        naive = self.root / 'naive'
        shutil.copytree(self.plugin, naive)
        (naive / 'plugin.json').unlink()
        with self.assertRaisesRegex(ValueError, 'path (characters|depth)'):
            validate_upload(naive)
        self.upload()

    def test_projection_preserves_canonical_files_packages_modes_and_links(self):
        before = inventory(self.plugin)
        # Non-executable modes, not only the Gradle wrapper bit, survive staging.
        (self.plugin / 'LICENSE').chmod(0o640)
        output = self.upload()
        layout = json.loads((output / LAYOUT).read_text())
        self.assertEqual(15, len(layout['transformations']))
        self.assertEqual(json.loads((self.plugin / 'plugin.json').read_text())['version'],
                         layout['base_plugin_version'])
        self.assertEqual((self.plugin / SOURCE_LOCK).read_bytes(), (output / SOURCE_LOCK).read_bytes())
        self.assertFalse((output / 'plugin.json').exists())
        self.assertFalse((output / SWIFT_FIXTURE).exists())
        self.assertTrue((output / UPLOAD_FIXTURE).is_file())
        self.assertEqual((self.plugin / SWIFT_GUIDE).read_bytes().replace(SWIFT_LINK, UPLOAD_LINK, 1),
                         (output / SWIFT_GUIDE).read_bytes())
        moves = {entry['source']: entry['output'] for entry in layout['transformations']}
        expected_paths = {LAYOUT}
        for name, source in files_under(self.plugin).items():
            if name == 'plugin.json':
                continue
            target = output / moves.get(name, name)
            expected_paths.add(target.relative_to(output).as_posix())
            if name != SWIFT_GUIDE:
                self.assertEqual(source.read_bytes(), target.read_bytes(), name)
            self.assertEqual(stat.S_IMODE(source.stat().st_mode), stat.S_IMODE(target.stat().st_mode), name)
            if source.suffix == '.kt':
                self.assertEqual('kotlin', target.parent.name)
                self.assertIn(b'package com.example.user.', target.read_bytes())
        self.assertEqual(expected_paths, set(files_under(output)))
        self.assertEqual(before, inventory(self.plugin))

    def test_archives_are_deterministic_and_validate_after_round_trip(self):
        first = self.upload()
        second = create_upload(self.plugin, self.root / 'second')
        archives = [self.root / 'first.zip', self.root / 'second.zip']
        for archive, folder in zip(archives, (first, second)):
            write_zip(archive, files_under(folder))
        self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())
        with zipfile.ZipFile(archives[0]) as archive:
            for entry in archive.infolist():
                self.assertIn(entry.compress_type, (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
                self.assertFalse(entry.flag_bits & 1)
                self.assertEqual(stat.S_IFREG, stat.S_IFMT(entry.external_attr >> 16))
        extracted = self.root / 'extracted'
        extract_zip(archives[0], extracted)
        validate_upload(extracted)
        self.assertEqual(inventory(first), inventory(extracted))
        wrapper = extracted / 'skills/androidcleannetwork/assets/UserExample/gradlew'
        self.assertTrue(wrapper.stat().st_mode & 0o111)

    def test_collisions_are_rejected_without_partial_output(self):
        kotlin = ('skills/androidcleannetwork/assets/UserExample/user-data/src/test/'
                  'kotlin/com/example/user/data/other/')
        collisions = (UPLOAD_FIXTURE, kotlin + 'UserApiFixtures.kt',
                      kotlin + 'userapifixtures.kt',
                      'skills/androidcleannetwork/assets/UserExample/user-data/src/test/'
                      'kotlin/UserApiFixtures.kt/child.txt')
        for name in collisions:
            with self.subTest(name=name):
                extra = self.plugin / name
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text('collision')
                with self.assertRaisesRegex(ValueError, 'collision'):
                    create_upload(self.plugin, self.destination)
                self.assertFalse(self.destination.exists())
                extra.unlink()

    def test_limits_accept_boundaries_and_reject_unsafe_paths(self):
        for name in ('a' * 255, '/'.join(['a'] * 12),
                     'a' * 200 + '/' + 'b' * 200 + '/' + 'c' * 70,
                     'folder (one)/file name,1.txt'):
            claude_upload._upload_path(name)
        for name in ('a' * 256, '/'.join(['a'] * 13),
                     'a' * 200 + '/' + 'b' * 200 + '/' + 'c' * 71,
                     '../outside', '/absolute', 'bad+name', 'café.txt', 'back\\slash',
                     'bin/tool', 'nested/archive.zip', 'ARCHIVE.ZIP'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                claude_upload._upload_path(name)

    def test_invalid_paths_in_extracted_tree_are_rejected(self):
        output = self.upload()
        for name in ('bad+name', '/'.join(['deep'] * 12 + ['file']), 'bin/tool', 'nested.zip'):
            with self.subTest(name=name):
                extra = output / name
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text('invalid')
                with self.assertRaises(ValueError):
                    validate_upload(output)
                extra.unlink()
                parent = extra.parent
                while parent != output:
                    parent.rmdir()
                    parent = parent.parent
        validate_upload(output)

    def test_file_and_byte_limits_include_provenance(self):
        output = self.upload()
        files = files_under(output)
        size = sum(path.stat().st_size for path in files.values())
        with patch.object(claude_upload, 'MAX_FILES', len(files)), patch.object(claude_upload, 'MAX_BYTES', size):
            validate_upload(output)
        with patch.object(claude_upload, 'MAX_FILES', len(files) - 1):
            with self.assertRaisesRegex(ValueError, 'file count'):
                validate_upload(output)
        with patch.object(claude_upload, 'MAX_BYTES', size - 1):
            with self.assertRaisesRegex(ValueError, 'uncompressed size'):
                validate_upload(output)

    def test_symlinks_are_rejected_in_source_and_output(self):
        output = self.upload()
        for folder in (self.plugin, output):
            with self.subTest(folder=folder.name):
                link = folder / 'link'
                link.symlink_to(folder / 'LICENSE')
                with self.assertRaisesRegex(ValueError, 'Symlink'):
                    if folder == self.plugin:
                        create_upload(folder, self.root / 'other')
                    else:
                        validate_upload(folder)
                link.unlink()

    def test_single_manifest_and_valid_names_are_required(self):
        output = self.upload()
        extra = output / 'plugin.json'
        shutil.copy2(output / '.claude-plugin/plugin.json', extra)
        with self.assertRaisesRegex(ValueError, 'exactly one manifest'):
            validate_upload(output)
        extra.unlink()
        manifest = output / '.claude-plugin/plugin.json'
        for name in ('Uppercase', 'under_score', '', 'x' * 65):
            self.change_json(manifest, lambda data: data.update(name=name))
            with self.assertRaisesRegex(ValueError, 'manifest name'):
                validate_upload(output)

    def test_duplicate_skill_name_and_xml_description_are_rejected(self):
        output = self.upload()
        skill = output / 'skills/cleannetwork/SKILL.md'
        original = skill.read_text()
        for change in (original.replace('name: cleannetwork', 'name: ioscleannetwork', 1),
                       original.replace('description: ', 'description: <example> ', 1)):
            skill.write_text(change)
            with self.assertRaisesRegex(ValueError, 'skill name/description'):
                validate_upload(output)

    def test_changed_or_missing_pinned_files_are_rejected(self):
        output = self.upload()
        config = output / 'skills/ioscleannetwork/assets/UserExample/Package.swift'
        original = config.read_bytes()
        config.write_bytes(original + b'\n// unexpected change\n')
        with self.assertRaisesRegex(ValueError, 'differs from pinned source'):
            validate_upload(output)
        config.write_bytes(original)
        config.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            validate_upload(output)

    def test_canonical_drift_and_future_pins_need_review(self):
        fixture = self.plugin / SWIFT_FIXTURE
        fixture.write_bytes(fixture.read_bytes() + b'\n// drift\n')
        with self.assertRaisesRegex(ValueError, 'Canonical skill differs'):
            create_upload(self.plugin, self.destination)
        self.assertFalse(self.destination.exists())
        self.change_json(self.plugin / SOURCE_LOCK,
                         lambda lock: lock['sources'][0].update(commit='0' * 40))
        with self.assertRaisesRegex(ValueError, 'Unreviewed source pin'):
            create_upload(self.plugin, self.destination)

    def test_swift_link_edit_requires_exactly_one_expected_link(self):
        guide = self.plugin / SWIFT_GUIDE
        original = guide.read_bytes()
        for content in (original.replace(SWIFT_LINK, b'no link'), original + b'\n' + SWIFT_LINK):
            with self.subTest(count=content.count(SWIFT_LINK)):
                guide.write_bytes(content)
                self.change_json(self.plugin / SOURCE_LOCK,
                                 lambda lock: lock['sources'][0]['files']['references/integration.md'].update(
                                     sha256=hashlib.sha256(content).hexdigest()))
                with self.assertRaisesRegex(ValueError, 'exactly one reviewed Swift fixture link'):
                    create_upload(self.plugin, self.destination)
                self.assertFalse(self.destination.exists())

    def test_tampered_mapping_or_rewritten_guide_is_rejected(self):
        output = self.upload()
        layout = output / LAYOUT
        original = layout.read_bytes()
        for key, value in (('output', 'elsewhere'), ('source_sha256', '0' * 64), ('output_sha256', '0' * 64)):
            self.change_json(layout, lambda data: data['transformations'][0].update({key: value}))
            with self.assertRaisesRegex(ValueError, 'layout provenance'):
                validate_upload(output)
            layout.write_bytes(original)
        guide = output / SWIFT_GUIDE
        guide.write_bytes(guide.read_bytes() + b'\nUnrecorded editorial change.\n')
        with self.assertRaisesRegex(ValueError, 'differs from pinned source'):
            validate_upload(output)

    def test_broken_and_escaping_links_are_rejected(self):
        output = self.upload()
        router = output / 'skills/cleannetwork/SKILL.md'
        original = router.read_text()
        outside = self.root / 'outside.md'
        outside.write_text('outside')
        for link in ('missing.md', '../../../outside.md', '%2e%2e/%2e%2e/%2e%2e/outside.md'):
            router.write_text(original + f'\n[bad]({link})\n')
            with self.assertRaisesRegex(ValueError, 'Broken or external'):
                validate_upload(output)

    def test_existing_and_overlapping_destinations_are_not_modified(self):
        self.destination.mkdir()
        marker = self.destination / 'keep'
        marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            create_upload(self.plugin, self.destination)
        self.assertEqual('keep', marker.read_text())
        before = inventory(self.plugin)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            create_upload(self.plugin, self.plugin / 'upload')
        self.assertEqual(before, inventory(self.plugin))


if __name__ == '__main__':
    unittest.main()
