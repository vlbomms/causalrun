"""Small SQLite records; provider calls never run inside these transactions."""
import contextlib
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS connectors (
    digest TEXT PRIMARY KEY, artifact TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS validations (
    digest TEXT PRIMARY KEY REFERENCES connectors(digest),
    report TEXT NOT NULL, report_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    digest TEXT PRIMARY KEY REFERENCES connectors(digest),
    report_digest TEXT NOT NULL, approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY, action_scope TEXT NOT NULL, connector_digest TEXT NOT NULL REFERENCES connectors(digest),
    action_key TEXT NOT NULL, payload TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('IN_DOUBT', 'COMMITTED')),
    receipt TEXT, UNIQUE(action_scope, action_key)
);
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY, action_id TEXT NOT NULL REFERENCES actions(id),
    kind TEXT NOT NULL, detail TEXT NOT NULL, recorded_at TEXT NOT NULL
);
"""


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # These files contain authority records; agents must not receive filesystem access.
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    with connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(SCHEMA)


@contextlib.contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
