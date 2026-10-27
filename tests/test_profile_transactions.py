import re

import pytest

import database.db as db


@pytest.fixture(autouse=True)
def _db(temp_db):
    pass


def _demo_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


def _add_expense(user_id, amount, category, date, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


def test_demo_user_has_eight_rows():
    assert len(db.get_recent_expenses(_demo_id())) == 8


def test_newest_first():
    rows = db.get_recent_expenses(_demo_id())
    conn = db.get_db()
    try:
        dates = [
            r["date"]
            for r in conn.execute(
                "SELECT date FROM expenses WHERE user_id = ? "
                "ORDER BY date DESC, id DESC",
                (_demo_id(),),
            )
        ]
    finally:
        conn.close()
    assert [r["date"] for r in rows] == [db._format_expense_date(d) for d in dates]


def test_limit_respected():
    assert len(db.get_recent_expenses(_demo_id(), limit=3)) == 3


def test_row_shape_and_date_format():
    row = db.get_recent_expenses(_demo_id())[0]
    assert set(row) == {"date", "description", "category", "amount"}
    assert re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{4}", row["date"])


def test_none_description_becomes_empty_string():
    uid = db.create_user("Null Desc", "nd@example.com", "pw12345")
    _add_expense(uid, 5.0, "Food", "2026-01-02", None)
    assert db.get_recent_expenses(uid)[0]["description"] == ""
    assert db.get_recent_expenses(uid)[0]["date"] == "02 Jan 2026"


def test_other_users_expenses_excluded():
    uid = db.create_user("Other", "other@example.com", "pw12345")
    _add_expense(uid, 99.0, "Misc", "2030-01-01", "secret")
    other_rows = db.get_recent_expenses(uid)
    assert [r["description"] for r in other_rows] == ["secret"]
    demo_rows = db.get_recent_expenses(_demo_id())
    assert len(demo_rows) == 8
    assert all(r["description"] != "secret" for r in demo_rows)
