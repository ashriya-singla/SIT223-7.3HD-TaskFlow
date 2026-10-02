#!/bin/sh
set -eu
: "${PYTHON:=python3}"
"$PYTHON" -m venv .venv
if [ -n "${WHEELHOUSE:-}" ]; then
  .venv/bin/python -m pip install --no-index --find-links "$WHEELHOUSE" -r requirements-ci.lock
else
  .venv/bin/python -m pip install -r requirements-ci.lock
fi
mkdir -p reports
# Commit tags are local release records; pushing tags needs a separate Git credential.
git config user.name 'TaskFlow CI'
git config user.email 'taskflow-ci@example.invalid'
