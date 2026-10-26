# Spec: Registration

## Overview
Make the registration form functional. `GET /register` already renders the form; this step adds the `POST /register` handler that validates input, hashes the password, creates a row in `users`, and redirects to the login page. It is the first step that writes user data and is a prerequisite for login (Step 3) and everything behind it.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()` with `PRAGMA foreign_keys = ON`)

## Routes
- `GET /register` — render the registration form (already implemented, unchanged) — public
- `POST /register` — validate form, create user, redirect to `/login` on success; re-render form with an error and HTTP 400 on failure — public

Login, logout and session handling are out of scope (Step 3).

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email UNIQUE NOT NULL`, `password_hash`, `created_at`) is sufficient.

New helpers in `database/db.py`:
- `get_user_by_email(email)` — returns a `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the user, returns the new user id; raises `sqlite3.IntegrityError` on a duplicate email

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change `action="/register"` to `action="{{ url_for('register') }}"`
  - Re-populate `name` and `email` inputs from submitted values on error (never the password)
  - Keep the existing `{% if error %}` block for error display

## Files to change
- `app.py` — allow `POST` on `/register`, add handler
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — see above
- `CLAUDE.md` — mark `POST /register` as implemented in the routes table

## Files to create
- `tests/test_registration.py` — pytest tests for the registration flow (using a temporary DB path)

## New dependencies
No new dependencies (werkzeug is already installed with Flask).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`, not in the route
- Use `url_for()` for every link and redirect — never hardcode URLs
- Use `abort()` for HTTP errors, not bare string returns
- Validation: name non-empty after strip; email non-empty, stripped, lowercased, contains `@`; password at least 8 characters (matches form placeholder)
- Duplicate email: catch `sqlite3.IntegrityError` (or check first) and show "An account with that email already exists" — do not leak a stack trace
- Do not implement login, sessions, or logout in this step
- Keep the app on port 5001

## Definition of done
- [ ] `GET /register` still renders the form with status 200
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is not the plaintext password and passes `check_password_hash`
- [ ] Submitting an email that already exists (case-insensitive) re-renders the form with a duplicate-email error and creates no new row
- [ ] Submitting a password shorter than 8 characters shows an error and creates no row
- [ ] Submitting an empty or whitespace-only name, or an email without `@`, shows an error and creates no row
- [ ] On error, the name and email fields keep their submitted values and the password field is empty
- [ ] The form posts to `url_for('register')`, with no hardcoded `/register`
- [ ] `pytest tests/test_registration.py` passes
- [ ] The seeded demo user (`demo@spendly.com`) still exists and is unaffected
