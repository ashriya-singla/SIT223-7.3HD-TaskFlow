"""Start monitoring idempotently and prove a real firing/resolved webhook incident."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(os.environ['TASKFLOW_RUNTIME'])
root.mkdir(parents=True, exist_ok=True)
python = str(Path('.venv/bin/python').resolve())


def get(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def service(name, command, cwd=None):
    pidfile = root / (name + '.pid')
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), 0)
            return
        except ProcessLookupError:
            pass
    log = (root / (name + '.log')).open('ab')
    process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=log,
                               start_new_session=True, env=os.environ.copy())
    log.close()
    pidfile.write_text(str(process.pid))


service('inbox', [python, str(Path('scripts/inbox.py').resolve())])
service('alertmanager', [os.environ['ALERTMANAGER_BIN'], '--config.file=alertmanager.yml',
        '--web.external-url=http://localhost:9093', '--storage.path=' + str(root / 'alertmanager'), '--web.listen-address=127.0.0.1:9093'],
        str(Path('monitoring').resolve()))
service('prometheus', [os.environ['PROMETHEUS_BIN'], '--config.file=prometheus.yml',
        '--web.external-url=http://localhost:9090', '--storage.tsdb.path=' + str(root / 'prometheus'), '--web.listen-address=127.0.0.1:9090'],
        str(Path('monitoring').resolve()))


def wait(predicate, label, seconds=60):
    for _ in range(seconds):
        try:
            if predicate():
                return
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(1)
    raise RuntimeError('Timed out waiting for ' + label)


def query(expression):
    import urllib.parse
    return get('http://127.0.0.1:9090/api/v1/query?query=' + urllib.parse.quote(expression))['data']['result']


wait(lambda: any(row['value'][1] == '1' for row in query('up{job="taskflow-production"}')),
     'healthy production scrape')
feed = root / 'alerts.jsonl'
start_line = len(feed.read_text().splitlines()) if feed.exists() else 0
subprocess.run([python, 'scripts/deploy.py', 'production', 'stop'], check=True)
try:
    def incident(status):
        lines = feed.read_text().splitlines()[start_line:] if feed.exists() else []
        return any(json.loads(line).get('status') == status and any(
            a['labels']['alertname'] == 'TaskFlowUnavailable' for a in json.loads(line)['alerts'])
            for line in lines)
    wait(lambda: incident('firing'), 'real outage alert notification')
    firing = get('http://127.0.0.1:9090/api/v1/alerts')
    Path('reports/monitoring-firing.json').write_text(json.dumps(firing, indent=2))
finally:
    subprocess.run([python, 'scripts/deploy.py', 'production', 'start'], check=True)
wait(lambda: incident('resolved'), 'recovery notification')
lines = feed.read_text().splitlines()[start_line:]
Path('reports/incident-webhooks.json').write_text(json.dumps([json.loads(line) for line in lines], indent=2))
Path('reports/monitoring-healthy.json').write_text(json.dumps(query('up{job="taskflow-production"}'), indent=2))
print('PASS: production outage detected; firing and resolved notifications delivered to local team inbox')
