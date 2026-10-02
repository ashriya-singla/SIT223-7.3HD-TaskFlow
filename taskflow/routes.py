"""HTTP endpoints and database-backed task operations."""

import secrets

from flask import jsonify, render_template, request, session
from prometheus_client import generate_latest
from werkzeug.security import check_password_hash

from .domain import STATUSES, validate_task


def register_routes(app, database, registry):
    @app.get("/")
    def index():
        return render_template(
            "index.html", version=app.config["VERSION"], env=app.config["ENVIRONMENT"]
        )

    @app.post("/login")
    def login():
        data = request.get_json(silent=True) or {}
        password = data.get("password", "") if isinstance(data, dict) else ""
        if not isinstance(password, str) or not check_password_hash(
            app.config["PASSWORD_HASH"], password
        ):
            return jsonify(error="Invalid credentials"), 401
        session.clear()
        session.update(authenticated=True, csrf=secrets.token_hex(32))
        return jsonify(csrf=session["csrf"])

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(message="Signed out")

    @app.get("/health")
    def health():
        database().execute("SELECT 1").fetchone()
        return jsonify(
            status="healthy", version=app.config["VERSION"], environment=app.config["ENVIRONMENT"]
        )

    @app.get("/metrics")
    def metrics():
        return generate_latest(registry), 200, {"Content-Type": "text/plain; version=0.0.4"}

    @app.get("/api/tasks")
    def list_tasks():
        search = request.args.get("q", "")[:120]
        rows = database().execute(
            "SELECT * FROM tasks WHERE title LIKE ? ORDER BY id DESC", (f"%{search}%",)
        )
        return jsonify(tasks=[dict(row) for row in rows])

    @app.post("/api/tasks")
    def add_task():
        try:
            task = validate_task(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        connection = database()
        cursor = connection.execute(
            "INSERT INTO tasks (title,status,priority) VALUES (?,?,?)",
            (task["title"], task["status"], task["priority"]),
        )
        connection.commit()
        return jsonify(id=cursor.lastrowid, **task), 201

    @app.patch("/api/tasks/<int:task_id>")
    def update_task(task_id):
        try:
            changes = validate_task(request.get_json(silent=True), partial=True)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        connection = database()
        row = connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return jsonify(error="Task not found"), 404
        task = dict(row) | changes
        connection.execute(
            "UPDATE tasks SET title=?,status=?,priority=? WHERE id=?",
            (task["title"], task["status"], task["priority"], task_id),
        )
        connection.commit()
        return jsonify(task)

    @app.delete("/api/tasks/<int:task_id>")
    def delete_task(task_id):
        connection = database()
        cursor = connection.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        connection.commit()
        if cursor.rowcount == 0:
            return jsonify(error="Task not found"), 404
        return "", 204

    @app.get("/api/summary")
    def summary():
        rows = database().execute("SELECT status,COUNT(*) AS count FROM tasks GROUP BY status")
        totals = dict.fromkeys(sorted(STATUSES), 0)
        totals.update({row["status"]: row["count"] for row in rows})
        return jsonify(totals)
