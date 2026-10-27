import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_db,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


DUPLICATE_EMAIL_ERROR = "An account with that email already exists"


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not name:
        error = "Name is required."
    elif not email:
        error = "Email is required."
    elif "@" not in email:
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif get_user_by_email(email) is not None:
        error = DUPLICATE_EMAIL_ERROR

    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = DUPLICATE_EMAIL_ERROR

    if error is not None:
        return (
            render_template("register.html", error=error, name=name, email=email),
            400,
        )
    return redirect(url_for("login"))


LOGIN_ERROR = "Invalid email or password."


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    return {"current_user": get_user_by_id(user_id) if user_id else None}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error=LOGIN_ERROR, email=email), 400

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# ---- Profile (hardcoded, Step 4) ----

PROFILE_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "initials": "DU",
    "member_since": "January 2026",
}

PROFILE_STATS = {
    "total_spent": 348.69,
    "transaction_count": 8,
    "top_category": "Bills",
}

PROFILE_TRANSACTIONS = [
    {"date": "22 Oct 2026", "description": "Groceries", "category": "Food", "amount": 27.30},
    {"date": "18 Oct 2026", "description": "Misc", "category": "Other", "amount": 10.00},
    {"date": "14 Oct 2026", "description": "New shoes", "category": "Shopping", "amount": 79.90},
    {"date": "10 Oct 2026", "description": "Movie ticket", "category": "Entertainment", "amount": 18.99},
    {"date": "08 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 45.00},
    {"date": "05 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 120.00},
    {"date": "03 Oct 2026", "description": "Metro card top-up", "category": "Transport", "amount": 35.00},
    {"date": "01 Oct 2026", "description": "Lunch", "category": "Food", "amount": 12.50},
]

PROFILE_CATEGORIES = [
    {"name": "Bills", "amount": 120.00},
    {"name": "Shopping", "amount": 79.90},
    {"name": "Health", "amount": 45.00},
    {"name": "Food", "amount": 39.80},
    {"name": "Transport", "amount": 35.00},
    {"name": "Entertainment", "amount": 18.99},
    {"name": "Other", "amount": 10.00},
]


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template(
        "profile.html",
        user=PROFILE_USER,
        stats=PROFILE_STATS,
        transactions=PROFILE_TRANSACTIONS,
        categories=PROFILE_CATEGORIES,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
