# Spec: Login and Logout

## Overview
Make sign-in and sign-out functional. `GET /login` already renders the form; this step adds the `POST /login` handler that verifies credentials against the hashed password, stores the user in the Flask session, and redirects to the landing page (the profile page is still a stub until Step 4). It also replaces the `/logout` stub so it clears the session. The navbar becomes session-aware so signed-in users see "Sign out" instead of "Sign in / Get started". This is the gate for every logged-in feature that follows (profile, expense CRUD).

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, `get_user_by_email()`, redirect to `/login`)

## Routes
- `GET /login` — render the sign-in form; if already logged in, redirect to `landing` — public
- `POST /login` — validate credentials, set `session["user_id"]`, redirect to `landing` on success; re-render the form with a generic error and HTTP 400 on failure — public
- `GET /logout` — clear the session and redirect to `landing` — logged-in (a logged-out visitor is simply redirected, no error)

`/profile` and the expense routes remain stubs and are out of scope.

## Database changes
No database changes. The existing `users` table is sufficient.

New helper in `database/db.py`:
- `get_user_by_id(user_id)` — returns a `sqlite3.Row` or `None` (used to load the current user for the navbar)

`get_user_by_email()` already exists and is reused for credential lookup.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Change `action="/login"` to `action="{{ url_for('login') }}"`
    - Re-populate the `email` input from the submitted value on error (never the password)
    - Keep the existing `{% if error %}` block
  - `templates/base.html`
    - When a user is logged in, show their name and a "Sign out" link (`url_for('logout')`) in `.nav-links`; otherwise keep "Sign in" / "Get started"

## Files to change
- `app.py` — set `app.secret_key`, allow `POST` on `/login`, add handler, implement `/logout`, add a context processor exposing `current_user` to templates
- `database/db.py` — add `get_user_by_id()`
- `templates/login.html` — see above
- `templates/base.html` — session-aware navbar
- `static/css/style.css` — only if the navbar user/sign-out display needs styling (use existing CSS variables)
- `CLAUDE.md` — mark `GET /login`/`POST /login` and `GET /logout` as implemented in the routes table

## Files to create
- `tests/test_login_logout.py` — pytest tests for the login/logout flow (using a temporary DB path)

## New dependencies
No new dependencies (Flask sessions and werkzeug are already available).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`, not in routes
- Use `url_for()` for every link and redirect — never hardcode URLs
- Use `abort()` for HTTP errors, not bare string returns
- Use Flask's built-in `session`; `app.secret_key` must be read from an environment variable (e.g. `SECRET_KEY`) with a dev-only fallback value — do not add packages
- Normalise the email (strip, lowercase) before lookup, same as registration
- Use one generic error ("Invalid email or password.") for both unknown email and wrong password — do not reveal which was wrong
- Empty email or password re-renders the form with an error and HTTP 400
- Store only `user_id` in the session; call `session.clear()` on logout
- Do not implement profile, expenses, or a `login_required` decorator beyond what this step needs
- Keep the app on port 5001

## Definition of done
- [ ] `GET /login` renders the form with status 200
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/` and the navbar shows the user's name and a "Sign out" link instead of "Sign in" / "Get started"
- [ ] Email matching is case-insensitive and ignores surrounding whitespace
- [ ] A wrong password shows "Invalid email or password." with status 400 and no session is created
- [ ] An unknown email shows the exact same error as a wrong password
- [ ] Empty email or password shows an error and no session is created
- [ ] On error, the email field keeps its submitted value and the password field is empty
- [ ] Visiting `GET /login` while logged in redirects to `/`
- [ ] `GET /logout` clears the session, redirects (302) to `/`, and the navbar shows "Sign in" / "Get started" again
- [ ] `GET /logout` while logged out redirects to `/` without error
- [ ] The login form posts to `url_for('login')`, with no hardcoded `/login`
- [ ] Newly registered users can log in with the password they registered with
- [ ] `pytest tests/test_login_logout.py` passes
- [ ] Registration tests (`pytest tests/test_registration.py`) still pass
