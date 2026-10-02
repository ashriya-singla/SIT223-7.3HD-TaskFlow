"""TaskFlow application factory with isolated storage and request metrics."""

import os
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from flask import Flask, g, jsonify, request, session
from prometheus_client import CollectorRegistry, Counter, Histogram

from .routes import register_routes


def create_app(config=None):
    """Create an application; secrets must be supplied by the deployment environment."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("TASKFLOW_SECRET"),
        PASSWORD_HASH=os.environ.get("TASKFLOW_PASSWORD_HASH"),
        DATABASE=os.environ.get("TASKFLOW_DATABASE", "taskflow.sqlite"),
        VERSION=os.environ.get("TASKFLOW_VERSION", "development"),
        ENVIRONMENT=os.environ.get("TASKFLOW_ENV", "local"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=os.environ.get("TASKFLOW_HTTPS") == "1",
        MAX_CONTENT_LENGTH=8192,
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"] or not app.config["PASSWORD_HASH"]:
        raise RuntimeError("TASKFLOW_SECRET and TASKFLOW_PASSWORD_HASH are required")
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(app.config["DATABASE"])) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL, priority TEXT NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
    registry = CollectorRegistry()
    count = Counter(
        "taskflow_requests", "HTTP requests", ["method", "route", "status"], registry=registry
    )
    duration = Histogram("taskflow_request_seconds", "Request latency", registry=registry)

    def database():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=5)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_database(_error):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    @app.before_request
    def authorise():
        g.start = time.monotonic()
        if request.path.startswith("/api/") and not session.get("authenticated"):
            return jsonify(error="Authentication required"), 401
        if request.path.startswith("/api/") and request.method in {"POST", "PATCH", "DELETE"}:
            expected = session.get("csrf", "")
            if not expected or not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), expected
            ):
                return jsonify(error="Invalid CSRF token"), 403
        return None

    @app.after_request
    def response_headers(response):
        route = request.url_rule.rule if request.url_rule else "unmatched"
        count.labels(request.method, route, str(response.status_code)).inc()
        duration.observe(time.monotonic() - g.start)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
                "Referrer-Policy": "same-origin",
                "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            }
        )
        return response

    register_routes(app, database, registry)
    return app
