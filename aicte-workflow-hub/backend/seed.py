"""Creates the database and fills it with SYNTHETIC demo data (random, fixed seed = repeatable).

None of this is real AICTE data. Institution names are made-up and marked Demo/Sample/Test.
Run:  python seed.py   (this deletes and recreates aicte.db)
"""
import os
import random
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from db import DB_PATH, REQUIRED_DOCS, SLA_DAYS, STAGES, get_db, init_db
from engine import generate_alerts

INSTITUTIONS = [
    ("Aryabhata Demo College of Engineering", "Indore"),
    ("Sample Institute of Management", "Bhopal"),
    ("Demo Polytechnic Institute", "Pune"),
    ("Test College of Pharmacy", "Jaipur"),
    ("Sample Technical University Campus", "Nagpur"),
    ("Demo Institute of Architecture", "Ahmedabad"),
    ("Sample Engineering College", "Lucknow"),
    ("Test Institute of Technology", "Chennai"),
    ("Demo College of Applied Sciences", "Hyderabad"),
    ("Sample School of Planning", "Kolkata"),
]
USERS = [  # id order matters: 1 admin, 2-3 officials, 4 institution user
    ("Demo Admin", "admin@demo.com", "admin", None),
    ("Demo Official One", "official1@demo.com", "official", None),
    ("Demo Official Two", "official2@demo.com", "official", None),
    ("Demo Institution User", "institution1@demo.com", "institution", 1),
]
DEMO_PASSWORD = "demo123"


def iso(d):
    return d.isoformat()


def seed(today=None, n_apps=36):
    today = today or date.today()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    conn = get_db()
    rng = random.Random(42)

    conn.executemany("INSERT INTO institutions (name, city) VALUES (?, ?)", INSTITUTIONS)
    pw = generate_password_hash(DEMO_PASSWORD)
    conn.executemany(
        "INSERT INTO users (name, email, password_hash, role, institution_id) VALUES (?, ?, ?, ?, ?)",
        [(n, e, pw, r, i) for n, e, r, i in USERS])
    # Mark one institution inactive so the Institutions page shows both states.
    conn.execute("UPDATE institutions SET status = 'Inactive' WHERE id = 9")

    types = list(REQUIRED_DOCS.keys())
    for i in range(1, n_apps + 1):
        inst_id = rng.randint(1, len(INSTITUTIONS))
        a_type = rng.choice(types)
        closed = rng.random() < 0.35
        durations = {s: max(1, round(SLA_DAYS[s] * rng.uniform(0.6, 1.6))) for s in STAGES}

        history = []  # (stage, entered, completed)
        if closed:
            status = rng.choices(["Approved", "Rejected"], weights=[85, 15])[0]
            idx = len(STAGES) - 1
            end = today - timedelta(days=rng.randint(1, 120))
            for s in reversed(STAGES):
                start = end - timedelta(days=durations[s])
                history.append((s, start, end))
                end = start
            history.reverse()
        else:
            status = "In Progress"
            idx = rng.choices(range(5), weights=[1, 3, 3, 2, 1])[0]
            entered = today - timedelta(days=rng.randint(0, SLA_DAYS[STAGES[idx]] * 2))
            history.append((STAGES[idx], entered, None))
            end = entered
            for s in reversed(STAGES[:idx]):
                start = end - timedelta(days=durations[s])
                history.insert(0, (s, start, end))
                end = start

        stage = STAGES[idx]
        stage_entered = history[-1][1]
        submitted_on = history[0][1]
        code = f"APP-{today.year}-{i:03d}"
        assigned = None if closed else rng.choice([2, 3])
        cur = conn.execute(
            "INSERT INTO applications (app_code, institution_id, type, current_stage, status, submitted_on, "
            "stage_entered_on, assigned_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (code, inst_id, a_type, stage, status, iso(submitted_on), iso(stage_entered), assigned))
        app_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO stage_history (application_id, stage, entered_on, completed_on) VALUES (?, ?, ?, ?)",
            [(app_id, s, iso(e), iso(c) if c else None) for s, e, c in history])

        # Documents: later stages tend to have more verified documents.
        if closed or idx >= 2:
            weights = [5, 20, 75]
        elif idx == 1:
            weights = [30, 40, 30]
        else:
            weights = [50, 50, 0]
        for name in REQUIRED_DOCS[a_type]:
            d_status = rng.choices(["Pending", "Submitted", "Verified"], weights=weights)[0]
            expiry, sub_on = None, None
            if d_status != "Pending":
                sub_on = iso(submitted_on)
                roll = rng.random()
                if roll < 0.06:
                    expiry = iso(today - timedelta(days=rng.randint(1, 40)))
                elif roll < 0.20:
                    expiry = iso(today + timedelta(days=rng.randint(1, 30)))
                elif roll < 0.90:
                    expiry = iso(today + timedelta(days=rng.randint(60, 700)))
            conn.execute(
                "INSERT INTO documents (application_id, name, status, submitted_on, expiry_date) "
                "VALUES (?, ?, ?, ?, ?)", (app_id, name, d_status, sub_on, expiry))

    conn.execute("INSERT INTO audit_log (ts, user_name, action, details) VALUES (datetime('now'), ?, ?, ?)",
                 ("System", "Seeded demo data", f"{n_apps} synthetic applications"))
    result = generate_alerts(conn, today)
    conn.commit()
    conn.close()
    return result


if __name__ == "__main__":
    out = seed()
    print("Database created at", DB_PATH)
    print("Alerts generated:", out)
    print(f"Demo logins (password '{DEMO_PASSWORD}'): admin@demo.com, official1@demo.com, institution1@demo.com")
