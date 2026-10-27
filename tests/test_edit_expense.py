from datetime import date, timedelta

import pytest

import database.db as db

pytestmark = pytest.mark.usefixtures("temp_db")


@pytest.fixture
def logged_in(client, login_demo):
    login_demo()
    return client


def valid_form(**overrides):
    data = {
        "amount": "40.25",
        "category": "Transport",
        "date": "2026-02-10",
        "description": "Updated cab",
    }
    data.update(overrides)
    return data


def _row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
    finally:
        conn.close()


def _expense_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _demo_user_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


def _make_expense(user_id=None, description="Original lunch"):
    return db.create_expense(
        user_id or _demo_user_id(), 12.5, "Food", "2026-01-05", description
    )


def _other_users_expense():
    other_id = db.create_user("Other Person", "other@example.com", "otherpass1")
    return _make_expense(other_id, "Other's expense")


def _url(expense_id):
    return f"/expenses/{expense_id}/edit"


class TestAuthGuard:
    def test_get_redirects_when_logged_out(self, client):
        response = client.get(_url(_make_expense()))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_redirects_when_logged_out(self, client):
        expense_id = _make_expense()
        response = client.post(_url(expense_id), data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert _row(expense_id)["description"] == "Original lunch"

    def test_missing_id_redirects_when_logged_out(self, client):
        assert client.get(_url(99999)).status_code == 302


class TestGet:
    def test_prefilled_form(self, logged_in):
        expense_id = _make_expense()
        response = logged_in.get(_url(expense_id))
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert 'value="12.50"' in html
        assert 'value="2026-01-05"' in html
        assert 'value="Original lunch"' in html
        assert '<option value="Food" selected>' in html
        assert f'action="{_url(expense_id)}"' in html
        assert 'href="/profile"' in html

    def test_null_description_is_empty(self, logged_in):
        expense_id = _make_expense(description=None)
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        assert "None" not in html
        assert 'name="description"' in html


class TestPost:
    def test_valid_update(self, logged_in):
        expense_id = _make_expense()
        count = _expense_count()
        response = logged_in.post(_url(expense_id), data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        row = _row(expense_id)
        assert row["user_id"] == _demo_user_id()
        assert row["amount"] == 40.25
        assert row["category"] == "Transport"
        assert row["date"] == "2026-02-10"
        assert row["description"] == "Updated cab"
        assert _expense_count() == count

    def test_blank_description_saved_as_null(self, logged_in):
        expense_id = _make_expense()
        logged_in.post(_url(expense_id), data=valid_form(description="   "))
        assert _row(expense_id)["description"] is None

    def test_other_expenses_untouched(self, logged_in):
        expense_id = _make_expense()
        sibling = _make_expense(description="Sibling")
        other = _other_users_expense()
        logged_in.post(_url(expense_id), data=valid_form())
        assert _row(sibling)["description"] == "Sibling"
        assert _row(other)["description"] == "Other's expense"

    def test_sql_injection_description_stored_verbatim(self, logged_in):
        expense_id = _make_expense()
        payload = "'); DROP TABLE expenses;--"
        logged_in.post(_url(expense_id), data=valid_form(description=payload))
        assert _row(expense_id)["description"] == payload

    def test_profile_shows_updated_values_and_edit_links(self, logged_in):
        expense_id = _make_expense()
        logged_in.post(_url(expense_id), data=valid_form(description="Zebra"))
        html = logged_in.get("/profile").get_data(as_text=True)
        assert "Zebra" in html
        assert f'href="{_url(expense_id)}"' in html


FUTURE = (date.today() + timedelta(days=2)).isoformat()


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": ""},
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "abc"},
        {"amount": "nan"},
        {"amount": "inf"},
        {"amount": "999999999"},
        {"category": "Nonsense"},
        {"category": ""},
        {"date": ""},
        {"date": "not-a-date"},
        {"date": FUTURE},
        {"date": "1999-12-31"},
        {"description": "x" * 201},
    ],
)
def test_invalid_input_rejected(logged_in, overrides):
    expense_id = _make_expense()
    before = tuple(_row(expense_id))
    response = logged_in.post(_url(expense_id), data=valid_form(**overrides))
    assert response.status_code == 400
    assert tuple(_row(expense_id)) == before


def test_invalid_input_rerenders_submitted_values(logged_in):
    expense_id = _make_expense()
    response = logged_in.post(
        _url(expense_id), data=valid_form(amount="abc", description="Keep me")
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert 'value="abc"' in html
    assert 'value="Keep me"' in html
    assert "auth-error" in html


class TestOwnership:
    def test_missing_expense_404(self, logged_in):
        assert logged_in.get(_url(99999)).status_code == 404
        assert logged_in.post(_url(99999), data=valid_form()).status_code == 404

    def test_other_users_expense_404(self, logged_in):
        other = _other_users_expense()
        assert logged_in.get(_url(other)).status_code == 404
        response = logged_in.post(_url(other), data=valid_form())
        assert response.status_code == 404
        assert _row(other)["description"] == "Other's expense"


def test_delete_page_renders_confirmation(logged_in):
    response = logged_in.get("/expenses/1/delete")
    assert response.status_code == 200
    assert "Delete expense" in response.get_data(as_text=True)


def test_db_helpers_scope_by_user():
    expense_id = _make_expense()
    other_id = db.create_user("Other Person", "other@example.com", "otherpass1")
    assert db.get_expense_by_id(expense_id, other_id) is None
    assert (
        db.update_expense(expense_id, other_id, 1.0, "Food", "2026-01-01", None)
        is False
    )
    assert _row(expense_id)["amount"] == 12.5
