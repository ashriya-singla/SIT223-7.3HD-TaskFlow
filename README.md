# TaskFlow - SIT223/SIT753 Task 7.3HD

A database-backed task-management web application and seven-stage Jenkins pipeline.
Features: session authentication, task creation/update/deletion, priorities, status tracking,
search, summaries, persistent SQLite storage, HTTP metrics and an incident inbox.

## Verified local stack

Python 3.14.8, Flask 3.1.3, Gunicorn 26.2.0, SQLite, pytest 9.1.1,
Ruff 0.16.10, Radon 6.0.1, Bandit 1.9.4, pip-audit 2.10.1,
Jenkins 2.568.3 / Java 21, Prometheus 3.15.0, Alertmanager 0.34.1.
Exact Python dependency versions are in `requirements-ci.lock` and `requirements-runtime.lock`.

## Pipeline contract

| Stage | Automation and blocking gate | Evidence |
|---|---|---|
| Build | Pinned tooling, wheel, commit/build release ID, SHA-256 | Fingerprinted wheel + manifest |
| Test | Unit and database-backed API integration tests; >=90% combined statement/branch coverage | JUnit + coverage XML/HTML |
| Code Quality | Ruff lint and format; complexity <=15; maintainability >=40 | Versioned gate + JSON/history |
| Security | Bandit source analysis and complete pinned runtime dependency audit; any finding blocks | JSON scan results |
| Deploy | Isolated staging release environment; artifact checksum; health and live CRUD smoke gates | Environment state + console |
| Release | Same verified wheel promoted to production; smoke gate; automatic previous-release recovery | Annotated local Git tag + manifest |
| Monitoring | Real production scrapes; outage/error/latency rules; actual firing + resolved webhooks | Incident and metrics JSON |

The application wheel is built once per run. Staging and production install the same wheel
and retain separate secrets, databases, logs and virtual environments. A failed startup restores
the previous process; a failed production smoke test rolls back the previous release. Release tags
are created in the Jenkins checkout and are not pushed to GitHub because the pipeline has no write
credential. Jenkins archives are the authoritative artifact and release record.

## Clone and configure Jenkins

```sh
git clone https://github.com/ashriya-singla/SIT223-7.3HD-TaskFlow.git
cd SIT223-7.3HD-TaskFlow
```

1. Install Python >=3.11 and Jenkins with Pipeline, Git, JUnit, Timestamper and Pipeline Graph View plugins.
   This demonstration uses macOS ARM64 and Python 3.14. Wheels cached on this laptop target that platform.
2. Download Prometheus and Alertmanager from their official release pages, verifying published SHA-256 sums.
3. Edit the five agent-specific paths in the Jenkinsfile environment block (`PYTHON`, `TASKFLOW_RUNTIME`,
   `WHEELHOUSE`, `PROMETHEUS_BIN`, `ALERTMANAGER_BIN`). Set `WHEELHOUSE` to an empty string to resolve the
   exact lockfile versions from PyPI instead of a local wheel cache. Avoid spaces in executable paths.
4. Create the private runtime directory outside the source repository. Bootstrap a temporary Python environment
   with the pinned dependencies and run `scripts/setup_secrets.py RUNTIME_DIRECTORY`. It writes a random demo
   password and password hash, both with mode 0600. Never upload the runtime directory.
5. Jenkins -> New Item -> Pipeline -> name `SIT223-7.3HD-TaskFlow` -> Pipeline script from SCM -> Git.
   Repository URL: `https://github.com/ashriya-singla/SIT223-7.3HD-TaskFlow.git`; branch: `*/main`;
   script path: `Jenkinsfile`; credentials: none (public read access). Save -> Build Now.
6. After the first run, SCM polling checks for changes every two minutes. Only new source revisions trigger a run.
   Deployment and release have no approval prompts. `disableConcurrentBuilds` serialises this job's releases.

The pipeline needs outbound HTTPS to PyPI/OSV for current vulnerability data. An audit service failure fails
closed. For reproducibility across another Python/OS combination, download compatible wheels for the exact
lockfile versions or use online bootstrap. The Python wheel is portable; tool binary caches are not.

## Local services

- Staging: http://localhost:8101
- Production: http://localhost:8102
- Prometheus: http://localhost:9090 (query `up`, `taskflow_requests_total`, and latency histograms)
- Alertmanager: http://localhost:9093
- Team incident inbox: http://localhost:9194

All listeners bind to loopback. "Production" is a separate local assessment environment, not a public
internet service. HTTP cookies work here; a public deployment requires TLS with `TASKFLOW_HTTPS=1`,
a reverse proxy, login rate limiting, external secret storage and proper multi-user authorisation.
The workspace is intentionally shared; it is not a tenant-isolated service.

The local alert receiver records real Alertmanager webhooks and displays them to the team through an
incident feed. No email/Slack message is sent. For an operational team, configure an approved external
receiver. Only the unavailable-service alert is injected and verified; latency/error alerts are configured.

## Run checks manually

```sh
export PYTHON=python3
sh scripts/bootstrap.sh
.venv/bin/python -m pytest --cov --cov-report=xml --junitxml=reports/junit.xml
.venv/bin/ruff check taskflow tests
.venv/bin/ruff format --check taskflow tests
.venv/bin/python scripts/quality.py
.venv/bin/bandit -r taskflow -f json -o reports/bandit.json
.venv/bin/pip-audit -r requirements-runtime.lock --no-deps --disable-pip --format json --output reports/dependency-audit.json
```

The dependency lock enumerates the complete runtime dependency graph. `--no-deps --disable-pip` avoids
resolving the graph again; it does not skip audit entries. No vulnerability IDs are ignored. The scan
reports known findings at scan time, not a guarantee of vulnerability absence.

## Incident demonstration and recovery

The Monitoring stage starts the three monitoring processes idempotently, verifies `up=1`, stops production,
waits for a real `TaskFlowUnavailable` alert and webhook, restores production in a `finally` block, and
requires a resolved webhook. It saves only newly received incident events for that run.
This intentionally interrupts only the assessment production environment for approximately 15-30 seconds.
The 8-second availability threshold and 2-second scrapes make the demonstration observable; operational
thresholds should be tuned to traffic and outage tolerance.

Manual rollback (load the private environment first):

```sh
set +x
. "$TASKFLOW_RUNTIME/ci.env"
.venv/bin/python scripts/deploy.py production rollback
```

Database files live outside versioned releases, so rollback preserves tasks. This project introduces no
schema migrations; future migrations must be backwards compatible or require a tested database restore.
Rollback protects service availability, not destructive data migrations.

## Submission evidence

Use the successful Jenkins run, its seven green stages, the JUnit result, archived artifacts, running
application, Prometheus alert rules and firing/resolved incident feed. The report must cite actual run
results. Record a <=10-minute walkthrough showing clone/setup, each stage, deployed CRUD and the incident.
Do not replace actual pipeline evidence with a drawn pipeline graphic. The public repository provides
read access to both the marker and unit chair without an invitation.

## References

- Jenkins pipeline syntax: https://www.jenkins.io/doc/book/pipeline/syntax/
- Jenkins tests/artifacts: https://www.jenkins.io/doc/pipeline/tour/tests-and-artifacts/
- Prometheus alert rules: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Alertmanager configuration: https://prometheus.io/docs/alerting/latest/configuration/
- Flask security: https://flask.palletsprojects.com/en/stable/web-security/
- Ruff: https://docs.astral.sh/ruff/
- Radon: https://radon.readthedocs.io/en/latest/intro.html
- Bandit: https://bandit.readthedocs.io/en/latest/
- pip-audit: https://github.com/pypa/pip-audit
