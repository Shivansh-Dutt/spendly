import os
import sqlite3
from datetime import date, datetime

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)

# (category, amount, day of month, description)
SEED_EXPENSES = (
    ("Food", 12.50, 1, "Lunch"),
    ("Transport", 35.00, 3, "Metro card top-up"),
    ("Bills", 120.00, 5, "Electricity bill"),
    ("Health", 45.00, 8, "Pharmacy"),
    ("Entertainment", 18.99, 10, "Movie ticket"),
    ("Shopping", 79.90, 14, "New shoes"),
    ("Other", 10.00, 18, "Misc"),
    ("Food", 27.30, 22, "Groceries"),
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cursor.lastrowid

        today = date.today()
        rows = [
            (
                user_id,
                amount,
                category,
                date(today.year, today.month, min(day, today.day)).isoformat(),
                description,
            )
            for category, amount, day, description in SEED_EXPENSES
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_expense(
    expense_id, user_id, amount, category, expense_date, description
):
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, "
            "description = ? WHERE id = ? AND user_id = ?",
            (amount, category, expense_date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_expense(expense_id, user_id):
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _format_expense_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d %b %Y")


def _format_member_since(created_at):
    return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")


def get_user_profile(user_id):
    user = get_user_by_id(user_id)
    if user is None:
        return None
    initials = "".join(part[0] for part in user["name"].split()[:2]).upper()
    return {
        "name": user["name"],
        "email": user["email"],
        "initials": initials or "?",
        "member_since": _format_member_since(user["created_at"]),
    }


def _date_range_clause(date_from, date_to):
    clause = ""
    params = []
    if date_from:
        clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clause += " AND date <= ?"
        params.append(date_to)
    return clause, params


# --- BEGIN transactions section (subagent 1) ---
def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None):
    range_clause, range_params = _date_range_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + range_clause + " "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *range_params, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "date": _format_expense_date(row["date"]),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]
# --- END transactions section ---


# --- BEGIN stats section (subagent 2) ---
def get_expense_stats(user_id, date_from=None, date_to=None):
    range_clause, range_params = _date_range_clause(date_from, date_to)
    params = (user_id, *range_params)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses "
            "WHERE user_id = ?" + range_clause,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + range_clause + " "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
        ).fetchone()
        return {
            "total_spent": round(float(totals[0]), 2),
            "transaction_count": int(totals[1]),
            "top_category": top[0] if top else "—",
        }
    finally:
        conn.close()
# --- END stats section ---


# --- BEGIN categories section (subagent 3) ---
def get_category_totals(user_id, date_from=None, date_to=None):
    range_clause, range_params = _date_range_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + range_clause + " GROUP BY category "
            "ORDER BY SUM(amount) DESC, category",
            (user_id, *range_params),
        ).fetchall()
    finally:
        conn.close()
    return [{"name": r["category"], "amount": round(r["total"], 2)} for r in rows]
# --- END categories section ---
