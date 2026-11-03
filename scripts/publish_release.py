"""Publish already-validated source packages using GitHub Actions' repository token.

Copyright (c) 2026 Leon. MIT License.
No user image/video generation credentials are used.
"""
from pathlib import Path
import json
import os
import re
import subprocess
from build_release import verify

root = Path(__file__).resolve().parents[1]
version = verify(root)
tag = 'v' + version
sha = os.environ['GITHUB_SHA']
repo = os.environ['GH_REPO']
if not re.fullmatch(r'[0-9a-f]{40}', sha) or not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
    raise ValueError('Invalid GitHub Actions context')

def gh(*args, check=True):
    return subprocess.run(['gh', *args], cwd=root, text=True, capture_output=True, check=check)

view = gh('release', 'view', tag, '--json', 'isDraft,assets,url', check=False)
if view.returncode == 0:
    data = json.loads(view.stdout)
    if not data['isDraft']:
        required = {'image-story-short.zip', 'image-story-workflow.zip', 'SHA256SUMS.txt'}
        if not required.issubset({a['name'] for a in data['assets']}):
            raise RuntimeError('Published release is incomplete; review it before changing assets')
        print('Existing published version retained: ' + data['url'])
        raise SystemExit(0)
else:
    gh('release', 'create', tag, '--draft', '--target', sha,
       '--title', 'v' + version + ' · 图片故事短片', '--notes-file', 'RELEASE_NOTES.md')

gh('release', 'upload', tag, 'dist/image-story-short.zip',
   'dist/image-story-workflow.zip', 'dist/SHA256SUMS.txt', '--clobber')
gh('release', 'edit', tag, '--draft=false', '--latest')
print(gh('release', 'view', tag, '--json', 'url', '--jq', '.url').stdout.strip())
