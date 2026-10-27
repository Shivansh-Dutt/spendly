# Spec: Profile Backend Routes

## Overview
Step 4 built the `/profile` page UI on hardcoded Python constants, so every logged-in user sees "Demo User" and the same eight transactions. This step connects the page to the database: the `/profile` view fetches the logged-in user's real details, summary stats, recent transactions and per-category totals through new helpers in `database/db.py`. The existing `profile.html` layout stays as built; only the data source changes. Doing this now makes the profile accurate before add/edit/delete expense (Steps 7-9) start changing the data.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `get_db()`, seed data)
- Step 2: Registration (user accounts exist)
- Step 3: Login + Logout (`session["user_id"]` is set)
- Step 4: Profile page (`profile.html`, `profile.css`, and the context shape the template expects)

## Routes
- `GET /profile` — render the profile page using the logged-in user's real data from the database — logged-in only (redirect to `/login` if not authenticated; also redirect to `/login` and clear the session if `user_id` no longer matches a user)

No other new routes.

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient. New query helpers are added to `database/db.py` (listed under Files to change).

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Handle the empty state: a user with no expenses must not crash the page. The category breakdown currently divides by `stats.total_spent`, which is `0` for a new user. Guard that division, and show a short "No transactions yet" message in place of the empty table and breakdown list.
  - The data shape the template reads must stay the same (see "Context contract" below), so the rest of the markup is unchanged.

### Context contract
The view passes the same four variables the template already uses:
- `user`: `name`, `email`, `initials`, `member_since` (formatted like `"January 2026"`)
- `stats`: `total_spent` (float), `transaction_count` (int), `top_category` (str, or `"—"` when there are no expenses)
- `transactions`: list of `{date, description, category, amount}`, newest first, `date` formatted like `"22 Oct 2026"`
- `categories`: list of `{name, amount}`, sorted by amount descending

## Files to change
- `database/db.py` — add helpers, all taking `user_id` and using parameterised queries:
  - `get_user_profile(user_id)` — name, email, derived initials, and `member_since` from `users.created_at`
  - `get_expense_stats(user_id)` — total spent, transaction count, top category (`SUM`/`COUNT`, top category by total amount)
  - `get_recent_expenses(user_id, limit=10)` — newest first (`ORDER BY date DESC, id DESC`)
  - `get_category_totals(user_id)` — `GROUP BY category ORDER BY SUM(amount) DESC`
- `app.py`
  - Remove the hardcoded `PROFILE_USER`, `PROFILE_STATS`, `PROFILE_TRANSACTIONS` and `PROFILE_CATEGORIES` constants and the "hardcoded, Step 4" comment.
  - Rewrite the `profile()` view: auth guard, call the db helpers, render the template. No SQL in the route.
  - Move the `/logout` route out of the "Placeholder routes — students will implement these" section and update that comment, since it is stale.
- `templates/profile.html` — empty-state handling as above
- `CLAUDE.md` — update the route table (`GET /profile` now reads from the database) and remove the outdated warning that `database/db.py` is empty
- `tests/test_profile.py` — update for real data (see Definition of done)

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
- No inline styles
- All DB logic lives in `database/db.py`; the route function only fetches data, renders and returns
- Every query is scoped by `user_id` taken from the session — never from query-string or form input — so one user can never see another user's expenses
- Close connections in a `try/finally`, matching the existing helpers
- Use `abort()` for HTTP errors rather than returning raw strings
- Do not implement the `/expenses/add`, `/expenses/<id>/edit` or `/expenses/<id>/delete` stubs; they belong to Steps 7-9
- Currency symbol stays as in the existing template (`₹`)

## Definition of done
- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] Logging in as the seeded demo user (`demo@spendly.com` / `demo123`) shows "Demo User", the seeded eight transactions, total `₹348.69`, 8 transactions and top category "Bills"
- [ ] Registering a new account and logging in shows that user's own name and email, not "Demo User"
- [ ] A newly registered user with no expenses sees the profile with `₹0.00`, `0` transactions, top category `—` and a "No transactions yet" message, with no 500 error
- [ ] Inserting an expense for one user does not appear on another user's profile
- [ ] Transactions are listed newest first; dates are formatted like `22 Oct 2026`
- [ ] Category breakdown is sorted by amount descending and the percentages add up to roughly 100%
- [ ] No hardcoded profile constants remain in `app.py`, and no SQL appears in any route function
- [ ] A session whose `user_id` no longer exists redirects to `/login` instead of erroring
- [ ] `pytest` passes, including updated `tests/test_profile.py` cases for the demo user, a new user with no expenses, and per-user data isolation
