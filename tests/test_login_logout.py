import pytest

import app as app_module
import database.db as db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
ERROR_MESSAGE = b"Invalid email or password."


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


@pytest.fixture
def client():
    return app_module.app.test_client()


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'action="/login"' in response.data


def test_login_success_sets_session_and_redirects(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert session_user_id(client) is not None


def test_login_normalises_email(client):
    response = login(client, email="  Demo@Spendly.COM ")
    assert response.status_code == 302
    assert session_user_id(client) is not None


def test_login_wrong_password(client):
    response = login(client, password="wrongpass")
    assert response.status_code == 400
    assert ERROR_MESSAGE in response.data
    assert session_user_id(client) is None


def test_unknown_email_gives_same_error(client):
    response = login(client, email="nobody@example.com")
    assert response.status_code == 400
    assert ERROR_MESSAGE in response.data
    assert session_user_id(client) is None


@pytest.mark.parametrize(
    "email, password",
    [("", DEMO_PASSWORD), (DEMO_EMAIL, ""), ("", "")],
)
def test_login_empty_fields(client, email, password):
    response = login(client, email=email, password=password)
    assert response.status_code == 400
    assert ERROR_MESSAGE in response.data
    assert session_user_id(client) is None


def test_error_keeps_email_and_not_password(client):
    response = login(client, password="wrongpass")
    assert f'value="{DEMO_EMAIL}"'.encode() in response.data
    assert b"wrongpass" not in response.data


def test_get_login_when_logged_in_redirects(client):
    login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_logout_clears_session(client):
    login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert session_user_id(client) is None


def test_logout_when_logged_out(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_navbar_reflects_session(client):
    logged_out = client.get("/").data
    assert b"Sign in" in logged_out
    assert b"Get started" in logged_out
    assert b"Sign out" not in logged_out

    login(client)
    logged_in = client.get("/").data
    assert b"Demo User" in logged_in
    assert b"Sign out" in logged_in
    assert b"Get started" not in logged_in

    client.get("/logout")
    after_logout = client.get("/").data
    assert b"Sign in" in after_logout
    assert b"Get started" in after_logout
    assert b"Sign out" not in after_logout


def test_registered_user_can_log_in(client):
    db.create_user("Alice", "alice@example.com", "password1")
    response = login(client, email="alice@example.com", password="password1")
    assert response.status_code == 302
    assert session_user_id(client) is not None
