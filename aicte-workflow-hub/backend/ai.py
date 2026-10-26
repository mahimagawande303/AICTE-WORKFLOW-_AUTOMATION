"""'Smart' features of the prototype.

HONEST NOTE: nothing here is a trained machine-learning model.
1. risk_score()          -> transparent rule-based scoring (every point is explained).
2. predict_completion()  -> simple statistics (average of past stage durations).
A real ML model (e.g. scikit-learn) is a *proposed* future step once real data exists.
"""
from datetime import date, datetime, timedelta

from db import SLA_DAYS, STAGES


def to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def days_in_stage(app, today=None):
    today = today or date.today()
    return (today - to_date(app["stage_entered_on"])).days


def risk_score(app, docs, today=None):
    """Return {score 0-100, level, reasons[]} for one application."""
    today = today or date.today()
    if app["status"] != "In Progress":
        return {"score": 0, "level": "Low", "reasons": ["Application is already closed"]}

    score, reasons = 0, []
    stage = app["current_stage"]
    used, sla = days_in_stage(app, today), SLA_DAYS[stage]

    if used > sla:
        over = used - sla
        pts = min(40, 10 + 3 * over)
        score += pts
        reasons.append(f"{over} day(s) over the {sla}-day limit in {stage} stage (+{pts})")
    elif used >= 0.8 * sla:
        score += 10
        reasons.append(f"{used} of {sla} allowed days used in {stage} stage - deadline is close (+10)")

    expired, expiring = [], []
    for d in docs:
        if d["expiry_date"]:
            delta = (to_date(d["expiry_date"]) - today).days
            if delta < 0:
                expired.append(d["name"])
            elif delta <= 30:
                expiring.append(d["name"])
    if expired:
        pts = min(30, 15 * len(expired))
        score += pts
        reasons.append(f"Expired document(s): {', '.join(expired)} (+{pts})")
    if expiring:
        pts = min(10, 5 * len(expiring))
        score += pts
        reasons.append(f"Document(s) expiring within 30 days: {', '.join(expiring)} (+{pts})")

    pending = [d["name"] for d in docs if d["status"] == "Pending"]
    if pending and stage != "Submitted":
        pts = min(24, 8 * len(pending))
        score += pts
        reasons.append(f"Document(s) still pending: {', '.join(pending)} (+{pts})")

    score = min(score, 100)
    level = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    if not reasons:
        reasons.append("No risk factors found")
    return {"score": score, "level": level, "reasons": reasons}


def predict_completion(conn, app, today=None):
    """Estimate the finish date from the average duration of past completed stages."""
    today = today or date.today()
    if app["status"] != "In Progress":
        return None
    rows = conn.execute(
        "SELECT stage, AVG(julianday(completed_on) - julianday(entered_on)) AS avg_days, COUNT(*) AS n "
        "FROM stage_history WHERE completed_on IS NOT NULL GROUP BY stage"
    ).fetchall()
    stats = {r["stage"]: (r["avg_days"], r["n"]) for r in rows}

    def estimate(stage):
        avg, n = stats.get(stage, (None, 0))
        return (avg, n) if n >= 3 else (float(SLA_DAYS[stage]), 0)  # fallback to SLA

    idx = STAGES.index(app["current_stage"])
    cur_avg, cur_n = estimate(app["current_stage"])
    remaining = max(cur_avg - days_in_stage(app, today), 1)
    samples = [cur_n]
    for s in STAGES[idx + 1:]:
        avg, n = estimate(s)
        remaining += avg
        samples.append(n)
    return {
        "expected_date": (today + timedelta(days=round(remaining))).isoformat(),
        "remaining_days": round(remaining),
        "method": "Average of past completed stages (SLA used if fewer than 3 samples)",
        "min_samples": min(samples),
    }
