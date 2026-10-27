import pytest

import database.db as db


@pytest.fixture(autouse=True)
def _use_temp_db(temp_db):
    pass


def _demo_id():
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
    finally:
        conn.close()
    return row["id"]


def test_demo_has_seven_categories_sorted_desc():
    cats = db.get_category_totals(_demo_id())
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert cats[0]["name"] == "Bills"


def test_demo_amounts_sum():
    cats = db.get_category_totals(_demo_id())
    assert round(sum(c["amount"] for c in cats), 2) == 348.69


def test_new_user_gets_empty_list():
    uid = db.create_user("New User", "new@example.com", "pw12345")
    assert db.get_category_totals(uid) == []


def test_other_users_expenses_excluded():
    uid = db.create_user("Other", "other@example.com", "pw12345")
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, 10.0, "Food", "2026-01-01", "x"),
        )
        conn.commit()
    finally:
        conn.close()
    assert db.get_category_totals(uid) == [{"name": "Food", "amount": 10.0}]
    total = sum(c["amount"] for c in db.get_category_totals(_demo_id()))
    assert round(total, 2) == 348.69


def test_profile_renders_progress_per_category(client, login_demo):
    login_demo()
    html = client.get("/profile").get_data(as_text=True)
    assert html.count("<progress") == 7
    assert "breakdown-bar--bills" in html


def test_new_user_profile_has_no_progress(client):
    db.create_user("Fresh", "fresh@example.com", "pw12345")
    client.post("/login", data={"email": "fresh@example.com", "password": "pw12345"})
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "<progress" not in resp.get_data(as_text=True)
