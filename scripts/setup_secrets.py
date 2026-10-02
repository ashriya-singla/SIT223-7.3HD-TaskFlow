"""Generate private local assessment credentials outside the repository."""
import secrets
import shlex
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
if (root / 'ci.env').exists():
    raise SystemExit('Existing credentials preserved; choose a new runtime directory')
password = secrets.token_urlsafe(18)
(root / 'ci.env').write_text('export TASKFLOW_DEMO_PASSWORD=' + shlex.quote(password) + '\n'
    + 'export TASKFLOW_PASSWORD_HASH=' + shlex.quote(generate_password_hash(password)) + '\n')
(root / 'workspace-password.txt').write_text(password + '\n')
for name in ['ci.env', 'workspace-password.txt']:
    (root / name).chmod(0o600)
print('Private credentials created in runtime directory; no secrets printed')
