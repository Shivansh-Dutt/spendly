import math
import os
import sqlite3
from datetime import date

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    delete_expense as remove_expense,
    get_category_totals,
    get_expense_by_id,
    get_expense_stats,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    get_user_profile,
    init_db,
    seed_db,
    update_expense,
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# ---- Profile ----

FILTER_RANGE_ERROR = "Start date must be on or before end date."
FILTER_FORMAT_ERROR = "Enter dates as YYYY-MM-DD."


def _parse_date_filter(args):
    """Return (date_from, date_to, error). On any error the filter is dropped."""
    date_from = args.get("date_from", "").strip()
    date_to = args.get("date_to", "").strip()
    try:
        parsed_from = date.fromisoformat(date_from) if date_from else None
        parsed_to = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        return "", "", FILTER_FORMAT_ERROR
    if parsed_from and parsed_to and parsed_from > parsed_to:
        return "", "", FILTER_RANGE_ERROR
    return date_from, date_to, None


# --- BEGIN transactions section (subagent 1) ---
def _profile_transactions(user_id, date_from, date_to):
    return get_recent_expenses(user_id, date_from=date_from, date_to=date_to)
# --- END transactions section ---


# --- BEGIN stats section (subagent 2) ---
def _profile_stats(user_id, date_from, date_to):
    return get_expense_stats(user_id, date_from=date_from, date_to=date_to)
# --- END stats section ---


# --- BEGIN categories section (subagent 3) ---
def _profile_categories(user_id, date_from, date_to):
    return get_category_totals(user_id, date_from=date_from, date_to=date_to)
# --- END categories section ---


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))
    user = get_user_profile(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    date_from, date_to, filter_error = _parse_date_filter(request.args)
    return render_template(
        "profile.html",
        user=user,
        stats=_profile_stats(user_id, date_from, date_to),
        transactions=_profile_transactions(user_id, date_from, date_to),
        categories=_profile_categories(user_id, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        filter_error=filter_error,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


# ---- Expenses ----

DESCRIPTION_MAX_LENGTH = 200
MAX_AMOUNT = 10_000_000
MIN_EXPENSE_DATE = date(2000, 1, 1)
EXPENSE_FIELDS = ("amount", "category", "date", "description")


def _validate_expense_form(form):
    """Return (clean_values, error). clean_values is None when error is set."""
    raw_amount = form.get("amount", "").strip()
    category = form.get("category", "")
    raw_date = form.get("date", "").strip()
    description = form.get("description", "").strip()

    try:
        amount = round(float(raw_amount), 2)
    except ValueError:
        return None, "Enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be greater than zero."
    if amount > MAX_AMOUNT:
        return None, "Amount is too large."

    if category not in CATEGORIES:
        return None, "Choose a category from the list."

    try:
        expense_date = date.fromisoformat(raw_date)
    except ValueError:
        return None, "Enter the date as YYYY-MM-DD."
    if expense_date < MIN_EXPENSE_DATE:
        return None, f"Date must be on or after {MIN_EXPENSE_DATE.isoformat()}."
    if expense_date > date.today():
        return None, "Date cannot be in the future."

    if len(description) > DESCRIPTION_MAX_LENGTH:
        return None, (
            f"Description must be {DESCRIPTION_MAX_LENGTH} characters or fewer."
        )

    return {
        "amount": amount,
        "category": category,
        "date": expense_date.isoformat(),
        "description": description or None,
    }, None


def _render_expense_form(
    form, error=None, status=200, template="add_expense.html", **context
):
    return (
        render_template(
            template,
            categories=CATEGORIES,
            description_max_length=DESCRIPTION_MAX_LENGTH,
            error=error,
            form=form,
            **context,
        ),
        status,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if request.method == "GET":
        form = dict.fromkeys(EXPENSE_FIELDS, "")
        form["date"] = date.today().isoformat()
        return _render_expense_form(form)

    clean, error = _validate_expense_form(request.form)
    if error is not None:
        form = {key: request.form.get(key, "") for key in EXPENSE_FIELDS}
        return _render_expense_form(form, error, 400)

    try:
        create_expense(
            user_id,
            clean["amount"],
            clean["category"],
            clean["date"],
            clean["description"],
        )
    except sqlite3.IntegrityError:
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — implemented in later steps                     #
# ------------------------------------------------------------------ #


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        form = {
            "amount": f"{expense['amount']:.2f}",
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }
        return _render_expense_form(
            form, template="edit_expense.html", expense_id=id
        )

    clean, error = _validate_expense_form(request.form)
    if error is not None:
        form = {key: request.form.get(key, "") for key in EXPENSE_FIELDS}
        return _render_expense_form(
            form, error, 400, template="edit_expense.html", expense_id=id
        )

    if not update_expense(
        id,
        user_id,
        clean["amount"],
        clean["category"],
        clean["date"],
        clean["description"],
    ):
        abort(404)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "POST":
        if not remove_expense(id, user_id):
            abort(404)
        return redirect(url_for("profile"))

    return render_template("delete_expense.html", expense_id=id, expense=expense)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
