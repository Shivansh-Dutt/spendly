# Spec: Add Expense

## Overview
Users can currently view their expenses on the profile page but have no way to create new ones; the only data comes from the demo seed. This step replaces the `GET /expenses/add` stub with a real form and adds a POST handler that validates input and inserts an expense for the logged-in user, then redirects back to `/profile` where the new expense appears in the transactions list, stats and category breakdown. It is the first write path for expenses and sets the pattern that edit (Step 8) and delete (Step 9) will follow.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with `PRAGMA foreign_keys = ON`, `CATEGORIES` constant)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4/5: Profile page and backend routes (where the new expense is displayed)

## Routes
- `GET /expenses/add` — renders the add-expense form — logged-in only (redirects to `/login` if not authenticated)
- `POST /expenses/add` — validates the form, inserts the expense for the session user, redirects to `/profile` on success; re-renders the form with an error, the submitted values and HTTP 400 on failure — logged-in only

`/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs.

## Database changes
No database changes. The `expenses` table already has `user_id`, `amount`, `category`, `date` (ISO `YYYY-MM-DD` text) and `description` (nullable). Add one new function in `database/db.py`:
- `create_expense(user_id, amount, category, expense_date, description)` — parameterised `INSERT`, returns `lastrowid`.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with `method="POST"` and `action="{{ url_for('add_expense') }}"`:
  - Amount (`type="number"`, `step="0.01"`, `min="0.01"`, required)
  - Category (`<select>` populated from `categories`, required)
  - Date (`type="date"`, required, defaults to today)
  - Description (`type="text"`, optional, `maxlength="200"`)
  - Submit button and a Cancel link to `url_for('profile')`
  - Inline error block when `error` is set; fields stay pre-filled with the submitted values
- **Modify:** `templates/base.html` — add an "Add expense" nav link (logged-in only, via `url_for`) between the Analytics link and the username

### Context contract
`add_expense.html` receives: `categories` (list of allowed names), `error` (string or `None`), and `form` (dict with `amount`, `category`, `date`, `description` strings for pre-filling; on GET, `date` is today's ISO date and the rest are empty).

## Files to change
- `app.py` — replace the `add_expense` stub with a GET/POST route; import `create_expense` and `CATEGORIES`; add a small validation helper
- `database/db.py` — add `create_expense`
- `templates/base.html` — "Add expense" nav link between Analytics and the username
- `static/css/style.css` — only if shared form classes need small additions; otherwise reuse `.form-group`, `.form-input`, `.auth-error`, `.btn-submit`
- `CLAUDE.md` — update the `/expenses/add` rows in the routes table to "Implemented"
- `tests/test_add_expense.py` — new tests (see Definition of done)

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles, loaded via the template's head block
- `tests/test_add_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles or `<style>` tags; page-specific styles go in `add_expense.css`
- All DB logic lives in `database/db.py`; the route only validates, calls the helper, and renders or redirects
- `user_id` always comes from `session`, never from form input
- Validate server-side (do not trust browser `required`/`min`/`type="date"`):
  - amount: parses as a finite number (reject `nan`/`inf`), greater than 0, at most 2 decimal places or rounded to 2
  - category: must be one of `CATEGORIES`
  - date: valid ISO date via `date.fromisoformat`
  - description: stripped, max 200 chars, stored as `NULL` if blank
- Use `url_for()` for every link and redirect; use `abort()` for HTTP errors, not bare strings
- Vanilla JS only; none is required for this feature
- Do not implement the edit or delete stubs

## Definition of done
- [ ] Unauthenticated `GET` or `POST` to `/expenses/add` redirects to `/login`
- [ ] Logged in, `GET /expenses/add` shows the form with Amount, Category (all 7 categories), Date (defaulting to today) and Description fields, plus a Cancel link back to `/profile`
- [ ] Submitting valid data redirects to `/profile` and the new expense appears at the top of the transactions list (formatted date, category, amount)
- [ ] After adding, the profile's total spent, transaction count and category breakdown reflect the new expense
- [ ] The new row in the `expenses` table has the session user's `user_id`
- [ ] Description left blank is accepted and saved as `NULL`
- [ ] Empty, zero, negative, non-numeric, `nan` and `inf` amounts are rejected with an error message and HTTP 400, with no row inserted
- [ ] A category not in the list (e.g. via a tampered request) is rejected with HTTP 400
- [ ] A malformed or missing date is rejected with HTTP 400
- [ ] On validation failure the form re-renders with the submitted values still filled in
- [ ] A SQL-injection-style description (e.g. `'); DROP TABLE expenses;--`) is stored as plain text and the table is unaffected
- [ ] When logged in, the navbar shows "Add expense" between "Analytics" and the username, linking to `/expenses/add` via `url_for`; it is hidden when logged out
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` still behave as before
- [ ] No hex colour values added to CSS; no SQL in route functions
- [ ] `pytest` passes, including new tests for: auth redirect, GET render, successful add, blank description, each invalid-field case, and that the expense is attached to the session user
