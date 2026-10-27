import os
import tempfile

import database.db as db

# Importing app runs init_db()/seed_db(); point it at a throwaway file first
# so tests never create or touch the real expense_tracker.db.
db.DB_PATH = os.path.join(tempfile.mkdtemp(), "conftest.db")


import pytest


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


@pytest.fixture
def client(temp_db):
    import app as app_module

    return app_module.app.test_client()


@pytest.fixture
def login_demo(client):
    def _login():
        return client.post(
            "/login", data={"email": "demo@spendly.com", "password": "demo123"}
        )

    return _login
