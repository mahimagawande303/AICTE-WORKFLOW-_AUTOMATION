"""Database layer: constants, schema and connection helper (SQLite)."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# AICTE_DB env variable lets the tests use a separate temporary database.
DB_PATH = os.environ.get("AICTE_DB", os.path.join(BASE_DIR, "aicte.db"))

# Workflow stages, in order.
STAGES = ["Submitted", "Scrutiny", "EVC", "Committee", "Final Decision"]

# Allowed days per stage (SLA). These are ASSUMED demo values, not official AICTE rules.
SLA_DAYS = {"Submitted": 2, "Scrutiny": 7, "EVC": 14, "Committee": 10, "Final Decision": 5}

# Required documents per application type (also an ASSUMED demo checklist).
REQUIRED_DOCS = {
    "New Institution": ["Land Use Certificate", "Building Plan", "Financial Statement", "Faculty List"],
    "Renewal": ["Lease Document", "Faculty List", "Financial Statement"],
    "Expansion": ["Building Plan", "Faculty List", "Financial Statement"],
    "Re-scrutiny": ["Faculty List", "Building Plan"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS institutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','official','institution')),
    institution_id INTEGER REFERENCES institutions(id)
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_code TEXT NOT NULL UNIQUE,
    institution_id INTEGER NOT NULL REFERENCES institutions(id),
    type TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'In Progress' CHECK (status IN ('In Progress','Approved','Rejected')),
    submitted_on TEXT NOT NULL,
    stage_entered_on TEXT NOT NULL,
    assigned_to INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS stage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    stage TEXT NOT NULL,
    entered_on TEXT NOT NULL,
    completed_on TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','Submitted','Verified')),
    submitted_on TEXT,
    expiry_date TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_on TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user_name TEXT NOT NULL,
    action TEXT NOT NULL,
    application_id INTEGER,
    details TEXT
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
