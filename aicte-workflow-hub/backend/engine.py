"""Alert engine: scans all in-progress applications and creates / auto-resolves alerts.

Alert types: OVERDUE, DOC_EXPIRED, DOC_EXPIRING, DOC_MISSING.
Each alert has a unique dedupe_key, so running the engine many times never duplicates alerts.
Alerts are in-app only. Email / SMS / WhatsApp delivery is NOT implemented (proposed).
The caller must commit the connection.
"""
from datetime import date

from ai import days_in_stage, to_date
from db import SLA_DAYS


def generate_alerts(conn, today=None):
    today = today or date.today()
    wanted = {}  # dedupe_key -> (application_id, kind, severity, message)

    apps = conn.execute("SELECT * FROM applications WHERE status = 'In Progress'").fetchall()
    for a in apps:
        code, stage = a["app_code"], a["current_stage"]
        over = days_in_stage(a, today) - SLA_DAYS[stage]
        if over > 0:
            wanted[f"OVERDUE:{a['id']}:{stage}"] = (
                a["id"], "OVERDUE", "High" if over > 5 else "Medium",
                f"{code} is {over} day(s) past its limit in {stage} stage")

        docs = conn.execute("SELECT * FROM documents WHERE application_id = ?", (a["id"],)).fetchall()
        for d in docs:
            if d["status"] == "Pending":
                if stage != "Submitted":
                    wanted[f"DOC_MISSING:{d['id']}"] = (
                        a["id"], "DOC_MISSING", "Medium", f"{code}: '{d['name']}' is still pending")
            elif d["expiry_date"]:
                delta = (to_date(d["expiry_date"]) - today).days
                if delta < 0:
                    wanted[f"DOC_EXPIRED:{d['id']}"] = (
                        a["id"], "DOC_EXPIRED", "High", f"{code}: '{d['name']}' expired {-delta} day(s) ago")
                elif delta <= 30:
                    wanted[f"DOC_EXPIRING:{d['id']}"] = (
                        a["id"], "DOC_EXPIRING", "High" if delta <= 7 else "Medium",
                        f"{code}: '{d['name']}' expires in {delta} day(s)")

    created = 0
    for key, (app_id, kind, sev, msg) in wanted.items():
        cur = conn.execute(
            "INSERT OR IGNORE INTO alerts (application_id, kind, severity, message, dedupe_key, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?)", (app_id, kind, sev, msg, key, today.isoformat()))
        created += cur.rowcount

    # Auto-resolve alerts whose problem no longer exists (doc verified, stage moved on, ...).
    resolved = 0
    for r in conn.execute("SELECT id, dedupe_key FROM alerts WHERE resolved = 0").fetchall():
        if r["dedupe_key"] not in wanted:
            conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (r["id"],))
            resolved += 1
    return {"created": created, "auto_resolved": resolved}
