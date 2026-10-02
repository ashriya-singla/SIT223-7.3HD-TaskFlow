"""Verify deployed HTTP authentication, persistence, CRUD, metrics and release identity."""
import http.cookiejar
import json
import os
import sys
import urllib.request
import uuid

base, expected = sys.argv[1:3]
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path, method='GET', data=None, csrf=''):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(base + path, data=body, method=method,
        headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
    with client.open(request, timeout=5) as response:
        raw = response.read()
        return json.loads(raw) if raw and path != '/metrics' else raw.decode()


assert call('/health')['version'] == expected
csrf = call('/login', 'POST', {'password': os.environ['TASKFLOW_DEMO_PASSWORD']})['csrf']
title = 'pipeline-smoke-' + uuid.uuid4().hex
created = call('/api/tasks', 'POST', {'title': title, 'priority': 'high'}, csrf)
try:
    assert any(row['id'] == created['id'] for row in call('/api/tasks')['tasks'])
    assert call('/api/tasks/' + str(created['id']), 'PATCH', {'status': 'done'}, csrf)['status'] == 'done'
    assert call('/api/summary')['done'] >= 1
    assert 'taskflow_requests_total' in call('/metrics')
finally:
    call('/api/tasks/' + str(created['id']), 'DELETE', csrf=csrf)
print('PASS: live HTTP CRUD, authentication, metrics and immutable version ' + expected)
