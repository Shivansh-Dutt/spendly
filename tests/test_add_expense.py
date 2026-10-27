from datetime import date, timedelta

import pytest

import database.db as db
from database.db import CATEGORIES

CATEGORY_NAMES = list(CATEGORIES)
ADD_URL = "/expenses/add"

pytestmark = pytest.mark.usefixtures("temp_db")


@pytest.fixture
def logged_in(client, login_demo):
    login_demo()
    return client


def valid_form(**overrides):
    data = {
        "amount": "25.50",
        "category": "Food",
        "date": "2026-01-15",
        "description": "Test lunch",
    }
    data.update(overrides)
    return data


def _all_expense_rows():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id, user_id, amount, category, date, description FROM expenses"
        ).fetchall()
    finally:
        conn.close()


def _expense_count():
    return len(_all_expense_rows())


def _demo_user_id():
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def _create_other_user():
    return db.create_user("Other Person", "other@example.com", "otherpass1")


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_get_redirects_to_login_when_logged_out(self, client):
        response = client.get(ADD_URL)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_redirects_to_login_when_logged_out(self, client):
        response = client.post(ADD_URL, data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_when_logged_out_inserts_nothing(self, client):
        before = _expense_count()
        client.post(ADD_URL, data=valid_form())
        assert _expense_count() == before, "Logged-out POST must not insert"


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #


class TestGetForm:
    def test_get_returns_200(self, logged_in):
        assert logged_in.get(ADD_URL).status_code == 200

    def test_form_posts_to_add_url(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert "<form" in body
        assert 'method="POST"' in body or 'method="post"' in body
        assert 'action="/expenses/add"' in body

    @pytest.mark.parametrize("name", ["amount", "category", "date", "description"])
    def test_form_has_field(self, logged_in, name):
        body = logged_in.get(ADD_URL).data.decode()
        assert f'name="{name}"' in body, f"Missing field {name}"

    @pytest.mark.parametrize("category", CATEGORY_NAMES)
    def test_form_lists_each_category(self, logged_in, category):
        body = logged_in.get(ADD_URL).data.decode()
        assert category in body, f"Category {category} missing from form"

    def test_form_has_one_option_per_category_plus_placeholder(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        select = body.split("<select")[1].split("</select>")[0]
        for category in CATEGORY_NAMES:
            assert f'value="{category}"' in select
        assert select.count("<option") == len(CATEGORY_NAMES) + 1

    def test_description_maxlength_matches_limit(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert 'maxlength="200"' in body

    def test_date_prefilled_with_today(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert date.today().isoformat() in body, "Date should default to today"

    def test_cancel_link_points_to_profile(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert "Cancel" in body
        assert 'href="/profile"' in body

    def test_form_has_submit_button(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert 'type="submit"' in body or "<button" in body

    def test_get_shows_no_error(self, logged_in):
        body = logged_in.get(ADD_URL).data.decode()
        assert "auth-error" not in body


# ------------------------------------------------------------------ #
# Navbar                                                              #
# ------------------------------------------------------------------ #


class TestNavbar:
    def test_logged_in_navbar_has_add_expense_link(self, logged_in):
        body = logged_in.get("/profile").data.decode()
        assert 'href="/expenses/add"' in body
        assert "Add expense" in body

    def test_add_expense_link_between_analytics_and_username(self, logged_in):
        body = logged_in.get("/profile").data.decode()
        nav = body.split('class="nav-links"')[1].split("</nav>")[0]
        analytics = nav.index("Analytics")
        add = nav.index("Add expense")
        username = nav.index("Demo User")
        assert analytics < add < username, "Order must be Analytics, Add expense, username"

    def test_logged_out_navbar_hides_add_expense_link(self, client):
        for path in ("/", "/login", "/register"):
            body = client.get(path).data.decode()
            assert 'href="/expenses/add"' not in body, f"Link leaked on {path}"
            assert "Add expense" not in body, f"Label leaked on {path}"


# ------------------------------------------------------------------ #
# Successful add                                                      #
# ------------------------------------------------------------------ #


class TestSuccessfulAdd:
    def test_valid_post_redirects_to_profile(self, logged_in):
        response = logged_in.post(ADD_URL, data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_one_row_with_values(self, logged_in):
        before = _expense_count()
        logged_in.post(ADD_URL, data=valid_form())
        rows = _all_expense_rows()
        assert len(rows) == before + 1
        row = [r for r in rows if r[5] == "Test lunch"][0]
        assert row[2] == pytest.approx(25.50)
        assert row[3] == "Food"
        assert row[4] == "2026-01-15"

    def test_row_belongs_to_session_user(self, logged_in):
        logged_in.post(ADD_URL, data=valid_form())
        row = [r for r in _all_expense_rows() if r[5] == "Test lunch"][0]
        assert row[1] == _demo_user_id()

    def test_new_expense_appears_on_profile(self, logged_in):
        logged_in.post(ADD_URL, data=valid_form(description="Unique sushi dinner"))
        body = logged_in.get("/profile").data.decode()
        assert "Unique sushi dinner" in body
        assert "25.50" in body

    def test_follow_redirect_lands_on_profile(self, logged_in):
        response = logged_in.post(
            ADD_URL, data=valid_form(description="Followed"), follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Followed" in response.data
        assert b"Member since" in response.data

    def test_profile_total_updates(self, logged_in):
        before = db.get_expense_stats(_demo_user_id())["total_spent"]
        logged_in.post(
            ADD_URL, data=valid_form(amount="100.00", date=date.today().isoformat())
        )
        expected = f"{before + 100:.2f}"
        body = logged_in.get("/profile").data.decode()
        assert expected in body, f"Total should be {before} + 100.00"

    def test_profile_category_breakdown_updates(self, logged_in):
        user_id = _demo_user_id()
        before = {
            c["name"]: c["amount"] for c in db.get_category_totals(user_id)
        }["Health"]
        logged_in.post(ADD_URL, data=valid_form(amount="100.00", category="Health"))
        after = {
            c["name"]: c["amount"] for c in db.get_category_totals(user_id)
        }["Health"]
        assert after == pytest.approx(before + 100)
        assert f"{after:.2f}" in logged_in.get("/profile").data.decode()

    def test_amount_with_integer_value_accepted(self, logged_in):
        response = logged_in.post(ADD_URL, data=valid_form(amount="40"))
        assert response.status_code == 302
        row = [r for r in _all_expense_rows() if r[5] == "Test lunch"][0]
        assert row[2] == pytest.approx(40.0)

    @pytest.mark.parametrize("category", CATEGORY_NAMES)
    def test_every_category_accepted(self, logged_in, category):
        response = logged_in.post(ADD_URL, data=valid_form(category=category))
        assert response.status_code == 302
        assert any(r[3] == category and r[5] == "Test lunch" for r in _all_expense_rows())

    def test_description_is_stripped(self, logged_in):
        logged_in.post(ADD_URL, data=valid_form(description="   padded   "))
        assert any(r[5] == "padded" for r in _all_expense_rows())

    def test_description_of_exactly_200_chars_accepted(self, logged_in):
        desc = "d" * 200
        response = logged_in.post(ADD_URL, data=valid_form(description=desc))
        assert response.status_code == 302
        assert any(r[5] == desc for r in _all_expense_rows())


# ------------------------------------------------------------------ #
# Blank description                                                   #
# ------------------------------------------------------------------ #


class TestBlankDescription:
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_description_saved_as_null(self, logged_in, blank):
        before = _expense_count()
        response = logged_in.post(
            ADD_URL, data=valid_form(amount="7.77", description=blank)
        )
        assert response.status_code == 302
        rows = _all_expense_rows()
        assert len(rows) == before + 1
        row = [r for r in rows if r[2] == pytest.approx(7.77)][0]
        assert row[5] is None, "Blank description must be stored as NULL"

    def test_missing_description_field_saved_as_null(self, logged_in):
        data = valid_form(amount="8.88")
        del data["description"]
        response = logged_in.post(ADD_URL, data=data)
        assert response.status_code == 302
        row = [r for r in _all_expense_rows() if r[2] == pytest.approx(8.88)][0]
        assert row[5] is None


# ------------------------------------------------------------------ #
# Validation failures                                                 #
# ------------------------------------------------------------------ #


class TestInvalidAmount:
    @pytest.mark.parametrize(
        "amount", ["", "0", "0.00", "-5", "-0.01", "abc", "nan", "inf", "-inf", "NaN", "Infinity"]
    )
    def test_invalid_amount_returns_400_and_inserts_nothing(self, logged_in, amount):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(amount=amount))
        assert response.status_code == 400, f"Amount {amount!r} should be rejected"
        assert _expense_count() == before

    @pytest.mark.parametrize("amount", ["0.001", "0.004", "1e308", "10000000.01"])
    def test_tiny_or_huge_amount_returns_400(self, logged_in, amount):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(amount=amount))
        assert response.status_code == 400, f"Amount {amount!r} should be rejected"
        assert _expense_count() == before

    def test_max_amount_accepted(self, logged_in):
        response = logged_in.post(ADD_URL, data=valid_form(amount="10000000"))
        assert response.status_code == 302

    def test_missing_amount_field_returns_400(self, logged_in):
        data = valid_form()
        del data["amount"]
        before = _expense_count()
        assert logged_in.post(ADD_URL, data=data).status_code == 400
        assert _expense_count() == before

    def test_invalid_amount_shows_error_block(self, logged_in):
        body = logged_in.post(ADD_URL, data=valid_form(amount="abc")).data.decode()
        assert "auth-error" in body, "Expected inline error block"


class TestInvalidCategory:
    @pytest.mark.parametrize("category", ["", "Bogus", "food", "Food; DROP TABLE x", "  "])
    def test_invalid_category_returns_400(self, logged_in, category):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(category=category))
        assert response.status_code == 400
        assert _expense_count() == before

    def test_missing_category_returns_400(self, logged_in):
        data = valid_form()
        del data["category"]
        before = _expense_count()
        assert logged_in.post(ADD_URL, data=data).status_code == 400
        assert _expense_count() == before


class TestInvalidDate:
    @pytest.mark.parametrize(
        "bad_date",
        ["", "not-a-date", "2026-13-01", "2026-02-30", "15/01/2026", "2026-1-5x", "0000-00-00"],
    )
    def test_malformed_date_returns_400(self, logged_in, bad_date):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(date=bad_date))
        assert response.status_code == 400, f"Date {bad_date!r} should be rejected"
        assert _expense_count() == before

    @pytest.mark.parametrize(
        "out_of_range",
        [
            "1999-12-31",
            "0001-01-01",
            (date.today() + timedelta(days=1)).isoformat(),
            "9999-12-31",
        ],
    )
    def test_out_of_range_date_returns_400(self, logged_in, out_of_range):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(date=out_of_range))
        assert response.status_code == 400, f"Date {out_of_range} should be rejected"
        assert _expense_count() == before

    @pytest.mark.parametrize(
        "boundary", ["2000-01-01", date.today().isoformat()]
    )
    def test_boundary_dates_accepted(self, logged_in, boundary):
        response = logged_in.post(ADD_URL, data=valid_form(date=boundary))
        assert response.status_code == 302

    def test_missing_date_field_returns_400(self, logged_in):
        data = valid_form()
        del data["date"]
        before = _expense_count()
        assert logged_in.post(ADD_URL, data=data).status_code == 400
        assert _expense_count() == before


class TestInvalidDescription:
    def test_description_over_200_chars_returns_400(self, logged_in):
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(description="x" * 201))
        assert response.status_code == 400
        assert _expense_count() == before


class TestFormRepopulation:
    def test_failed_post_re_renders_submitted_values(self, logged_in):
        response = logged_in.post(
            ADD_URL,
            data=valid_form(
                amount="-3", category="Shopping", date="2026-02-03",
                description="Keep me around",
            ),
        )
        assert response.status_code == 400
        body = response.data.decode()
        assert "-3" in body
        assert "2026-02-03" in body
        assert "Keep me around" in body
        assert "<form" in body
        # selected category retained
        option = body.split('value="Shopping"')[1].split(">")[0]
        assert "selected" in option, "Submitted category should stay selected"

    def test_failed_post_for_bad_category_keeps_other_values(self, logged_in):
        response = logged_in.post(
            ADD_URL, data=valid_form(category="Bogus", description="Still here")
        )
        assert response.status_code == 400
        body = response.data.decode()
        assert "Still here" in body
        assert "25.50" in body

    def test_failed_post_still_lists_all_categories(self, logged_in):
        body = logged_in.post(ADD_URL, data=valid_form(amount="")).data.decode()
        for category in CATEGORY_NAMES:
            assert f'value="{category}"' in body

    def test_failed_post_html_escapes_description(self, logged_in):
        payload = '"><script>alert(1)</script>'
        body = logged_in.post(
            ADD_URL, data=valid_form(amount="abc", description=payload)
        ).data.decode()
        assert "<script>alert(1)</script>" not in body, "Description must be escaped"


# ------------------------------------------------------------------ #
# Security                                                            #
# ------------------------------------------------------------------ #


class TestSecurity:
    def test_sql_injection_description_stored_literally(self, logged_in):
        payload = "'); DROP TABLE expenses;--"
        before = _expense_count()
        response = logged_in.post(ADD_URL, data=valid_form(description=payload))
        assert response.status_code == 302
        rows = _all_expense_rows()  # would raise if table were dropped
        assert len(rows) == before + 1
        assert any(r[5] == payload for r in rows), "Payload must be stored as plain text"

    def test_sql_injection_in_category_rejected(self, logged_in):
        before = _expense_count()
        response = logged_in.post(
            ADD_URL, data=valid_form(category="Food'); DROP TABLE expenses;--")
        )
        assert response.status_code == 400
        assert _expense_count() == before

    def test_user_id_in_form_body_is_ignored(self, logged_in):
        other_id = _create_other_user()
        demo_id = _demo_user_id()
        assert other_id != demo_id
        response = logged_in.post(
            ADD_URL, data=valid_form(description="Spoof attempt", user_id=str(other_id))
        )
        assert response.status_code == 302
        row = [r for r in _all_expense_rows() if r[5] == "Spoof attempt"][0]
        assert row[1] == demo_id, "Expense must belong to the session user"

    def test_stale_session_user_redirects_to_login(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 999999
        before = _expense_count()
        response = client.post(ADD_URL, data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert _expense_count() == before

    def test_expense_not_visible_to_other_user(self, client, login_demo):
        login_demo()
        client.post(ADD_URL, data=valid_form(description="Private purchase"))
        client.get("/logout")
        _create_other_user()
        client.post(
            "/login", data={"email": "other@example.com", "password": "otherpass1"}
        )
        body = client.get("/profile").data.decode()
        assert "Private purchase" not in body


# ------------------------------------------------------------------ #
# Stubs unchanged                                                     #
# ------------------------------------------------------------------ #


class TestOtherStubsUnchanged:
    def test_edit_stub_still_responds(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 200
        assert b"Step 8" in response.data

    def test_delete_stub_still_responds(self, client):
        response = client.get("/expenses/1/delete")
        assert response.status_code == 200
        assert b"Step 9" in response.data

    def test_stubs_do_not_modify_data(self, logged_in):
        before = _expense_count()
        logged_in.get("/expenses/1/edit")
        logged_in.get("/expenses/1/delete")
        assert _expense_count() == before
