"""Flask backend (REST API + serves the frontend).  Run:  python app.py"""
import os
from datetime import date, datetime
from functools import wraps

from flask import Flask, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash

from ai import days_in_stage, predict_completion, risk_score, to_date
from db import DB_PATH, REQUIRED_DOCS, SLA_DAYS, STAGES, get_db
from engine import generate_alerts

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE, "..", "frontend"), static_url_path="")
app.json.sort_keys = False  # keep stage order (Submitted -> ... -> Final Decision) in JSON
# DEMO ONLY: in a real deployment load this from an environment variable.
SECRET_KEY = os.environ.get("SECRET_KEY", "demo-secret-change-me")
serializer = URLSafeTimedSerializer(SECRET_KEY)


# ---------- helpers ----------
def auth(*roles):
    """Login check + optional role check. Gives handlers g.user and g.conn."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Please login first"), 401
            try:
                data = serializer.loads(header[7:], max_age=8 * 3600)
            except (BadSignature, SignatureExpired):
                return jsonify(error="Session invalid or expired"), 401
            conn = get_db()
            u = conn.execute("SELECT id, name, email, role, institution_id FROM users WHERE id = ?",
                             (data["uid"],)).fetchone()
            if not u:
                conn.close()
                return jsonify(error="User not found"), 401
            if roles and u["role"] not in roles:
                conn.close()
                return jsonify(error="Your role is not allowed to do this"), 403
            g.user, g.conn = dict(u), conn
            try:
                return fn(*args, **kwargs)
            finally:
                conn.close()
        return wrapper
    return deco


def scope(alias="a"):
    """Institution users may only see their own institution's data."""
    if g.user["role"] == "institution":
        return f" AND {alias}.institution_id = {int(g.user['institution_id'])}"
    return ""


def audit(conn, user_name, action, app_id=None, details=""):
    conn.execute("INSERT INTO audit_log (ts, user_name, action, application_id, details) "
                 "VALUES (datetime('now'), ?, ?, ?, ?)", (user_name, action, app_id, details))


def docs_grouped(conn, only_in_progress=False):
    sql = "SELECT d.* FROM documents d JOIN applications a ON a.id = d.application_id WHERE 1=1"
    if only_in_progress:
        sql += " AND a.status = 'In Progress'"
    sql += scope()
    grouped = {}
    for d in conn.execute(sql).fetchall():
        grouped.setdefault(d["application_id"], []).append(d)
    return grouped


def app_view(a, docs, today):
    d = dict(a)
    d["days_in_stage"] = days_in_stage(a, today)
    d["sla_days"] = SLA_DAYS[a["current_stage"]]
    d["overdue_days"] = max(0, d["days_in_stage"] - d["sla_days"]) if a["status"] == "In Progress" else 0
    d["risk"] = risk_score(a, docs, today)
    return d


APP_SELECT = ("SELECT a.*, i.name AS institution_name, u.name AS assigned_name FROM applications a "
              "JOIN institutions i ON i.id = a.institution_id LEFT JOIN users u ON u.id = a.assigned_to WHERE 1=1")


# ---------- pages ----------
@app.get("/")
def home():
    return app.send_static_file("index.html")


# ---------- auth ----------
@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE email = ?", (str(data.get("email", "")).strip().lower(),)).fetchone()
    if not u or not check_password_hash(u["password_hash"], str(data.get("password", ""))):
        conn.close()
        return jsonify(error="Wrong email or password"), 401
    audit(conn, u["name"], "Login")
    conn.commit()
    conn.close()
    return jsonify(token=serializer.dumps({"uid": u["id"]}),
                   user={"name": u["name"], "email": u["email"], "role": u["role"]})


@app.get("/api/config")
@auth()
def config():
    return jsonify(stages=STAGES, sla_days=SLA_DAYS, required_docs=REQUIRED_DOCS)


# ---------- dashboard ----------
@app.get("/api/dashboard")
@auth()
def dashboard():
    conn, today = g.conn, date.today()
    grouped = docs_grouped(conn)
    apps = conn.execute(APP_SELECT + scope() + " ORDER BY a.id DESC").fetchall()
    views = [app_view(a, grouped.get(a["id"], []), today) for a in apps]
    active = [v for v in views if v["status"] == "In Progress"]

    expiring = 0
    for a in active:
        for d in grouped.get(a["id"], []):
            if d["expiry_date"] and 0 <= (to_date(d["expiry_date"]) - today).days <= 30:
                expiring += 1
    open_alerts = conn.execute(
        "SELECT COUNT(*) FROM alerts al JOIN applications a ON a.id = al.application_id "
        "WHERE al.resolved = 0" + scope()).fetchone()[0]
    stage_counts = {s: 0 for s in STAGES}
    for a in active:
        stage_counts[a["current_stage"]] += 1
    return jsonify(
        total=len(views),
        in_progress=len(active),
        approved=sum(v["status"] == "Approved" for v in views),
        rejected=sum(v["status"] == "Rejected" for v in views),
        overdue=sum(v["overdue_days"] > 0 for v in active),
        expiring_docs=expiring,
        open_alerts=open_alerts,
        stage_counts=stage_counts,
        top_risk=sorted(active, key=lambda v: v["risk"]["score"], reverse=True)[:5],
        recent=views[:5],
    )


# ---------- applications ----------
@app.get("/api/applications")
@auth()
def list_applications():
    conn, today = g.conn, date.today()
    sql, params = APP_SELECT + scope(), []
    q = request.args.get("q", "").strip()
    if q:
        sql += " AND (a.app_code LIKE ? OR i.name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if request.args.get("stage"):
        sql += " AND a.current_stage = ?"
        params.append(request.args["stage"])
    if request.args.get("status"):
        sql += " AND a.status = ?"
        params.append(request.args["status"])
    sql += " ORDER BY a.id DESC"
    grouped = docs_grouped(conn)
    return jsonify([app_view(a, grouped.get(a["id"], []), today) for a in conn.execute(sql, params).fetchall()])


@app.get("/api/applications/<int:app_id>")
@auth()
def application_detail(app_id):
    conn, today = g.conn, date.today()
    a = conn.execute(APP_SELECT + scope() + " AND a.id = ?", (app_id,)).fetchone()
    if not a:
        return jsonify(error="Application not found"), 404
    docs = conn.execute("SELECT * FROM documents WHERE application_id = ? ORDER BY id", (app_id,)).fetchall()
    history = conn.execute("SELECT stage, entered_on, completed_on FROM stage_history "
                           "WHERE application_id = ? ORDER BY id", (app_id,)).fetchall()
    return jsonify(
        application=app_view(a, docs, today),
        documents=[dict(d, days_to_expiry=(to_date(d["expiry_date"]) - today).days if d["expiry_date"] else None)
                   for d in docs],
        history=[dict(h) for h in history],
        prediction=predict_completion(conn, a, today),
        stages=STAGES,
    )


@app.post("/api/applications")
@auth()
def create_application():
    conn, today = g.conn, date.today()
    data = request.get_json(silent=True) or {}
    a_type = data.get("type")
    if a_type not in REQUIRED_DOCS:
        return jsonify(error=f"type must be one of {list(REQUIRED_DOCS)}"), 400
    if g.user["role"] == "institution":
        inst_id = g.user["institution_id"]
    else:
        inst_id = data.get("institution_id")
        if not conn.execute("SELECT 1 FROM institutions WHERE id = ?", (inst_id,)).fetchone():
            return jsonify(error="Valid institution_id is required"), 400
    n = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] + 1
    code = f"APP-{today.year}-{n:03d}"
    cur = conn.execute(
        "INSERT INTO applications (app_code, institution_id, type, current_stage, submitted_on, stage_entered_on) "
        "VALUES (?, ?, ?, 'Submitted', ?, ?)", (code, inst_id, a_type, today.isoformat(), today.isoformat()))
    app_id = cur.lastrowid
    conn.execute("INSERT INTO stage_history (application_id, stage, entered_on) VALUES (?, 'Submitted', ?)",
                 (app_id, today.isoformat()))
    for name in REQUIRED_DOCS[a_type]:
        conn.execute("INSERT INTO documents (application_id, name) VALUES (?, ?)", (app_id, name))
    audit(conn, g.user["name"], "Application created", app_id, f"{code} ({a_type})")
    conn.commit()
    return jsonify(id=app_id, app_code=code), 201


@app.post("/api/applications/<int:app_id>/advance")
@auth("admin", "official")
def advance(app_id):
    conn, today = g.conn, date.today().isoformat()
    a = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if not a:
        return jsonify(error="Application not found"), 404
    if a["status"] != "In Progress":
        return jsonify(error="Application is already closed"), 409

    idx = STAGES.index(a["current_stage"])

    if idx == len(STAGES) - 1:  # Final Decision -> needs a decision
        decision = (request.get_json(silent=True) or {}).get("decision")
        if decision not in ("Approved", "Rejected"):
            return jsonify(error="At Final Decision send decision = 'Approved' or 'Rejected'"), 400
        conn.execute("UPDATE stage_history SET completed_on = ? WHERE application_id = ? AND completed_on IS NULL",
                     (today, app_id))
        conn.execute("UPDATE applications SET status = ? WHERE id = ?", (decision, app_id))
        msg = f"{a['app_code']} {decision}"
    else:
        # Compliance gate: cannot leave Scrutiny while any document is still Pending.
        if a["current_stage"] == "Scrutiny":
            pending = [r["name"] for r in conn.execute(
                "SELECT name FROM documents WHERE application_id = ? AND status = 'Pending'", (app_id,))]
            if pending:
                return jsonify(error="Cannot move to EVC. Pending documents: " + ", ".join(pending)), 409
        nxt = STAGES[idx + 1]
        conn.execute("UPDATE stage_history SET completed_on = ? WHERE application_id = ? AND completed_on IS NULL",
                     (today, app_id))
        conn.execute("INSERT INTO stage_history (application_id, stage, entered_on) VALUES (?, ?, ?)",
                     (app_id, nxt, today))
        conn.execute("UPDATE applications SET current_stage = ?, stage_entered_on = ?, "
                     "assigned_to = COALESCE(assigned_to, ?) WHERE id = ?",
                     (nxt, today, g.user["id"] if g.user["role"] == "official" else None, app_id))
        msg = f"{a['app_code']} moved {a['current_stage']} -> {nxt}"
    audit(conn, g.user["name"], "Stage changed", app_id, msg)
    generate_alerts(conn)
    conn.commit()
    return jsonify(ok=True, message=msg)


# ---------- documents / compliance ----------
@app.get("/api/documents")
@auth()
def list_documents():
    today = date.today()
    sql = ("SELECT d.*, a.app_code, a.current_stage, i.name AS institution_name FROM documents d "
           "JOIN applications a ON a.id = d.application_id JOIN institutions i ON i.id = a.institution_id "
           "WHERE a.status = 'In Progress'" + scope())
    params = []
    if request.args.get("status"):
        sql += " AND d.status = ?"
        params.append(request.args["status"])
    sql += " ORDER BY d.expiry_date IS NULL, d.expiry_date"
    rows = g.conn.execute(sql, params).fetchall()
    return jsonify([dict(r, days_to_expiry=(to_date(r["expiry_date"]) - today).days if r["expiry_date"] else None)
                    for r in rows])


@app.post("/api/documents/<int:doc_id>/status")
@auth()
def set_document_status(doc_id):
    conn = g.conn
    data = request.get_json(silent=True) or {}
    new, expiry = data.get("status"), data.get("expiry_date") or None
    if new not in ("Pending", "Submitted", "Verified"):
        return jsonify(error="status must be Pending, Submitted or Verified"), 400
    if expiry:
        try:
            datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            return jsonify(error="expiry_date must be YYYY-MM-DD"), 400
    row = conn.execute("SELECT d.*, a.institution_id, a.app_code FROM documents d "
                       "JOIN applications a ON a.id = d.application_id WHERE d.id = ?", (doc_id,)).fetchone()
    if not row:
        return jsonify(error="Document not found"), 404
    if g.user["role"] == "institution" and (row["institution_id"] != g.user["institution_id"] or new != "Submitted"):
        return jsonify(error="Institutions can only mark their own documents as Submitted"), 403
    conn.execute("UPDATE documents SET status = ?, submitted_on = CASE WHEN ? = 'Submitted' THEN ? "
                 "ELSE submitted_on END, expiry_date = COALESCE(?, expiry_date) WHERE id = ?",
                 (new, new, date.today().isoformat(), expiry, doc_id))
    audit(conn, g.user["name"], f"Document {new}", row["application_id"], f"{row['app_code']}: {row['name']}")
    generate_alerts(conn)
    conn.commit()
    return jsonify(ok=True)


# ---------- alerts ----------
@app.get("/api/alerts")
@auth()
def list_alerts():
    resolved = 1 if request.args.get("resolved") == "1" else 0
    rows = g.conn.execute(
        "SELECT al.*, a.app_code, i.name AS institution_name FROM alerts al "
        "JOIN applications a ON a.id = al.application_id JOIN institutions i ON i.id = a.institution_id "
        "WHERE al.resolved = ?" + scope() +
        " ORDER BY CASE al.severity WHEN 'High' THEN 0 ELSE 1 END, al.id DESC", (resolved,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/alerts/refresh")
@auth("admin", "official")
def refresh_alerts():
    result = generate_alerts(g.conn)
    audit(g.conn, g.user["name"], "Alert engine run", None, str(result))
    g.conn.commit()
    return jsonify(result)


@app.post("/api/alerts/<int:alert_id>/resolve")
@auth("admin", "official")
def resolve_alert(alert_id):
    cur = g.conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
    if cur.rowcount == 0:
        return jsonify(error="Alert not found"), 404
    audit(g.conn, g.user["name"], "Alert resolved manually", None, f"alert #{alert_id}")
    g.conn.commit()
    return jsonify(ok=True)


# ---------- institutions & audit ----------
@app.get("/api/institutions")
@auth("admin", "official")
def list_institutions():
    rows = g.conn.execute(
        "SELECT i.*, COUNT(a.id) AS applications, SUM(a.status = 'In Progress') AS active "
        "FROM institutions i LEFT JOIN applications a ON a.institution_id = i.id GROUP BY i.id").fetchall()
    return jsonify([dict(r, active=r["active"] or 0) for r in rows])


@app.get("/api/audit")
@auth("admin", "official")
def audit_log():
    rows = g.conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        from seed import seed
        print("First run: creating demo database ->", seed())
    app.run(debug=True, port=5000)
