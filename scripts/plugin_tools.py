"""Shared, dependency-free integrity and archive helpers."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / 'plugins/cleannetwork'
SKILLS = {'cleannetwork', 'ioscleannetwork', 'androidcleannetwork'}
EXCLUDED = {'.git', '.build', '.swiftpm', '.gradle', '.kotlin', 'build',
            '__pycache__', '.DS_Store', 'local.properties', '.idea', 'Package.resolved'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def safe_relative(value):
    path = PurePosixPath(value)
    if not value or not path.parts or path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe relative path: {value!r}')
    return path


def files_under(root):
    if root.is_symlink():
        raise ValueError('Package root cannot be a symlink')
    result = {}
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if file.is_symlink():
            raise ValueError(f'Symlink is not portable: {relative}')
        if any(part in EXCLUDED for part in relative.parts) or file.suffix == '.iml':
            raise ValueError(f'Generated or local file in package: {relative}')
        if file.is_file():
            result[relative.as_posix()] = file
    return result


def inventory(root):
    return {name: {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'executable': bool(path.stat().st_mode & 0o111)}
            for name, path in files_under(root).items()}


def validate(root=ROOT):
    plugin = root / 'plugins/cleannetwork'
    manifest = read_json(plugin / 'plugin.json')
    if manifest['name'] != 'cleannetwork' or not re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']):
        raise ValueError('Plugin name/version is invalid')
    if manifest.get('license') != 'MIT' or (plugin / 'LICENSE').read_bytes() != (root / 'LICENSE').read_bytes():
        raise ValueError('Bundled license mismatch')
    overlay = manifest['extensions']['com.openai']
    if overlay['onboardingSkill'] != './skills/cleannetwork/SKILL.md':
        raise ValueError('Unexpected onboarding entrypoint')
    if any(key in overlay for key in ('apps', 'hooks', 'mcpServers')):
        raise ValueError('This plugin should contain instructions only')
    interface = overlay['interface']
    for field, limit in (('displayName', 30), ('shortDescription', 30),
                         ('longDescription', 4000), ('developerName', 80)):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f'Invalid public listing field: {field}')
    for field in ('logo', 'composerIcon'):
        if interface.get(field) != './assets/icon.png':
            raise ValueError(f'Missing public listing icon: {field}')
    icon = (plugin / 'assets/icon.png').read_bytes()
    if (len(icon) < 33 or icon[:8] != b'\x89PNG\r\n\x1a\n' or icon[12:16] != b'IHDR'
            or struct.unpack('>II', icon[16:24]) != (512, 512) or len(icon) > 2_000_000):
        raise ValueError('Public listing icon must be a 512px PNG under 2 MB')
    marketplace = read_json(root / '.agents/plugins/marketplace.json')
    if marketplace['name'] != 'cleannetwork-tools' or len(marketplace['plugins']) != 1:
        raise ValueError('Unexpected marketplace identity/content')
    entry = marketplace['plugins'][0]
    if entry['name'] != manifest['name'] or entry['source'] != {'source': 'local', 'path': './plugins/cleannetwork'}:
        raise ValueError('Marketplace does not point at the packaged plugin')
    if entry['policy'] != {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}:
        raise ValueError('Unexpected installation policy')
    if entry['category'] != 'Productivity':
        raise ValueError('Unexpected marketplace category')
    claude = read_json(plugin / '.claude-plugin/plugin.json')
    shared_fields = ('name', 'version', 'description', 'author', 'license', 'keywords', 'homepage', 'repository')
    expected_claude = {key: manifest[key] for key in shared_fields}
    expected_claude.update(displayName=interface['displayName'], icon='./assets/icon.png')
    if claude != expected_claude:
        raise ValueError('Claude manifest differs from the shared plugin metadata')
    claude_marketplace = read_json(root / '.claude-plugin/marketplace.json')
    if (claude_marketplace['name'] != marketplace['name']
            or claude_marketplace['owner'] != manifest['author']
            or len(claude_marketplace['plugins']) != 1):
        raise ValueError('Unexpected Claude marketplace identity/content')
    claude_entry = claude_marketplace['plugins'][0]
    if (claude_entry['name'] != manifest['name']
            or claude_entry['source'] != './plugins/cleannetwork'):
        raise ValueError('Claude marketplace does not point at the packaged plugin')
    if {p.name for p in (plugin / 'skills').iterdir()} != SKILLS:
        raise ValueError('Expected exactly the router and two SDK skills')
    lock = read_json(plugin / 'sources.lock.json')
    if lock['format'] != 1 or {s['skill'] for s in lock['sources']} != SKILLS - {'cleannetwork'} or len(lock['sources']) != 2:
        raise ValueError('Invalid source lock')
    for source in lock['sources']:
        if not re.fullmatch(r'[0-9a-f]{40}', source['commit']):
            raise ValueError('Source must be pinned to a complete Git commit')
        skill = plugin / 'skills' / source['skill']
        if not source['files'] or inventory(skill) != source['files']:
            raise ValueError(f'Bundled skill differs from pinned source: {source["skill"]}')
        if f'api-baseline: "{source["tag"]}"' not in (skill / 'SKILL.md').read_text():
            raise ValueError('Skill baseline differs from source version')
        if source['path'] != f'skills/{source["skill"]}':
            raise ValueError('Unexpected upstream skill path')
        safe_relative(source['path'])
    files = files_under(plugin)
    for skill in SKILLS:
        text = (plugin / 'skills' / skill / 'SKILL.md').read_text()
        if not text.startswith('---\n') or f'\nname: {skill}\n' not in text or '\ndescription: ' not in text:
            raise ValueError(f'Invalid skill frontmatter: {skill}')
        if not (plugin / 'skills' / skill / 'agents/openai.yaml').is_file():
            raise ValueError(f'Missing UI metadata: {skill}')
    for relative, path in files.items():
        if path.suffix != '.md':
            continue
        text = path.read_text()
        if re.search(r'/(?:Users|home)/[^/\s]+/', text):
            raise ValueError(f'Nonportable content: {relative}')
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if link.startswith(('http://', 'https://', '#', 'mailto:')):
                continue
            target = (path.parent / link.split('#', 1)[0]).resolve()
            if not target.is_relative_to(plugin.resolve()) or not target.exists():
                raise ValueError(f'Broken or external bundled reference: {relative}: {link}')
    if not (plugin / 'skills/androidcleannetwork/assets/UserExample/gradlew').stat().st_mode & 0o111:
        raise ValueError('Gradle wrapper must be executable')
    return manifest


def write_zip(path, files):
    """Stable bytes: sorted entries, fixed timestamps and preserved execute bits."""
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in sorted(files.items()):
            safe_relative(name)
            if source.is_symlink():
                raise ValueError(f'Cannot package a symlink: {source}')
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def extract_zip(archive, destination):
    """Extract regular files only; reject traversal, symlinks and duplicates."""
    with zipfile.ZipFile(archive) as source:
        seen = set()
        for info in source.infolist():
            relative = safe_relative(info.filename)
            if str(relative) in seen or info.is_dir() or ((info.external_attr >> 16) & 0o170000) not in (0, 0o100000):
                raise ValueError('ZIP has duplicate, directory or non-regular entries')
            seen.add(str(relative))
            file = destination / relative
            if file.is_symlink() or file.exists():
                raise ValueError(f'ZIP would overwrite a file: {relative}')
            if not file.resolve().is_relative_to(destination.resolve()):
                raise ValueError('ZIP target escapes destination')
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(source.read(info))
            file.chmod(0o755 if (info.external_attr >> 16) & 0o111 else 0o644)
