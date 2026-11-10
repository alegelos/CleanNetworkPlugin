"""A bounded, auditable projection for Claude account-upload path limits.

The canonical skills and their source lock stay unchanged. Only this staging
copy renames one Swift fixture, updates its link, and flattens Kotlin source
paths. A source-pin update requires reviewing these transformations again.

Limits: https://platform.claude.com/docs/en/manage-claude/plugins-api#upload-requirements
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit

from plugin_tools import files_under, inventory, read_json, safe_relative

MAX_FILES = 5000
# Decimal MB is conservative for both interpretations of the documented limit.
MAX_BYTES = 200_000_000
MAX_DEPTH = 12
MAX_PATH = 472
MAX_COMPONENT = 255
MANIFEST = '.claude-plugin/plugin.json'
LAYOUT = 'upload-layout.json'
SOURCE_LOCK = 'sources.lock.json'
REVIEWED_SOURCES = {
    'ioscleannetwork': ('1.0.4', 'cbcb6d0ecdbd85210db368e9872cc296fb3531e4'),
    'androidcleannetwork': ('1.0.1', '1d363a279ff60d3c30939b95428cec77c7f001c4'),
}
SWIFT_FIXTURE = ('skills/ioscleannetwork/assets/UserExample/Tests/'
                 'UserExampleTests/Support/UserAPISetup+Fixtures.swift')
UPLOAD_FIXTURE = SWIFT_FIXTURE.replace('UserAPISetup+Fixtures.swift',
                                       'UserAPISetupFixtures.swift')
SWIFT_GUIDE = 'skills/ioscleannetwork/references/integration.md'
SWIFT_LINK = (b'[UserAPISetup+Fixtures.swift](../assets/UserExample/Tests/'
              b'UserExampleTests/Support/UserAPISetup+Fixtures.swift)')
UPLOAD_LINK = SWIFT_LINK.replace(b'UserAPISetup+Fixtures.swift',
                                 b'UserAPISetupFixtures.swift')
KOTLIN_SOURCE = re.compile(
    r'(skills/androidcleannetwork/assets/UserExample/(?:user-data|user-domain)/'
    r'src/(?:main|test)/kotlin)/com/example/user/(?:[^/]+/)+([^/]+\.kt)')
DESCRIPTION = ('Distribution-only path adaptation for Claude account uploads. '
               'The source lock describes canonical upstream files; the entries '
               'below record renamed files and the sole Markdown link edit. '
               'Kotlin package declarations and build configuration are unchanged.')


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _files(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Upload source/root must be a regular directory')
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f'Symlink or non-regular upload entry: {path.relative_to(root)}')
    return files_under(root)


def _upload_path(name):
    path = safe_relative(name)
    if not re.fullmatch(r'[A-Za-z0-9 _./(),-]+', name):
        raise ValueError(f'Unsupported upload path characters: {name}')
    if len(path.parts) > MAX_DEPTH:
        raise ValueError(f'Upload path depth exceeds {MAX_DEPTH}: {name}')
    if len(name) > MAX_PATH or any(len(part) > MAX_COMPONENT for part in path.parts):
        raise ValueError(f'Upload path/name length limit exceeded: {name}')
    if path.parts[0] == 'bin':
        raise ValueError('Upload cannot contain a top-level bin directory')
    if path.suffix.lower() == '.zip':
        raise ValueError(f'Upload cannot contain a nested ZIP: {name}')


def _output_path(name):
    if name == SWIFT_FIXTURE:
        return UPLOAD_FIXTURE
    match = KOTLIN_SOURCE.fullmatch(name)
    return f'{match[1]}/{match[2]}' if match else name


def _projection(names):
    """Reject exact, case-insensitive and file/directory destination collisions."""
    outputs = {}
    seen = {}
    for name in sorted(names):
        output = _output_path(name)
        key = output.casefold()
        if key in seen:
            raise ValueError(f'Upload path collision: {seen[key]} and {name} -> {output}')
        outputs[name] = output
        seen[key] = name
    for output in outputs.values():
        if any(parent.as_posix().casefold() in seen
               for parent in PurePosixPath(output).parents if parent != PurePosixPath('.')):
            raise ValueError(f'Upload file/directory collision: {output}')
    return outputs


def _locked_files(lock):
    if not isinstance(lock, dict) or lock.get('format') != 1:
        raise ValueError('Invalid upload source lock')
    sources = lock.get('sources')
    if (not isinstance(sources, list) or len(sources) != len(REVIEWED_SOURCES)
            or any(not isinstance(source, dict) for source in sources)
            or {source.get('skill') for source in sources} != set(REVIEWED_SOURCES)):
        raise ValueError('Unexpected upload source skills')
    result = {}
    for source in sources:
        skill = source['skill']
        if (source.get('tag'), source.get('commit')) != REVIEWED_SOURCES[skill]:
            raise ValueError(f'Unreviewed source pin for Claude upload: {skill}')
        prefix = f'skills/{skill}'
        if source.get('path') != prefix or not isinstance(source.get('files'), dict) or not source['files']:
            raise ValueError(f'Invalid upload source inventory: {skill}')
        for name, entry in source['files'].items():
            relative = safe_relative(name)
            if (relative.as_posix() != name or not isinstance(entry, dict)
                    or set(entry) != {'sha256', 'executable'}
                    or not isinstance(entry['sha256'], str)
                    or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])
                    or type(entry['executable']) is not bool):
                raise ValueError(f'Invalid upload source entry: {name}')
            result[f'{prefix}/{name}'] = entry
    if SWIFT_FIXTURE not in result or SWIFT_GUIDE not in result:
        raise ValueError('Reviewed Swift fixture/link source is missing')
    return result


def _rewrite_guide(data, reverse=False):
    before, after = (UPLOAD_LINK, SWIFT_LINK) if reverse else (SWIFT_LINK, UPLOAD_LINK)
    if data.count(before) != 1 or after in data:
        raise ValueError('Expected exactly one reviewed Swift fixture link')
    return data.replace(before, after, 1)


def _transformation(source, output, entry, data):
    if source == SWIFT_GUIDE:
        reason = 'update-swift-fixture-link'
    elif source == SWIFT_FIXTURE:
        reason = 'rename-swift-fixture'
    else:
        reason = 'flatten-kotlin-source-path'
    return {'source': source, 'output': output, 'reason': reason,
            'source_sha256': entry['sha256'], 'output_sha256': _sha256(data),
            'executable': entry['executable']}


def _layout(version, lock_bytes, transformations):
    return {'format': 1, 'target': 'claude-account-upload',
            'base_plugin_version': version, 'description': DESCRIPTION,
            'source_lock_sha256': _sha256(lock_bytes),
            'omitted': ['plugin.json'], 'transformations': transformations}


def _valid_name(name):
    return (isinstance(name, str) and 1 <= len(name) <= 64
            and all(character == '-' or character.isdigit()
                    or (character.isalpha() and character.islower()) for character in name))


def _manifest(root, files):
    manifests = [name for name in files if PurePosixPath(name).name == 'plugin.json']
    if manifests != [MANIFEST]:
        raise ValueError(f'Upload needs exactly one manifest at {MANIFEST}')
    manifest = read_json(root / MANIFEST)
    if not isinstance(manifest, dict) or not _valid_name(manifest.get('name')):
        raise ValueError('Invalid Claude upload manifest name')
    if not isinstance(manifest.get('version'), str) or not re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']):
        raise ValueError('Invalid Claude upload manifest version')
    for field, limit in (('displayName', 64), ('description', 500)):
        if field in manifest and (not isinstance(manifest[field], str) or len(manifest[field]) > limit):
            raise ValueError(f'Claude upload manifest {field} exceeds its limit')
    return manifest


def _validate_skills(files):
    expected = {f'skills/{name}/SKILL.md': name
                for name in (*REVIEWED_SOURCES, 'cleannetwork')}
    if {name for name in files if PurePosixPath(name).name == 'SKILL.md'} != set(expected):
        raise ValueError('Upload needs exactly the three expected skill entrypoints')
    for path, name in expected.items():
        text = files[path].read_text(encoding='utf-8')
        frontmatter = re.match(r'\A---\n(.*?)\n---(?:\n|\Z)', text, re.S)
        if frontmatter is None:
            raise ValueError(f'Invalid skill frontmatter: {path}')
        fields = frontmatter[1].splitlines()
        names = [line[len('name: '):] for line in fields if line.startswith('name: ')]
        descriptions = [line[len('description: '):] for line in fields if line.startswith('description: ')]
        if (names != [name] or len(descriptions) != 1 or not descriptions[0].strip()
                or re.search(r'<[^>]+>', descriptions[0])):
            raise ValueError(f'Invalid or duplicate skill name/description: {path}')


def _validate_links(root, files):
    for name, path in files.items():
        if path.suffix != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        # The bundled guides use inline links; also check reference definitions.
        links = re.findall(r'\[[^\]\n]*\]\((<[^>\n]+>|[^)\n]+)\)', text)
        links += re.findall(r'(?m)^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)', text)
        for link in links:
            link = link.strip()
            if link.startswith('<') and link.endswith('>'):
                link = link[1:-1]
            else:
                link = re.sub(r'\s+["\'].*["\']$', '', link)
            parsed = urlsplit(link)
            if parsed.scheme in ('http', 'https', 'mailto') or link.startswith('#'):
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            if parsed.scheme or parsed.netloc or not target.is_relative_to(root.resolve()) or not target.exists():
                raise ValueError(f'Broken or external bundled reference: {name}: {link}')


def validate_upload(root: Path):
    """Validate an extracted staging tree and its reversible source provenance.

    Returns its Claude manifest; invalid layouts raise ValueError. Archive
    compression/encryption and compressed size are the ZIP writer's concern.
    """
    root = Path(root)
    files = _files(root)
    for path in root.rglob('*'):
        _upload_path(path.relative_to(root).as_posix())
    if len(files) > MAX_FILES:
        raise ValueError(f'Upload file count exceeds {MAX_FILES}')
    if sum(path.stat().st_size for path in files.values()) > MAX_BYTES:
        raise ValueError(f'Upload uncompressed size exceeds {MAX_BYTES} bytes')
    manifest = _manifest(root, files)
    if SOURCE_LOCK not in files or LAYOUT not in files:
        raise ValueError('Upload is missing its source lock or layout provenance')
    locked = _locked_files(read_json(root / SOURCE_LOCK))
    projection = _projection(locked)
    actual = {name for name in files if any(name.startswith(f'skills/{skill}/')
                                          for skill in REVIEWED_SOURCES)}
    if actual != set(projection.values()):
        raise ValueError('Upload skill inventory differs from the source projection')
    transformations = []
    for source, output in sorted(projection.items()):
        entry = locked[source]
        path = files[output]
        data = path.read_bytes()
        canonical = _rewrite_guide(data, reverse=True) if source == SWIFT_GUIDE else data
        if (_sha256(canonical) != entry['sha256']
                or bool(path.stat().st_mode & 0o111) != entry['executable']):
            raise ValueError(f'Upload differs from pinned source: {source}')
        if source != output or source == SWIFT_GUIDE:
            transformations.append(_transformation(source, output, entry, data))
    expected = _layout(manifest['version'], files[SOURCE_LOCK].read_bytes(), transformations)
    if read_json(root / LAYOUT) != expected:
        raise ValueError('Upload layout provenance does not match the source projection')
    _validate_skills(files)
    _validate_links(root, files)
    return manifest


def create_upload(plugin: Path, destination: Path) -> Path:
    """Create a new validated staging directory without modifying the plugin.

    The destination must not exist or overlap the canonical plugin. Failed
    validation leaves no partial destination. Bytes and modes are preserved
    except for the documented link edit and newly generated layout metadata.
    """
    plugin, destination = Path(plugin), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f'Upload destination already exists: {destination}')
    if (destination.resolve().is_relative_to(plugin.resolve())
            or plugin.resolve().is_relative_to(destination.resolve())):
        raise ValueError('Upload destination must not overlap the canonical plugin')
    files = _files(plugin)
    if LAYOUT in files:
        raise ValueError('Canonical plugin already contains upload layout metadata')
    if 'plugin.json' not in files or MANIFEST not in files or SOURCE_LOCK not in files:
        raise ValueError('Canonical plugin is missing its manifests or source lock')
    projection = _projection(name for name in files if name != 'plugin.json')
    locked = _locked_files(read_json(plugin / SOURCE_LOCK))
    for skill in REVIEWED_SOURCES:
        prefix = f'skills/{skill}/'
        expected = {name[len(prefix):]: entry for name, entry in locked.items() if name.startswith(prefix)}
        if inventory(plugin / 'skills' / skill) != expected:
            raise ValueError(f'Canonical skill differs from pinned source: {skill}')
    manifest = read_json(plugin / MANIFEST)
    shared = read_json(plugin / 'plugin.json')
    if (not isinstance(manifest, dict) or not isinstance(shared, dict)
            or any(manifest.get(field) != shared.get(field) for field in ('name', 'version'))):
        raise ValueError('Canonical plugin and Claude metadata differ')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='claude-upload-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'plugin'
        stage.mkdir()
        transformations = []
        for source, output in sorted(projection.items()):
            target = stage / output
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(files[source], target)
            if source == SWIFT_GUIDE:
                target.write_bytes(_rewrite_guide(files[source].read_bytes()))
            if source != output or source == SWIFT_GUIDE:
                transformations.append(_transformation(source, output, locked[source], target.read_bytes()))
        layout = _layout(manifest.get('version'), files[SOURCE_LOCK].read_bytes(), transformations)
        (stage / LAYOUT).write_text(json.dumps(layout, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        (stage / LAYOUT).chmod(0o644)
        validate_upload(stage)
        if destination.exists() or destination.is_symlink():
            raise ValueError(f'Upload destination already exists: {destination}')
        stage.rename(destination)
    return destination
