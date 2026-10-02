"""Unit and database-backed API integration tests."""

import pytest
from werkzeug.security import generate_password_hash

from taskflow import create_app
from taskflow.domain import validate_task


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "PASSWORD_HASH": generate_password_hash("testing-password"),
            "DATABASE": str(tmp_path / "tasks.sqlite"),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authorised(client):
    response = client.post("/login", json={"password": "testing-password"})
    return client, {"X-CSRF-Token": response.json["csrf"]}


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"title": " "},
        {"title": 3},
        {"title": "x" * 121},
        {"title": "ok", "status": "wrong"},
        {"title": "ok", "priority": []},
        {"title": "ok", "id": 1},
    ],
)
def test_invalid_tasks(data):
    with pytest.raises(ValueError):
        validate_task(data)


def test_partial_empty():
    with pytest.raises(ValueError):
        validate_task({}, partial=True)


def test_defaults():
    assert validate_task({"title": "  Read  "}) == {
        "title": "Read",
        "status": "todo",
        "priority": "medium",
    }


def test_required_secrets(tmp_path):
    with pytest.raises(RuntimeError):
        create_app({"SECRET_KEY": None, "DATABASE": str(tmp_path / "x")})


def test_public_endpoints(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").json["status"] == "healthy"
    assert b"taskflow_requests_total" in client.get("/metrics").data
    assert client.get("/missing").status_code == 404


@pytest.mark.parametrize("password", ["wrong", None, 1])
def test_login_denied(client, password):
    assert client.post("/login", json={"password": password}).status_code == 401


def test_bad_login_body(client):
    assert client.post("/login", json=[]).status_code == 401


def test_authentication_and_csrf(client, authorised):
    other = client.application.test_client()
    assert other.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "test"}).status_code == 403


def test_lifecycle(authorised):
    client, headers = authorised
    response = client.post(
        "/api/tasks", json={"title": "Ship release", "priority": "high"}, headers=headers
    )
    assert response.status_code == 201
    task_id = response.json["id"]
    assert len(client.get("/api/tasks").json["tasks"]) == 1
    assert client.get("/api/tasks?q=absent").json["tasks"] == []
    assert (
        client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=headers).json[
            "status"
        ]
        == "done"
    )
    assert client.get("/api/summary").json == {"done": 1, "doing": 0, "todo": 0}
    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == 204
    assert client.get("/api/tasks").json["tasks"] == []
    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == 404
    assert (
        client.patch(f"/api/tasks/{task_id}", json={"title": "x"}, headers=headers).status_code
        == 404
    )
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.get("/api/tasks").status_code == 401


def test_validation_responses(authorised):
    client, headers = authorised
    assert client.post("/api/tasks", json={}, headers=headers).status_code == 400
    assert client.patch("/api/tasks/1", json={}, headers=headers).status_code == 400


def test_sql_payload_is_data(authorised):
    client, headers = authorised
    title = "'); DROP TABLE tasks; --"
    assert client.post("/api/tasks", json={"title": title}, headers=headers).status_code == 201
    assert client.get("/api/tasks").json["tasks"][0]["title"] == title


def test_persistence_and_headers(app, authorised):
    client, headers = authorised
    client.post("/api/tasks", json={"title": "Persist"}, headers=headers)
    second = app.test_client()
    second_headers = {
        "X-CSRF-Token": second.post("/login", json={"password": "testing-password"}).json["csrf"]
    }
    assert second.get("/api/tasks").json["tasks"][0]["title"] == "Persist"
    response = second.post("/api/logout", headers=second_headers)
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
