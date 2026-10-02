pipeline {
    agent any
    options {
        timestamps()
        disableConcurrentBuilds()
        skipStagesAfterUnstable()
        timeout(time: 15, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
    }
    triggers { pollSCM('H/2 * * * *') }
    environment {
        PYTHON = '/opt/homebrew/bin/python3'
        TASKFLOW_RUNTIME = '/Users/siddhantsharma/Documents/Codex/2026-10-03/files-mentioned-by-the-user-7/work/runtime'
        WHEELHOUSE = '/Users/siddhantsharma/Documents/Codex/2026-10-03/files-mentioned-by-the-user-7/work/wheelhouse'
        PROMETHEUS_BIN = '/Users/siddhantsharma/Documents/Codex/2026-10-03/files-mentioned-by-the-user-7/work/prometheus-3.15.0.darwin-arm64/prometheus'
        ALERTMANAGER_BIN = '/Users/siddhantsharma/Documents/Codex/2026-10-03/files-mentioned-by-the-user-7/work/alertmanager-0.34.1.darwin-arm64/alertmanager'
        JENKINS_NODE_COOKIE = 'taskflow-services'
    }
    stages {
        stage('Build') {
            steps {
                sh 'sh scripts/bootstrap.sh'
                sh '.venv/bin/python scripts/build.py'
                archiveArtifacts artifacts: 'dist/*', fingerprint: true
            }
        }
        stage('Test') {
            steps {
                sh '.venv/bin/python -m pytest --cov --cov-report=xml --cov-report=html:reports/coverage --junitxml=reports/junit.xml'
            }
            post { always { junit 'reports/junit.xml' } }
        }
        stage('Code Quality') {
            steps {
                sh '.venv/bin/ruff check taskflow tests'
                sh '.venv/bin/ruff format --check taskflow tests'
                sh '.venv/bin/python scripts/quality.py'
                archiveArtifacts artifacts: 'reports/quality.json,coverage.xml', fingerprint: true
            }
        }
        stage('Security') {
            steps {
                sh '.venv/bin/bandit -r taskflow -f json -o reports/bandit.json'
                sh '.venv/bin/pip-audit -r requirements-runtime.lock --no-deps --disable-pip --format json --output reports/dependency-audit.json'
            }
            post { always { archiveArtifacts artifacts: 'reports/*audit*.json,reports/bandit.json', allowEmptyArchive: true } }
        }
        stage('Deploy') {
            steps {
                sh '''set +x
                    . "$TASKFLOW_RUNTIME/ci.env"
                    .venv/bin/python scripts/deploy.py staging deploy
                    VERSION=$(.venv/bin/python -c 'import json;print(json.load(open("dist/manifest.json"))["version"])')
                    .venv/bin/python scripts/smoke.py http://127.0.0.1:8101 "$VERSION"
                '''
            }
        }
        stage('Release') {
            steps {
                sh '''set +x
                    . "$TASKFLOW_RUNTIME/ci.env"
                    .venv/bin/python scripts/release.py
                '''
                archiveArtifacts artifacts: 'reports/release.json', fingerprint: true
            }
        }
        stage('Monitoring') {
            steps {
                sh '''set +x
                    . "$TASKFLOW_RUNTIME/ci.env"
                    .venv/bin/python scripts/monitor.py
                '''
                archiveArtifacts artifacts: 'reports/monitoring-*.json,reports/incident-webhooks.json', fingerprint: true
            }
        }
    }
    post {
        always { archiveArtifacts artifacts: 'reports/**/*.json,reports/coverage/**', allowEmptyArchive: true }
        success { echo 'All seven gates passed. Production is healthy; incident firing and recovery delivery verified.' }
        failure { echo 'Pipeline failed. Inspect the failed stage and archived evidence before retrying.' }
    }
}
