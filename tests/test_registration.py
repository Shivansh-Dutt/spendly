import sqlite3

import pytest
from werkzeug.security import check_password_hash

import app as app_module
import database.db as db

DUPLICATE_MESSAGE = "An account with that email already exists"


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


@pytest.fixture
def client():
    return app_module.app.test_client()


def count_users():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def register(client, name="Alice", email="alice@example.com", password="password1"):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password}
    )


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"<form" in response.data


def test_valid_registration_redirects_to_login(client):
    before = count_users()
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert count_users() == before + 1


def test_password_is_hashed(client):
    register(client, password="password1")
    user = db.get_user_by_email("alice@example.com")
    assert user["password_hash"] != "password1"
    assert check_password_hash(user["password_hash"], "password1")


def test_email_is_stripped_and_lowercased(client):
    register(client, email="  Foo@Bar.COM ")
    assert db.get_user_by_email("foo@bar.com") is not None


@pytest.mark.parametrize("email", ["demo@spendly.com", "DEMO@spendly.com"])
def test_duplicate_email_rejected(client, email):
    before = count_users()
    response = register(client, email=email)
    assert response.status_code == 400
    assert DUPLICATE_MESSAGE.encode() in response.data
    assert count_users() == before


def test_password_length_boundary(client):
    before = count_users()
    response = register(client, password="1234567")
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data
    assert count_users() == before

    assert register(client, password="12345678").status_code == 302


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "", "email": "a@b.com", "password": "password1"},
        {"name": "   ", "email": "a@b.com", "password": "password1"},
        {"name": "Al", "email": "", "password": "password1"},
        {"name": "Al", "email": "no-at-sign", "password": "password1"},
        {},
    ],
)
def test_invalid_input_rejected(client, fields):
    before = count_users()
    response = client.post("/register", data=fields)
    assert response.status_code == 400
    assert count_users() == before


def test_error_repopulates_fields_but_not_password(client):
    response = register(client, name='"><script>x', email="a@b.com", password="short")
    html = response.get_data(as_text=True)
    assert 'value="a@b.com"' in html
    assert "<script>x" not in html
    assert "&#34;&gt;&lt;script&gt;x" in html
    assert "short" not in html.replace("at least 8 characters", "")


def test_form_action_uses_url_for(client):
    html = client.get("/register").get_data(as_text=True)
    with app_module.app.test_request_context():
        expected = app_module.url_for("register")
    assert f'action="{expected}"' in html


def test_demo_user_unaffected(client):
    original = db.get_user_by_email("demo@spendly.com")["password_hash"]
    register(client)
    assert db.get_user_by_email("demo@spendly.com")["password_hash"] == original


def test_create_user_duplicate_raises_integrity_error():
    db.create_user("A", "dup@example.com", "password1")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("B", "dup@example.com", "password1")


def test_race_on_duplicate_returns_400(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_user_by_email", lambda email: None)
    before = count_users()
    response = register(client, email="demo@spendly.com")
    assert response.status_code == 400
    assert DUPLICATE_MESSAGE.encode() in response.data
    assert count_users() == before


def test_get_user_by_email():
    assert db.get_user_by_email("nobody@example.com") is None
    assert db.get_user_by_email("demo@spendly.com") is not None
