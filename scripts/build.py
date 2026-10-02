"""Build once and identify the deployment artifact by source revision and SHA-256."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

subprocess.run(['.venv/bin/python', '-m', 'build', '--wheel', '--no-isolation'], check=True)
wheel = next(Path('dist').glob('*.whl'))
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
version = '1.0.' + os.environ.get('BUILD_NUMBER', '0') + '+' + commit[:12]
manifest = {'version': version, 'commit': commit, 'wheel': str(wheel),
            'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}
Path('dist/manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
