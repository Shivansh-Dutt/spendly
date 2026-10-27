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
def _use_temp_db(temp_db):
    pass


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
    assert tbody.count("<tr>") >= 3


def test_profile_transaction_content(client):
    login(client)
    body = client.get("/profile").data
    assert b"Electricity bill" in body
    assert b"badge--bills" in body
    assert "₹120.00".encode() in body


def test_profile_category_breakdown(client):
    login(client)
    body = client.get("/profile").data
    assert body.count(b"<progress") >= 3
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


def test_profile_new_user_empty_state(client):
    db.create_user("Asha Rao", "asha@example.com", "password123")
    client.post("/login", data={"email": "asha@example.com", "password": "password123"})
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.data
    assert b"Asha Rao" in body
    assert b"Demo User" not in body
    assert b"No transactions yet" in body
    assert "₹0.00".encode() in body


def test_profile_shows_own_name_not_demo(client):
    db.create_user("Asha Rao", "asha@example.com", "password123")
    client.post("/login", data={"email": "asha@example.com", "password": "password123"})
    body = client.get("/profile").data
    assert b"asha@example.com" in body
    assert b"AR" in body


def test_profile_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_profile_isolates_users(client):
    user_id = db.create_user("Asha Rao", "asha@example.com", "password123")
    conn = db.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, 5.00, "Food", "2026-10-01", "Chai"),
    )
    conn.commit()
    conn.close()

    login(client)
    assert b"Chai" not in client.get("/profile").data

    client.get("/logout")
    client.post("/login", data={"email": "asha@example.com", "password": "password123"})
    body = client.get("/profile").data
    assert b"Chai" in body
    assert b"Electricity bill" not in body


# ---- Date filter ----

ASHA_EMAIL = "asha-filter@example.com"


def _login_user_with_expenses(client, rows):
    user_id = db.create_user("Asha Rao", ASHA_EMAIL, "password123")
    conn = db.get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, *row) for row in rows],
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/login", data={"email": ASHA_EMAIL, "password": "password123"})
    return user_id


FILTER_ROWS = [
    (10.0, "Food", "2026-01-05", "Jan A"),
    (20.0, "Transport", "2026-01-15", "Jan B"),
    (40.0, "Bills", "2026-02-10", "Feb A"),
]


def test_profile_filter_form_is_present(client):
    login(client)
    body = client.get("/profile").data
    assert b'name="date_from"' in body
    assert b'name="date_to"' in body
    assert b"Apply" in body
    assert b"Clear" in body


def test_filter_both_bounds_inclusive(client):
    _login_user_with_expenses(client, FILTER_ROWS)
    body = client.get("/profile?date_from=2026-01-05&date_to=2026-01-15").data.decode()
    assert "₹30.00" in body
    assert "Jan A" in body and "Jan B" in body
    assert "Feb A" not in body
    assert 'value="2026-01-05"' in body and 'value="2026-01-15"' in body


def test_filter_only_date_from(client):
    _login_user_with_expenses(client, FILTER_ROWS)
    body = client.get("/profile?date_from=2026-01-15").data.decode()
    assert "Jan B" in body and "Feb A" in body
    assert "Jan A" not in body


def test_filter_only_date_to(client):
    _login_user_with_expenses(client, FILTER_ROWS)
    body = client.get("/profile?date_to=2026-01-15").data.decode()
    assert "Jan A" in body and "Jan B" in body
    assert "Feb A" not in body


def test_filter_top_category_follows_range(client):
    _login_user_with_expenses(client, FILTER_ROWS)
    stats = db.get_expense_stats(
        db.get_user_by_email(ASHA_EMAIL)["id"], date_from="2026-01-01", date_to="2026-01-31"
    )
    assert stats["top_category"] == "Transport"
    assert stats["transaction_count"] == 2


def test_filter_empty_range(client):
    _login_user_with_expenses(client, FILTER_ROWS)
    response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
    body = response.data.decode()
    assert response.status_code == 200
    assert "₹0.00" in body
    assert "No transactions in this date range" in body
    assert "—" in body


@pytest.mark.parametrize(
    "query",
    [
        "date_from=banana",
        "date_to=2026-13-45",
        "date_from=' OR 1=1 --",
        "date_from=2026-12-01&date_to=2026-01-01",
    ],
)
def test_filter_invalid_input_shows_error_and_unfiltered_data(client, query):
    _login_user_with_expenses(client, FILTER_ROWS)
    response = client.get("/profile?" + query)
    body = response.data.decode()
    assert response.status_code == 200
    assert 'role="alert"' in body
    assert "₹70.00" in body


def test_filter_is_scoped_to_logged_in_user(client):
    login(client)
    client.get("/logout")
    _login_user_with_expenses(client, FILTER_ROWS)
    body = client.get("/profile?date_from=2026-01-01&date_to=2026-12-31").data.decode()
    assert "₹70.00" in body
    assert "Electricity bill" not in body
    assert "₹348.69" not in body


def test_filter_requires_login(client):
    response = client.get("/profile?date_from=2026-01-01")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
