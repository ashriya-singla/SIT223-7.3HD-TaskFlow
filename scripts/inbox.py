"""Local team alert receiver with a browser-visible incident feed (no external messaging)."""
import json
import os
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root = Path(os.environ['TASKFLOW_RUNTIME'])
feed = root / 'alerts.jsonl'


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/alerts':
            self.send_error(404)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if length > 65536:
            self.send_error(413)
            return
        data = json.loads(self.rfile.read(length))
        data['received_at'] = datetime.now(UTC).isoformat()
        with feed.open('a') as stream:
            stream.write(json.dumps(data) + '\n')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'accepted')

    def do_GET(self):
        data = [json.loads(line) for line in feed.read_text().splitlines()] if feed.exists() else []
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data[-20:], indent=2).encode())


ThreadingHTTPServer(('127.0.0.1', 9094), Handler).serve_forever()
