import os
import tempfile

import database.db as db

# Importing app runs init_db()/seed_db(); point it at a throwaway file first
# so tests never create or touch the real expense_tracker.db.
db.DB_PATH = os.path.join(tempfile.mkdtemp(), "conftest.db")
