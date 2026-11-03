"""Validate the portable skill and build two source-only download packages.

Copyright (c) 2026 Leon. Licensed under MIT.
Uses Python's standard library only; never invokes image/video models.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'image-story-short'
REFS = ['capability-and-handoff.md', 'art-direction.md', 'story-and-shots.md',
        'transition-design.md', 'delivery-templates.md', 'review-and-repair.md']


def verify(root=ROOT):
    root = Path(root).resolve()
    skill = root / 'skills' / 'image-story-short'
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must contain a semantic version such as 1.3.0')
    for required in ['LICENSE', 'NOTICE', 'README.md', 'RELEASE_NOTES.md']:
        if not (root / required).is_file():
            raise ValueError(f'Missing {required}')
    for required in ['LICENSE', 'NOTICE', 'SKILL.md', 'agents/openai.yaml']:
        if not (skill / required).is_file():
            raise ValueError(f'Missing skill file: {required}')
    for filename in REFS:
        if not (skill / 'references' / filename).is_file():
            raise ValueError(f'Missing skill reference: {filename}')
    for path in [root / 'LICENSE', skill / 'LICENSE']:
        license_text = path.read_text(encoding='utf-8')
        if not license_text.startswith('MIT License\n') or 'Copyright (c) 2026 Leon' not in license_text:
            raise ValueError(f'Unexpected license: {path.name}')

    markdown_files = list((root / 'docs').glob('*.md')) + list(skill.rglob('*.md')) + [root / 'README.md']
    link_count = 0
    for path in markdown_files:
        text = path.read_text(encoding='utf-8')
        if '\ufffd' in text or re.search(r'\bTODO\b|\[TODO', text):
            raise ValueError(f'Encoding or unfinished scaffold: {path.relative_to(root)}')
        if re.search(r'(?:C:[\\/](?:Users|Windows)|zhuangzisheng@)', text, re.I):
            raise ValueError(f'Local/private data in publication: {path.relative_to(root)}')
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if target.startswith(('https://', 'http://')):
                continue
            filename, marker, fragment = target.partition('#')
            resolved = (path.parent / filename).resolve() if filename else path.resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                raise ValueError(f'Broken file reference in {path.name}: {target}')
            if marker:
                ids = re.findall(r'<a\s+id="([^"]+)"\s*>', resolved.read_text(encoding='utf-8'))
                if fragment not in ids:
                    raise ValueError(f'Broken anchor in {path.name}: {target}')
            link_count += 1

    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    front, body = text.split('---', 2)[1:]
    if not re.search(r'^name: image-story-short$', front, re.M) or not re.search(r'^license: MIT$', front, re.M):
        raise ValueError('Skill identity or license is missing')
    def anchor(match):
        label, filename = match.groups()
        if filename not in REFS:
            raise ValueError(f'Unregistered skill reference: {filename}')
        return f'[{label}](#{PurePosixPath(filename).stem})'
    expected = re.sub(r'\[([^\]]+)\]\(references/([^)]+)\)', anchor, body.strip())
    master = (root / 'docs' / '01_通用主指令.md').read_text(encoding='utf-8')
    if expected not in master:
        raise ValueError('Standalone instructions differ from SKILL.md')
    for filename in REFS:
        if (skill / 'references' / filename).read_text(encoding='utf-8').strip() not in master:
            raise ValueError(f'Standalone instructions omit {filename}')

    examples = (root / 'docs' / '04_跨风格演示.md').read_text(encoding='utf-8')
    for part in re.split(r'^## [ABC]：', examples, flags=re.M)[1:]:
        cursor = 0
        for a, b in re.findall(r'\| (\d+)—(\d+)秒 \|', part):
            start, end = int(a), int(b)
            if start != cursor or end <= start:
                raise ValueError('Example timeline contains a gap or overlap')
            cursor = end
        if not 0 < cursor < 40:
            raise ValueError('Example timeline is not shorter than 40 seconds')
    print(json.dumps({'version': version, 'markdown_files': len(markdown_files),
                      'internal_links_checked': link_count, 'status': 'PASS'}, ensure_ascii=False))
    return version


def write_zip(destination, entries):
    entries = list(entries)
    expected = {name for _, name in entries}
    if len(expected) != len(entries):
        raise ValueError('Duplicate archive entries')
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as z:
        z.comment = b'Copyright (c) 2026 Leon. MIT License. Third-party attribution retained.'
        for path, name in entries:
            z.write(path, name)
    with zipfile.ZipFile(destination) as z:
        if z.testzip() is not None or set(z.namelist()) != expected:
            raise ValueError('Archive failed integrity verification')
        for path, name in entries:
            if z.read(name) != path.read_bytes():
                raise ValueError(f'Archive content mismatch: {name}')


def build():
    version = verify()
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    write_zip(dist / 'image-story-short.zip',
              ((p, (Path('image-story-short') / p.relative_to(SKILL)).as_posix())
               for p in sorted(SKILL.rglob('*')) if p.is_file()))
    excluded = {'.git', 'dist', '__pycache__'}
    entries = []
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if path.is_file() and not (set(relative.parts) & excluded) and path.suffix != '.pyc':
            entries.append((path, (Path('image-story-workflow-' + version) / relative).as_posix()))
    write_zip(dist / 'image-story-workflow.zip', entries)
    sums = []
    for name in ['image-story-short.zip', 'image-story-workflow.zip']:
        sums.append(hashlib.sha256((dist / name).read_bytes()).hexdigest() + '  ' + name)
    (dist / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    print('Built skill ZIP, complete workflow ZIP, and SHA256SUMS.txt')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    verify() if args.check else build()
