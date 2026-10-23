# Expense Tracker: Session Summary

## What the project is
A Flask web app for tracking expenses, at an early scaffold stage. It appears to be a step-by-step course project: later routes are placeholders marked "coming in Step N".

## Setup done this session
- Ran `pip install -r requirements.txt`:
  - Flask 3.1.3 (was 3.0.3)
  - Werkzeug 3.1.6 (was 3.1.2)
  - pytest 8.3.5 (was 8.3.2)
  - pytest-flask 1.3.0 (new)
- `flask.exe` and `pytest.exe` were installed to `C:\Users\shiva\AppData\Roaming\Python\Python314\Scripts`, which is not on PATH. Use `python -m flask run` and `python -m pytest` until it is added.
- Ran `git init` and `git add .` (nothing committed yet). The LF-to-CRLF warnings are harmless.

## Tech stack
- Python 3.14
- Flask 3.1.3, Werkzeug 3.1.6, Jinja2 templates
- SQLite (planned, not implemented)
- pytest 8.3.5 with pytest-flask 1.3.0
- Server-rendered HTML, plus `static/css/style.css` and `static/js/main.js`
- Dev server: `debug=True`, port 5001

## Project structure
```
expense-tracker/
├── app.py                  Flask app and all routes
├── requirements.txt        Pinned dependencies
├── .gitignore              Excludes venv/, expense_tracker.db, __pycache__/
├── database/
│   ├── __init__.py         Empty package marker
│   └── db.py               Stub: get_db / init_db / seed_db to be written (Step 1)
├── templates/
│   ├── base.html           Shared layout
│   ├── landing.html        Home page
│   ├── login.html          Login form
│   └── register.html       Registration form
├── static/
│   ├── css/style.css       Styling (530 lines)
│   └── js/main.js          Nearly empty
└── venv/                   Local virtualenv (git-ignored)
```

## Routes
| Route | Status |
|---|---|
| `/` | Working (landing page) |
| `/register` | Working (renders form only) |
| `/login` | Working (renders form only) |
| `/logout` | Placeholder (Step 3) |
| `/profile` | Placeholder (Step 4) |
| `/expenses/add` | Placeholder (Step 7) |
| `/expenses/<id>/edit` | Placeholder (Step 8) |
| `/expenses/<id>/delete` | Placeholder (Step 9) |

## Next steps
- Step 1: implement `database/db.py` (`get_db`, `init_db`, `seed_db`).
- Add a `tests/` folder (pytest is installed but there are no tests yet).
- Make the first commit.
