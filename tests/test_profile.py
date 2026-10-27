import re
from pathlib import Path

import pytest

import app as app_module
import database.db as db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
ROOT = Path(__file__).resolve().parent.parent
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


@pytest.fixture
def client():
    return app_module.app.test_client()


def login(client):
    return client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_redirect_lands_on_login_page(client):
    response = client.get("/profile", follow_redirects=True)
    assert response.status_code == 200
    assert b'action="/login"' in response.data


def test_profile_returns_200_when_logged_in(client):
    login(client)
    assert client.get("/profile").status_code == 200


def test_profile_shows_user_info(client):
    login(client)
    body = client.get("/profile").data
    assert b"Demo User" in body
    assert b"demo@spendly.com" in body
    assert b"DU" in body
    assert b"Member since" in body


def test_profile_shows_summary_stats(client):
    login(client)
    body = client.get("/profile").data
    assert "₹348.69".encode() in body
    assert b"Bills" in body
    assert body.count(b'class="stat-card"') == 3


def test_profile_transaction_table_rows(client):
    login(client)
    body = client.get("/profile").data.decode()
    tbody = body.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count("<tr>") == len(app_module.PROFILE_TRANSACTIONS) >= 3


def test_profile_transaction_content(client):
    login(client)
    body = client.get("/profile").data
    assert b"Electricity bill" in body
    assert b"badge--bills" in body
    assert "₹120.00".encode() in body


def test_profile_category_breakdown(client):
    login(client)
    body = client.get("/profile").data
    assert body.count(b"<progress") == len(app_module.PROFILE_CATEGORIES) >= 3
    assert b"breakdown-bar--shopping" in body


def test_profile_navbar_shows_logged_in_state(client):
    login(client)
    body = client.get("/profile").data
    assert b"Sign out" in body
    assert b'href="/logout"' in body


def test_profile_loads_page_stylesheet(client):
    login(client)
    assert b"css/profile.css" in client.get("/profile").data


@pytest.mark.parametrize("path", ["templates/profile.html", "static/css/profile.css"])
def test_profile_files_have_no_hex_colours(path):
    assert not HEX_COLOUR.search((ROOT / path).read_text(encoding="utf-8"))


def test_profile_template_has_no_inline_styles():
    source = (ROOT / "templates/profile.html").read_text(encoding="utf-8")
    assert "style=" not in source
    assert "<style" not in source
