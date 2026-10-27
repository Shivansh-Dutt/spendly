# Spec: Edit Expense

## Overview
Users can add expenses (Step 7) but cannot correct a mistake once saved. This step replaces the `GET /expenses/<id>/edit` stub with a real, pre-filled form and adds a POST handler that validates input and updates the expense, then redirects back to `/profile`. Each row in the profile transactions table gets an "Edit" link. Ownership is enforced: a user can only edit their own expenses. It reuses the Step 7 validation and form pattern and is the second write path before delete (Step 9).

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with `PRAGMA foreign_keys = ON`, `CATEGORIES`)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4/5: Profile page and backend routes (transactions table where the Edit link lives)
- Step 7: Add expense (`_validate_expense_form`, `EXPENSE_FIELDS`, form styling)

## Routes
- `GET /expenses/<int:id>/edit` — renders the edit form pre-filled with the expense's current values — logged-in only (redirects to `/login` if not authenticated; 404 if the expense does not exist or belongs to another user)
- `POST /expenses/<int:id>/edit` — validates the form, updates the expense, redirects to `/profile` on success; re-renders the form with an error, the submitted values and HTTP 400 on failure — logged-in only (same 404 rule)

`/expenses/<id>/delete` remains a stub.

## Database changes
No schema changes. Add to `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — parameterised `SELECT ... WHERE id = ? AND user_id = ?`; returns the row (`id`, `amount`, `category`, `date` as raw ISO, `description`) or `None`.
- `update_expense(expense_id, user_id, amount, category, expense_date, description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`; returns `True` if a row was updated (`cursor.rowcount > 0`), else `False`.
- Modify `get_recent_expenses` to also return each expense's `id` (needed to build the Edit link). Existing keys are unchanged.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; form with `method="POST"` and `action="{{ url_for('edit_expense', id=expense_id) }}"`:
  - Amount, Category, Date, Description fields identical to `add_expense.html`, pre-filled from `form`
  - "Save changes" submit button and a Cancel link to `url_for('profile')`
  - Inline error block when `error` is set
- **Modify:** `templates/profile.html` — add an Actions column to the transactions table with an "Edit" link per row (`url_for('edit_expense', id=t.id)`)

### Context contract
`edit_expense.html` receives: `expense_id` (int), `categories`, `description_max_length`, `error` (string or `None`), and `form` (dict with `amount`, `category`, `date`, `description` strings; on GET these come from the stored expense, with a `NULL` description shown as empty).

## Files to change
- `app.py` — replace the `edit_expense` stub with a GET/POST route; import `get_expense_by_id`, `update_expense`; reuse `_validate_expense_form`; generalise `_render_expense_form` (or add a sibling helper) so both templates share it
- `database/db.py` — add `get_expense_by_id`, `update_expense`; include `id` in `get_recent_expenses`
- `templates/profile.html` — Edit link column
- `static/css/profile.css` — small style for the Edit link / actions column, using CSS variables
- `CLAUDE.md` — mark `/expenses/<id>/edit` GET and POST as Implemented in the routes table
- `tests/test_profile_transactions.py` — adjust only if existing assertions break due to the new `id` key

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py`

(Reuse `static/css/add_expense.css` via the template's head block; no new CSS file unless the edit page needs distinct styles.)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles or `<style>` tags
- All DB logic lives in `database/db.py`; the route only validates, calls helpers, and renders or redirects
- `user_id` always comes from `session`, never from form input; every read and update is scoped by both `id` and `user_id`
- Use `abort(404)` (not a bare string, not 403) when the expense is missing or not owned by the user, so existence of other users' expenses is not leaked
- Reuse `_validate_expense_form` — do not duplicate validation rules (amount finite and > 0, category in `CATEGORIES`, date valid/not future, description max 200, blank → `NULL`)
- Use `url_for()` for every link and redirect
- Vanilla JS only; none is required
- Do not implement the delete stub

## Definition of done
- [ ] Unauthenticated `GET` or `POST` to `/expenses/<id>/edit` redirects to `/login`
- [ ] Each row in the profile transactions table has an "Edit" link pointing to `/expenses/<id>/edit` (built with `url_for`)
- [ ] Logged in, `GET /expenses/<id>/edit` for your own expense shows the form pre-filled with its amount, category, date and description, plus a Cancel link back to `/profile`
- [ ] A `NULL` description appears as an empty field, not the text "None"
- [ ] Submitting valid changes redirects to `/profile`, and the updated values appear in the transactions list, stats and category breakdown
- [ ] The edited row keeps its `id` and `user_id`; no new row is created
- [ ] Clearing the description saves it as `NULL`
- [ ] Empty, zero, negative, non-numeric, `nan` and `inf` amounts are rejected with an error and HTTP 400, and the stored row is unchanged
- [ ] An invalid category, malformed date, or future date is rejected with HTTP 400 and the row is unchanged
- [ ] On validation failure the form re-renders with the submitted values still filled in
- [ ] `GET` and `POST` to the edit URL of a non-existent expense return 404
- [ ] `GET` and `POST` to the edit URL of another user's expense return 404, and that expense is not modified
- [ ] A SQL-injection-style description is stored as plain text and the table is unaffected
- [ ] `/expenses/<id>/delete` still behaves as before
- [ ] No hex colour values added to CSS; no SQL in route functions
- [ ] `pytest` passes, including new tests for: auth redirect, pre-filled GET, successful update, blank description, each invalid-field case, 404 for missing and other-user expenses, and that the update does not touch other expenses
