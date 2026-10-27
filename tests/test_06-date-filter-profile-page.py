"""Tests for the Date Filter for Profile Page feature (spec 06).

Written from .claude/specs/06-date-filter-profile-page.md.
All test data uses fixed dates in 2020 so it never collides with the
relative-to-today seed data (which is removed for the demo user anyway).
"""
import re

import pytest

import database.db as db


# ---------------------------------------------------------------- fixtures

@pytest.fixture(autouse=True)
def _use_temp_db(temp_db):
    """Every test runs against a throwaway, freshly seeded database."""


# (date, category, amount, description)
DEMO_EXPENSES = [
    ("2020-01-01", "Food", 10.00, "alpha-food"),
    ("2020-01-15", "Bills", 100.00, "bravo-bills"),
    ("2020-01-31", "Travel", 20.00, "charlie-travel"),
    ("2020-02-10", "Food", 5.00, "delta-food"),
]
OTHER_EXPENSES = [
    ("2020-01-15", "Shopping", 999.00, "other-secret"),
    ("2020-03-01", "Shopping", 111.00, "other-march"),
]

ALL_MARKERS = [d for _, _, _, d in DEMO_EXPENSES]


def _insert(user_id, rows):
    conn = db.get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amt, cat, dt, desc) for dt, cat, amt, desc in rows],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def demo_id():
    """Demo user id, with the seeded expenses replaced by known 2020 rows."""
    user = db.get_user_by_email("demo@spendly.com")
    conn = db.get_db()
    try:
        conn.execute("DELETE FROM expenses WHERE user_id = ?", (user["id"],))
        conn.commit()
    finally:
        conn.close()
    _insert(user["id"], DEMO_EXPENSES)
    return user["id"]


@pytest.fixture
def other_id(demo_id):
    uid = db.create_user("Other Person", "other@example.com", "otherpass1")
    _insert(uid, OTHER_EXPENSES)
    return uid


@pytest.fixture
def logged_in(client, demo_id):
    resp = client.post(
        "/login", data={"email": "demo@spendly.com", "password": "demo123"}
    )
    assert resp.status_code in (302, 303)
    return client


def _get(client, **params):
    return client.get("/profile", query_string=params)


def _text(resp):
    return resp.get_data(as_text=True)


def _stats(text):
    """Return (total_string, count_string, top_category) from the stat cards."""
    values = re.findall(r'class="stat-value">([^<]*)<', text)
    assert len(values) == 3, f"Expected 3 stat values, got {values}"
    return tuple(v.strip() for v in values)


def _present(text):
    return {m for m in ALL_MARKERS if m in text}


# ------------------------------------------------------------ auth guard

class TestAuthGuard:
    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "2026-01-01"},
            {"date_to": "2026-12-31"},
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
            {"date_from": "banana"},
        ],
    )
    def test_unauthenticated_with_query_params_redirects_to_login(
        self, client, params
    ):
        resp = _get(client, **params)
        assert resp.status_code == 302, "Expected redirect when logged out"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------- no filter / form

class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, logged_in):
        resp = _get(logged_in)
        text = _text(resp)
        assert resp.status_code == 200
        assert _present(text) == set(ALL_MARKERS)
        assert _stats(text) == ("₹135.00", "4", "Bills")

    def test_no_params_uses_recent_transactions_heading(self, logged_in):
        text = _text(_get(logged_in))
        assert "Recent transactions" in text

    def test_no_params_shows_no_error(self, logged_in):
        text = _text(_get(logged_in))
        assert "filter-error" not in text

    def test_blank_params_behave_as_unfiltered(self, logged_in):
        resp = _get(logged_in, date_from="", date_to="")
        text = _text(resp)
        assert resp.status_code == 200
        assert _present(text) == set(ALL_MARKERS)
        assert "Recent transactions" in text
        assert "filter-error" not in text

    def test_seeded_demo_data_unchanged_without_params(self, client):
        """Fresh seed (no test rows): 8 transactions, 348.69, top Bills."""
        client.post(
            "/login", data={"email": "demo@spendly.com", "password": "demo123"}
        )
        text = _text(_get(client))
        assert _stats(text) == ("₹348.69", "8", "Bills")


class TestFilterForm:
    def test_form_has_date_inputs_apply_and_clear(self, logged_in):
        text = _text(_get(logged_in))
        assert re.search(r'<form[^>]*method="get"', text, re.I), "GET form expected"
        assert re.search(r'<input[^>]*type="date"[^>]*name="date_from"', text)
        assert re.search(r'<input[^>]*type="date"[^>]*name="date_to"', text)
        assert "Apply" in text
        assert "Clear" in text

    def test_form_action_points_to_profile(self, logged_in):
        text = _text(_get(logged_in))
        assert re.search(r'<form[^>]*action="/profile"', text)

    def test_clear_link_points_to_unfiltered_profile(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-01"))
        match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*Clear\s*</a>', text)
        assert match, "Clear link not found"
        assert match.group(1) == "/profile"

    def test_following_clear_link_returns_unfiltered(self, logged_in):
        _get(logged_in, date_from="2020-02-01")
        resp = logged_in.get("/profile")
        assert _present(_text(resp)) == set(ALL_MARKERS)

    def test_inputs_prefilled_after_applying_both_dates(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-10", date_to="2020-01-20"))
        assert 'value="2020-01-10"' in text
        assert 'value="2020-01-20"' in text

    def test_inputs_prefilled_with_only_from(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-10"))
        assert 'value="2020-01-10"' in text

    def test_inputs_prefilled_with_only_to(self, logged_in):
        text = _text(_get(logged_in, date_to="2020-01-20"))
        assert 'value="2020-01-20"' in text

    def test_inputs_empty_when_no_filter(self, logged_in):
        text = _text(_get(logged_in))
        assert not re.search(r'value="\d{4}-\d{2}-\d{2}"', text)


# --------------------------------------------------------- happy paths

class TestFiltering:
    def test_both_bounds_limit_transactions(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-10", date_to="2020-01-20"))
        assert _present(text) == {"bravo-bills"}

    def test_both_bounds_update_stats(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        assert _stats(text) == ("₹130.00", "3", "Bills")

    def test_lower_bound_is_inclusive(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-15", date_to="2020-01-20"))
        assert "bravo-bills" in text
        assert "alpha-food" not in text

    def test_upper_bound_is_inclusive(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-10", date_to="2020-01-15"))
        assert "bravo-bills" in text
        assert "charlie-travel" not in text

    def test_same_day_range_returns_that_day(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-31", date_to="2020-01-31"))
        assert _present(text) == {"charlie-travel"}
        assert _stats(text) == ("₹20.00", "1", "Travel")

    def test_only_date_from_returns_on_or_after(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-31"))
        assert _present(text) == {"charlie-travel", "delta-food"}
        assert _stats(text)[1] == "2"

    def test_only_date_to_returns_on_or_before(self, logged_in):
        text = _text(_get(logged_in, date_to="2020-01-15"))
        assert _present(text) == {"alpha-food", "bravo-bills"}
        assert _stats(text)[1] == "2"

    def test_filtered_heading_is_transactions(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        assert "Recent transactions" not in text
        assert re.search(r"<h2[^>]*>\s*Transactions\s*</h2>", text)

    def test_valid_filter_shows_no_error(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        assert "filter-error" not in text

    def test_category_breakdown_reflects_filter(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        breakdown = text.split("Spending by category", 1)[1]
        assert "Food" in breakdown and "Bills" in breakdown and "Travel" in breakdown
        assert "₹10.00" in breakdown  # Food only counts January's 10.00
        assert "₹15.00" not in breakdown  # all-time Food would be 15.00

    def test_category_breakdown_excludes_out_of_range_categories(self, logged_in):
        text = _text(_get(logged_in, date_from="2020-02-01", date_to="2020-02-28"))
        breakdown = text.split("Spending by category", 1)[1]
        assert "Food" in breakdown
        assert "Bills" not in breakdown
        assert "Travel" not in breakdown

    def test_filter_uses_chronological_not_text_order(self, logged_in):
        """Range spanning a month boundary works on ISO dates."""
        text = _text(_get(logged_in, date_from="2020-01-31", date_to="2020-02-10"))
        assert _present(text) == {"charlie-travel", "delta-food"}


# ---------------------------------------------------------- empty range

class TestEmptyRange:
    def test_empty_range_shows_zero_stats(self, logged_in):
        resp = _get(logged_in, date_from="2019-01-01", date_to="2019-12-31")
        assert resp.status_code == 200
        assert _stats(_text(resp)) == ("₹0.00", "0", "—")

    def test_empty_range_shows_empty_state_message(self, logged_in):
        text = _text(_get(logged_in, date_from="2019-01-01", date_to="2019-12-31"))
        assert "No transactions in this date range" in text
        assert "No transactions yet" not in text
        assert _present(text) == set()

    def test_empty_range_with_only_from_in_future(self, logged_in):
        resp = _get(logged_in, date_from="2999-01-01")
        assert resp.status_code == 200
        assert "No transactions in this date range" in _text(resp)

    def test_no_data_without_filter_keeps_original_empty_state(
        self, client, demo_id
    ):
        conn = db.get_db()
        try:
            conn.execute("DELETE FROM expenses WHERE user_id = ?", (demo_id,))
            conn.commit()
        finally:
            conn.close()
        client.post(
            "/login", data={"email": "demo@spendly.com", "password": "demo123"}
        )
        text = _text(_get(client))
        assert "No transactions yet" in text
        assert "No transactions in this date range" not in text


# ------------------------------------------------------ validation errors

INVALID_CASES = [
    pytest.param({"date_from": "banana"}, id="malformed-from"),
    pytest.param({"date_to": "banana"}, id="malformed-to"),
    pytest.param({"date_from": "2020-13-45"}, id="impossible-date"),
    pytest.param({"date_from": "2020-02-30"}, id="nonexistent-day"),
    pytest.param({"date_from": "01/02/2020"}, id="wrong-format"),
    pytest.param(
        {"date_from": "2020-02-01", "date_to": "2020-01-01"}, id="reversed-range"
    ),
    pytest.param({"date_from": "' OR 1=1 --"}, id="sqli-from"),
    pytest.param({"date_to": "'; DROP TABLE expenses; --"}, id="sqli-drop-to"),
    pytest.param(
        {"date_from": "2020-01-15", "date_to": "banana"}, id="valid-from-bad-to"
    ),
]


class TestValidation:
    @pytest.mark.parametrize("params", INVALID_CASES)
    def test_invalid_input_returns_200_not_500(self, logged_in, params):
        resp = _get(logged_in, **params)
        assert resp.status_code == 200, f"Got {resp.status_code} for {params}"

    @pytest.mark.parametrize("params", INVALID_CASES)
    def test_invalid_input_shows_error_message(self, logged_in, params):
        text = _text(_get(logged_in, **params))
        assert "filter-error" in text, f"No error shown for {params}"

    @pytest.mark.parametrize("params", INVALID_CASES)
    def test_invalid_input_shows_unfiltered_data(self, logged_in, params):
        text = _text(_get(logged_in, **params))
        assert _present(text) == set(ALL_MARKERS)
        assert _stats(text) == ("₹135.00", "4", "Bills")

    @pytest.mark.parametrize("params", INVALID_CASES)
    def test_invalid_input_keeps_recent_heading(self, logged_in, params):
        text = _text(_get(logged_in, **params))
        assert "Recent transactions" in text
        assert "No transactions in this date range" not in text

    def test_reversed_range_error_mentions_start_before_end(self, logged_in):
        text = _text(
            _get(logged_in, date_from="2020-12-01", date_to="2020-01-01")
        )
        assert "Start date must be on or before end date" in text

    def test_sqli_does_not_alter_database(self, logged_in):
        _get(logged_in, date_to="'; DROP TABLE expenses; --")
        conn = db.get_db()
        try:
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        finally:
            conn.close()
        assert count == len(DEMO_EXPENSES)

    def test_sqli_does_not_leak_other_users_rows(self, logged_in, other_id):
        text = _text(_get(logged_in, date_from="' OR 1=1 --"))
        assert "other-secret" not in text
        assert "other-march" not in text

    def test_sqli_in_unknown_user_param_is_ignored(self, logged_in, other_id):
        text = _text(_get(logged_in, user_id=str(other_id)))
        assert "other-secret" not in text


# ------------------------------------------------------- user isolation

class TestIsolation:
    def test_filter_excludes_other_users_expenses(self, logged_in, other_id):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        assert "other-secret" not in text
        assert _stats(text) == ("₹130.00", "3", "Bills")

    def test_filter_over_range_only_other_user_has_is_empty(
        self, logged_in, other_id
    ):
        text = _text(_get(logged_in, date_from="2020-03-01", date_to="2020-03-31"))
        assert "other-march" not in text
        assert _stats(text) == ("₹0.00", "0", "—")
        assert "No transactions in this date range" in text

    def test_other_user_sees_only_own_filtered_data(self, client, other_id):
        client.post(
            "/login", data={"email": "other@example.com", "password": "otherpass1"}
        )
        text = _text(_get(client, date_from="2020-01-01", date_to="2020-01-31"))
        assert "other-secret" in text
        assert _present(text) == set()
        assert _stats(text) == ("₹999.00", "1", "Shopping")

    def test_category_breakdown_excludes_other_users_under_filter(
        self, logged_in, other_id
    ):
        text = _text(_get(logged_in, date_from="2020-01-01", date_to="2020-01-31"))
        breakdown = text.split("Spending by category", 1)[1]
        assert "Shopping" not in breakdown


# ----------------------------------------------------------- db layer

class TestDbGetExpenseStats:
    def test_defaults_cover_all_rows(self, demo_id):
        stats = db.get_expense_stats(demo_id)
        assert stats["total_spent"] == 135.00
        assert stats["transaction_count"] == 4
        assert stats["top_category"] == "Bills"

    def test_both_bounds(self, demo_id):
        stats = db.get_expense_stats(
            demo_id, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert stats["total_spent"] == 130.00
        assert stats["transaction_count"] == 3

    def test_only_from(self, demo_id):
        stats = db.get_expense_stats(demo_id, date_from="2020-01-31")
        assert stats["total_spent"] == 25.00
        assert stats["transaction_count"] == 2
        assert stats["top_category"] == "Travel"

    def test_only_to(self, demo_id):
        stats = db.get_expense_stats(demo_id, date_to="2020-01-01")
        assert stats["total_spent"] == 10.00
        assert stats["transaction_count"] == 1
        assert stats["top_category"] == "Food"

    def test_empty_range(self, demo_id):
        stats = db.get_expense_stats(
            demo_id, date_from="2019-01-01", date_to="2019-12-31"
        )
        assert stats == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }

    def test_top_category_computed_within_range(self, demo_id):
        stats = db.get_expense_stats(
            demo_id, date_from="2020-01-31", date_to="2020-02-10"
        )
        assert stats["top_category"] == "Travel"

    def test_scoped_to_user(self, demo_id, other_id):
        stats = db.get_expense_stats(
            demo_id, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert stats["total_spent"] == 135.00
        assert stats["transaction_count"] == 4


class TestDbGetRecentExpenses:
    def test_defaults_return_all_newest_first(self, demo_id):
        rows = db.get_recent_expenses(demo_id)
        assert [r["description"] for r in rows] == [
            "delta-food",
            "charlie-travel",
            "bravo-bills",
            "alpha-food",
        ]

    def test_both_bounds_inclusive(self, demo_id):
        rows = db.get_recent_expenses(
            demo_id, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert [r["description"] for r in rows] == [
            "charlie-travel",
            "bravo-bills",
            "alpha-food",
        ]

    def test_only_from(self, demo_id):
        rows = db.get_recent_expenses(demo_id, date_from="2020-01-15")
        assert {r["description"] for r in rows} == {
            "bravo-bills",
            "charlie-travel",
            "delta-food",
        }

    def test_only_to(self, demo_id):
        rows = db.get_recent_expenses(demo_id, date_to="2020-01-15")
        assert {r["description"] for r in rows} == {"alpha-food", "bravo-bills"}

    def test_empty_range(self, demo_id):
        assert db.get_recent_expenses(
            demo_id, date_from="2019-01-01", date_to="2019-12-31"
        ) == []

    def test_limit_still_applies_with_filter(self, demo_id):
        rows = db.get_recent_expenses(
            demo_id, limit=2, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert [r["description"] for r in rows] == ["delta-food", "charlie-travel"]

    def test_scoped_to_user(self, demo_id, other_id):
        rows = db.get_recent_expenses(
            demo_id, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert "other-secret" not in {r["description"] for r in rows}
        assert len(rows) == 4

    def test_injection_string_treated_as_data(self, demo_id):
        rows = db.get_recent_expenses(demo_id, date_from="' OR 1=1 --")
        assert rows == [] or len(rows) <= 4  # never raises, never other users
        assert all(r["description"] in ALL_MARKERS for r in rows)


class TestDbGetCategoryTotals:
    def test_defaults_all_rows(self, demo_id):
        totals = {c["name"]: c["amount"] for c in db.get_category_totals(demo_id)}
        assert totals == {"Food": 15.00, "Bills": 100.00, "Travel": 20.00}

    def test_both_bounds(self, demo_id):
        totals = {
            c["name"]: c["amount"]
            for c in db.get_category_totals(
                demo_id, date_from="2020-01-01", date_to="2020-01-31"
            )
        }
        assert totals == {"Food": 10.00, "Bills": 100.00, "Travel": 20.00}

    def test_only_from(self, demo_id):
        totals = {
            c["name"]: c["amount"]
            for c in db.get_category_totals(demo_id, date_from="2020-01-31")
        }
        assert totals == {"Travel": 20.00, "Food": 5.00}

    def test_only_to(self, demo_id):
        totals = {
            c["name"]: c["amount"]
            for c in db.get_category_totals(demo_id, date_to="2020-01-01")
        }
        assert totals == {"Food": 10.00}

    def test_empty_range(self, demo_id):
        assert db.get_category_totals(
            demo_id, date_from="2019-01-01", date_to="2019-12-31"
        ) == []

    def test_sorted_by_amount_descending(self, demo_id):
        names = [c["name"] for c in db.get_category_totals(demo_id)]
        assert names == ["Bills", "Travel", "Food"]

    def test_scoped_to_user(self, demo_id, other_id):
        names = {
            c["name"]
            for c in db.get_category_totals(
                demo_id, date_from="2020-01-01", date_to="2020-12-31"
            )
        }
        assert "Shopping" not in names
