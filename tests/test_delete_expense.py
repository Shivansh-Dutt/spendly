import pytest

import database.db as db

pytestmark = pytest.mark.usefixtures("temp_db")


@pytest.fixture
def logged_in(client, login_demo):
    login_demo()
    return client


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
    return f"/expenses/{expense_id}/delete"


class TestAuthGuard:
    def test_get_redirects_when_logged_out(self, client):
        response = client.get(_url(_make_expense()))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_redirects_and_keeps_row_when_logged_out(self, client):
        expense_id = _make_expense()
        response = client.post(_url(expense_id))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert _row(expense_id) is not None


class TestGet:
    def test_shows_confirmation_details(self, logged_in):
        expense_id = _make_expense()
        response = logged_in.get(_url(expense_id))
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "12.50" in html
        assert "Food" in html
        assert "2026-01-05" in html
        assert "Original lunch" in html
        assert "Delete expense" in html
        assert f'action="{_url(expense_id)}"' in html
        assert 'href="/profile"' in html

    def test_get_does_not_delete(self, logged_in):
        expense_id = _make_expense()
        logged_in.get(_url(expense_id))
        assert _row(expense_id) is not None

    def test_null_description_not_rendered_as_none(self, logged_in):
        expense_id = _make_expense(description=None)
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        assert "None" not in html

    def test_missing_expense_404(self, logged_in):
        assert logged_in.get(_url(99999)).status_code == 404

    def test_other_users_expense_404(self, logged_in):
        assert logged_in.get(_url(_other_users_expense())).status_code == 404


class TestPost:
    def test_deletes_and_redirects_to_profile(self, logged_in):
        expense_id = _make_expense()
        response = logged_in.post(_url(expense_id))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        assert _row(expense_id) is None

    def test_only_target_row_removed(self, logged_in):
        target = _make_expense()
        sibling = _make_expense(description="Keep me")
        other = _other_users_expense()
        before = _expense_count()
        logged_in.post(_url(target))
        assert _expense_count() == before - 1
        assert _row(sibling) is not None
        assert _row(other) is not None

    def test_profile_no_longer_lists_expense(self, logged_in):
        expense_id = _make_expense(description="Unique vanishing item")
        assert "Unique vanishing item" in logged_in.get("/profile").get_data(
            as_text=True
        )
        logged_in.post(_url(expense_id))
        assert "Unique vanishing item" not in logged_in.get("/profile").get_data(
            as_text=True
        )

    def test_second_post_404(self, logged_in):
        expense_id = _make_expense()
        logged_in.post(_url(expense_id))
        assert logged_in.post(_url(expense_id)).status_code == 404

    def test_missing_expense_404(self, logged_in):
        assert logged_in.post(_url(99999)).status_code == 404

    def test_other_users_expense_404_and_untouched(self, logged_in):
        other = _other_users_expense()
        assert logged_in.post(_url(other)).status_code == 404
        assert _row(other) is not None

    def test_deleting_all_expenses_leaves_profile_working(self, logged_in):
        conn = db.get_db()
        try:
            ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM expenses WHERE user_id = ?", (_demo_user_id(),)
                )
            ]
        finally:
            conn.close()
        for expense_id in ids:
            logged_in.post(_url(expense_id))
        assert logged_in.get("/profile").status_code == 200


class TestProfileLinks:
    def test_delete_and_edit_links_present(self, logged_in):
        expense_id = _make_expense()
        html = logged_in.get("/profile").get_data(as_text=True)
        assert f'href="/expenses/{expense_id}/delete"' in html
        assert f'href="/expenses/{expense_id}/edit"' in html


class TestDbHelper:
    def test_owner_deletes(self):
        expense_id = _make_expense()
        assert db.delete_expense(expense_id, _demo_user_id()) is True
        assert _row(expense_id) is None

    def test_non_owner_cannot_delete(self):
        other = _other_users_expense()
        assert db.delete_expense(other, _demo_user_id()) is False
        assert _row(other) is not None
