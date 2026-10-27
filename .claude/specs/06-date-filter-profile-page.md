# Spec: Date Filter for Profile Page

## Overview
The profile page currently shows all-time stats, the 10 most recent transactions and the all-time category breakdown. This step adds an optional date range filter (From / To) to `/profile`. When a range is applied, the summary stats, the transaction list and the category breakdown all reflect only expenses inside that range. With no range, the page behaves exactly as it does today. This makes the profile useful for answering "what did I spend this month?" before add/edit/delete expense (Steps 7-9) start changing the data.

## Depends on
- Step 1: Database setup (`expenses.date` stored as ISO `YYYY-MM-DD` text)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4: Profile page (`profile.html`, `profile.css`)
- Step 5: Profile backend routes (`get_expense_stats`, `get_recent_expenses`, `get_category_totals`, and the `_profile_*` helpers in `app.py`)

## Routes
- `GET /profile` — now accepts optional query parameters `date_from` and `date_to` (ISO `YYYY-MM-DD`) and renders the profile filtered to that range — logged-in only (unchanged auth behaviour)

No other new routes. The filter is a plain GET form, so a filtered view is bookmarkable and works without JS.

## Database changes
No database changes. `expenses.date` is already ISO text, so string comparison (`date >= ? AND date <= ?`) is correct and needs no schema change.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter form above the stats row: `method="get"`, `action="{{ url_for('profile') }}"`, two `<input type="date">` fields (`date_from`, `date_to`) pre-filled with the current values, an "Apply" submit button and a "Clear" link to `url_for('profile')`.
  - Show an inline error message (e.g. "Start date must be on or before end date.") when the submitted range is invalid.
  - Rename the transactions heading to "Transactions" when a filter is active (keep "Recent transactions" otherwise).
  - Empty state when a filter is active and nothing matches: "No transactions in this date range" (instead of "No transactions yet").

### Context contract
The view passes the existing variables unchanged (`user`, `stats`, `transactions`, `categories`) plus:
- `date_from`: ISO string or `""`
- `date_to`: ISO string or `""`
- `filter_error`: error message string or `None`

## Files to change
- `database/db.py` — add optional `date_from=None, date_to=None` parameters to `get_expense_stats`, `get_recent_expenses` and `get_category_totals`. Build the `WHERE` clause from fixed SQL fragments (`AND date >= ?`, `AND date <= ?`) with values passed as parameters — never interpolate user input into SQL. Defaults keep current behaviour.
- `app.py`
  - Add a small helper that parses/validates `date_from` / `date_to` from `request.args` (valid ISO date via `datetime.strptime` / `date.fromisoformat`; blank means no bound).
  - If either value is malformed, or `date_from > date_to`: ignore the filter (show unfiltered data) and pass `filter_error`. Do not 500.
  - Pass the validated dates through the existing `_profile_transactions`, `_profile_stats`, `_profile_categories` helpers.
- `templates/profile.html` — as above
- `static/css/profile.css` — styles for the filter form, using existing CSS variables
- `CLAUDE.md` — update the `GET /profile` row to mention the optional date filter
- `tests/test_profile.py` — add filter cases (see Definition of done)

## Files to create
None, other than this spec.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles; page-specific styles go in `profile.css`
- All DB logic lives in `database/db.py`; the route function only validates input, fetches data, renders and returns
- Every query stays scoped by `user_id` from the session — never from query-string input
- Validate dates server-side; do not trust the browser's `type="date"` input
- Vanilla JS only, and none is required for this feature
- Use `url_for()` for the form action and the Clear link
- Do not implement the `/expenses/add`, `/expenses/<id>/edit` or `/expenses/<id>/delete` stubs

## Definition of done
- [ ] `/profile` with no query parameters looks and behaves exactly as before (demo user: `₹348.69`, 8 transactions, top category "Bills")
- [ ] The filter form shows From and To date inputs, an Apply button and a Clear link
- [ ] Submitting a range updates the stats, transaction list and category breakdown to only include expenses inside the range (inclusive of both end dates)
- [ ] Only `date_from` set returns expenses on or after that date; only `date_to` set returns expenses on or before it
- [ ] The inputs stay pre-filled with the applied dates after submitting
- [ ] "Clear" returns to the unfiltered profile
- [ ] A range with no matching expenses shows `₹0.00`, `0` transactions, top category `—` and "No transactions in this date range", with no 500 error
- [ ] `?date_from=banana` or `?date_from=2026-12-01&date_to=2026-01-01` shows an error message and the unfiltered data, with no 500 error
- [ ] A SQL-injection-style value such as `?date_from=' OR 1=1 --` is rejected by validation and does not alter results
- [ ] Filtering never shows another user's expenses
- [ ] Unauthenticated access to `/profile?date_from=2026-01-01` still redirects to `/login`
- [ ] No hex colour values added to CSS; no SQL in route functions
- [ ] `pytest` passes, including new tests for: both bounds, single bound, empty range, invalid date, reversed range, and per-user isolation under a filter
