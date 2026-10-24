import inspect
import re
import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash

import database.db as db


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    return path


@pytest.fixture
def conn(db_path):
    db.init_db()
    connection = db.get_db()
    yield connection
    connection.close()


def test_schema(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"users", "expenses"} <= tables

    users = {r["name"]: r for r in conn.execute("PRAGMA table_info(users)")}
    assert set(users) == {"id", "name", "email", "password_hash", "created_at"}
    assert users["id"]["pk"] == 1
    for col in ("name", "email", "password_hash"):
        assert users[col]["notnull"] == 1

    expenses = {r["name"]: r for r in conn.execute("PRAGMA table_info(expenses)")}
    assert set(expenses) == {
        "id", "user_id", "amount", "category", "date", "description", "created_at",
    }
    assert expenses["id"]["pk"] == 1
    for col in ("user_id", "amount", "category", "date"):
        assert expenses[col]["notnull"] == 1
    assert expenses["description"]["notnull"] == 0


def test_init_and_seed_are_idempotent(db_path):
    db.init_db()
    db.init_db()
    db.seed_db()
    db.seed_db()

    conn = db.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 8
    finally:
        conn.close()


def test_seed_content(db_path):
    db.init_db()
    db.seed_db()

    conn = db.get_db()
    try:
        user = conn.execute("SELECT * FROM users").fetchone()
        assert user["email"] == "demo@spendly.com"
        assert user["password_hash"] != "demo123"
        assert check_password_hash(user["password_hash"], "demo123")

        expenses = conn.execute("SELECT * FROM expenses").fetchall()
        assert len(expenses) == 8
        assert {e["category"] for e in expenses} == set(db.CATEGORIES)
        assert all(e["user_id"] == user["id"] for e in expenses)

        month = date.today().strftime("%Y-%m")
        assert all(e["date"].startswith(month) for e in expenses)
        assert all(e["date"] <= date.today().isoformat() for e in expenses)
    finally:
        conn.close()


def test_duplicate_email_rejected(conn):
    sql = "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)"
    conn.execute(sql, ("A", "dup@example.com", "x"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, ("B", "dup@example.com", "y"))


def test_foreign_key_enforced(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) "
            "VALUES (?, ?, ?, ?)",
            (9999, 1.0, "Food", "2026-01-01"),
        )


def test_row_factory_allows_name_access(conn):
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Row", "row@example.com", "x"),
    )
    row = conn.execute("SELECT email FROM users").fetchone()
    assert row["email"] == "row@example.com"


def test_parameterized_queries(conn):
    evil = "Robert'); DROP TABLE users;--"
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (evil, "bobby@example.com", "x"),
    )
    assert conn.execute("SELECT name FROM users").fetchone()["name"] == evil

    assert not re.search(r"execute(many)?\(\s*f[\"']", inspect.getsource(db))
