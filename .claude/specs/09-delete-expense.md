# Spec: Delete Expense

## Overview
Users can add (Step 7) and edit (Step 8) expenses but cannot remove one. This step replaces the `/expenses/<id>/delete` stub with a real flow: `GET` shows a confirmation page describing the expense, and `POST` permanently deletes it and redirects to `/profile`. Deletion is a state change, so it is done via POST only (never a GET link that deletes), which prevents accidental deletion by link prefetching or cross-site image/link requests. Each row in the profile transactions table gets a "Delete" link next to "Edit". Ownership is enforced: a user can only delete their own expenses. This completes the expense CRUD set.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with `PRAGMA foreign_keys = ON`)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4/5: Profile page and backend routes (transactions table with Actions column)
- Step 8: Edit expense (`get_expense_by_id`, Edit link / actions column, 404-on-not-owned pattern)

## Routes
- `GET /expenses/<int:id>/delete` — renders a confirmation page showing the expense's amount, category, date and description, with a "Delete" button (POST form) and a Cancel link — logged-in only (redirects to `/login` if not authenticated; 404 if the expense does not exist or belongs to another user)
- `POST /expenses/<int:id>/delete` — deletes the expense, redirects to `/profile` — logged-in only (redirects to `/login` if not authenticated; 404 if the expense does not exist or belongs to another user)

The existing route is GET-only and returns a raw string; it is replaced by a `GET`/`POST` route.

## Database changes
No schema changes. Add to `database/db.py`:
- `delete_expense(expense_id, user_id)` — parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`; commits; returns `True` if a row was deleted (`cursor.rowcount > 0`), else `False`.

`get_expense_by_id` (Step 8) is reused for the confirmation page.

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; shows the expense details being deleted and a warning that it cannot be undone; a `method="POST"` form with `action="{{ url_for('delete_expense', id=expense_id) }}"` and a "Delete expense" submit button; a Cancel link to `url_for('profile')`
- **Modify:** `templates/profile.html` — add a "Delete" link per transaction row in the Actions column (`url_for('delete_expense', id=t.id)`), beside the existing Edit link

### Context contract
`delete_expense.html` receives: `expense_id` (int) and `expense` (row/dict with `amount`, `category`, `date` as raw ISO, `description` — `NULL` description shown as empty or "—", never the text "None").

## Files to change
- `app.py` — replace the `delete_expense` stub with a GET/POST route; import `delete_expense` from `database.db` (rename the route function or the import alias to avoid a name clash, e.g. route `delete_expense_view` with `endpoint="delete_expense"`, or import the helper as `remove_expense`)
- `database/db.py` — add the delete helper
- `templates/profile.html` — Delete link in the Actions column
- `static/css/profile.css` — small style for the Delete link (danger colour via CSS variable)
- `CLAUDE.md` — mark `/expenses/<id>/delete` GET and POST as Implemented in the routes table

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css` — confirmation page styles (or reuse `add_expense.css` via the head block if sufficient)
- `tests/test_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles or `<style>` tags
- All DB logic lives in `database/db.py`; the route only checks session, calls helpers, and renders or redirects
- Deletion must happen on POST only; a GET must never modify data
- `user_id` always comes from `session`, never from form input; every read and delete is scoped by both `id` and `user_id`
- Use `abort(404)` (not a bare string, not 403) when the expense is missing or not owned by the user, so the existence of other users' expenses is not leaked
- Use `url_for()` for every link, form action and redirect
- Vanilla JS only; none is required (confirmation is the server-rendered page)
- Do not touch any other stub route

## Definition of done
- [ ] Unauthenticated `GET` or `POST` to `/expenses/<id>/delete` redirects to `/login`, and nothing is deleted
- [ ] Each row in the profile transactions table has a "Delete" link pointing to `/expenses/<id>/delete` (built with `url_for`)
- [ ] Logged in, `GET /expenses/<id>/delete` for your own expense shows a confirmation page with its amount, category, date and description, a "Delete expense" button and a Cancel link back to `/profile`
- [ ] `GET /expenses/<id>/delete` does not delete the expense (it still appears on `/profile` afterwards)
- [ ] A `NULL` description is not rendered as the text "None"
- [ ] Clicking Cancel returns to `/profile` with the expense intact
- [ ] Submitting the confirmation form (`POST`) redirects to `/profile` and the expense no longer appears in the transactions list; stats and category breakdown reflect its removal
- [ ] Only the targeted row is removed; other expenses (including the user's others) are unchanged
- [ ] `GET` and `POST` to the delete URL of a non-existent expense return 404
- [ ] `GET` and `POST` to the delete URL of another user's expense return 404, and that expense still exists
- [ ] Deleting the same expense twice: the second `POST` returns 404
- [ ] Deleting the last remaining expense leaves `/profile` rendering correctly with zeros / empty state
- [ ] The Edit link and `/expenses/<id>/edit` behave as before
- [ ] No hex colour values added to CSS; no SQL in route functions
- [ ] `pytest` passes, including new tests for: auth redirect (GET and POST), confirmation GET shows details without deleting, successful POST delete, 404 for missing and other-user expenses, double-delete 404, and that deletion does not touch other expenses
