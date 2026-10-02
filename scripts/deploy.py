"""Local infrastructure as code: isolated releases, database, health gate and rollback."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('environment', choices=['staging', 'production'])
parser.add_argument('action', choices=['deploy', 'stop', 'start', 'rollback'])
args = parser.parse_args()
root = Path(os.environ['TASKFLOW_RUNTIME']).resolve()
root.mkdir(parents=True, exist_ok=True)
state_path = root / (args.environment + '.json')
state = json.loads(state_path.read_text()) if state_path.exists() else {}
port = 8101 if args.environment == 'staging' else 8102


def stop():
    if state.get('pid'):
        try:
            os.killpg(state['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1)


def start(release):
    env = os.environ.copy()
    env.update(TASKFLOW_DATABASE=str(root / (args.environment + '.sqlite')),
               TASKFLOW_ENV=args.environment, TASKFLOW_VERSION=release['version'])
    secret_file = root / (args.environment + '-secret')
    if not secret_file.exists():
        import secrets
        secret_file.write_text(secrets.token_hex(48))
        secret_file.chmod(0o600)
    env['TASKFLOW_SECRET'] = secret_file.read_text()
    log = (root / (args.environment + '.log')).open('ab')
    process = subprocess.Popen([
        str(Path(release['path']) / 'venv/bin/gunicorn'), '--bind', f'127.0.0.1:{port}',
        '--workers', '1', '--threads', '4', '--access-logfile', '-', 'taskflow:create_app()'],
        env=env, cwd=root, stdout=log, stderr=log, start_new_session=True)
    log.close()
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError('Service exited; inspect environment log')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                if json.load(response)['version'] == release['version']:
                    return process.pid
        except (OSError, ValueError):
            time.sleep(0.5)
    os.killpg(process.pid, signal.SIGTERM)
    raise RuntimeError('Health gate timed out')


if args.action == 'stop':
    stop()
elif args.action == 'start':
    state['pid'] = start(state['current'])
    state_path.write_text(json.dumps(state, indent=2))
else:
    previous = state.get('current')
    if args.action == 'rollback':
        candidate = state['previous']
    else:
        manifest = json.loads(Path('dist/manifest.json').read_text())
        wheel = Path(manifest['wheel']).resolve()
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest['sha256']:
            raise RuntimeError('Artifact integrity check failed')
        release_dir = root / 'releases' / args.environment / manifest['version']
        release_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([os.environ['PYTHON'], '-m', 'venv', str(release_dir / 'venv')], check=True)
        install = [str(release_dir / 'venv/bin/python'), '-m', 'pip', 'install']
        if os.environ.get('WHEELHOUSE'):
            install += ['--no-index', '--find-links', os.environ['WHEELHOUSE']]
        subprocess.run(install + [str(wheel), '-r', 'requirements-runtime.lock'], check=True)
        candidate = {'path': str(release_dir), **manifest}
    stop()
    try:
        state['pid'] = start(candidate)
        state.update(current=candidate, previous=previous)
        state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        if previous:
            state['pid'] = start(previous)
            state_path.write_text(json.dumps(state, indent=2))
        raise
    print(json.dumps({'environment': args.environment, 'port': port, 'version': candidate['version']}))
