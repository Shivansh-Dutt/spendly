import pytest

import database.db as db


@pytest.fixture(autouse=True)
def _use_temp_db(temp_db):
    pass


def _demo_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


def _add_expense(user_id, amount, category):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, category, "2026-01-01"),
        )
        conn.commit()
    finally:
        conn.close()


def test_demo_stats():
    stats = db.get_expense_stats(_demo_id())
    assert stats == {
        "total_spent": 348.69,
        "transaction_count": 8,
        "top_category": "Bills",
    }


def test_new_user_stats_empty():
    uid = db.create_user("New Person", "new@example.com", "password1")
    assert db.get_expense_stats(uid) == {
        "total_spent": 0.0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_other_users_expenses_excluded():
    uid = db.create_user("New Person", "new@example.com", "password1")
    _add_expense(uid, 5.5, "Fun")
    stats = db.get_expense_stats(uid)
    assert stats["total_spent"] == 5.5
    assert stats["transaction_count"] == 1
    assert stats["top_category"] == "Fun"
    assert db.get_expense_stats(_demo_id())["transaction_count"] == 8


def test_top_category_tie_breaks_by_name():
    uid = db.create_user("Tie User", "tie@example.com", "password1")
    _add_expense(uid, 10, "Zed")
    _add_expense(uid, 10, "Alpha")
    assert db.get_expense_stats(uid)["top_category"] == "Alpha"


def test_profile_page_demo_total(client, login_demo):
    login_demo()
    html = client.get("/profile").get_data(as_text=True)
    assert "₹348.69" in html


def test_profile_page_new_user_total(client):
    db.create_user("New Person", "new@example.com", "password1")
    client.post("/login", data={"email": "new@example.com", "password": "password1"})
    html = client.get("/profile").get_data(as_text=True)
    assert "₹0.00" in html
