"""Promote the verified wheel without rebuilding; record release identity in Git."""
import json
import os
import subprocess
from pathlib import Path

python = '.venv/bin/python'
subprocess.run([python, 'scripts/deploy.py', 'production', 'deploy'], check=True)
manifest = json.loads(Path('dist/manifest.json').read_text())
try:
    subprocess.run([python, 'scripts/smoke.py', 'http://127.0.0.1:8102', manifest['version']], check=True)
except subprocess.CalledProcessError:
    state = json.loads((Path(os.environ['TASKFLOW_RUNTIME']) / 'production.json').read_text())
    if state.get('previous'):
        subprocess.run([python, 'scripts/deploy.py', 'production', 'rollback'], check=True)
    raise
subprocess.run(['git', 'tag', '-a', 'release/' + manifest['version'], '-m',
                'Verified production release ' + manifest['sha256']], check=True)
Path('reports/release.json').write_text(json.dumps(manifest, indent=2))
print('Verified promotion and annotated release tag: release/' + manifest['version'])
