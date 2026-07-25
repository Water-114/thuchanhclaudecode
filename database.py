"""Shared SQLite connection helpers, usable from app.py and admin.py alike."""
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "coffeeshop.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
