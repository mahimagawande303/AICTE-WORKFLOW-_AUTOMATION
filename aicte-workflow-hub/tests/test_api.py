"""Run from the project root:  python -m unittest discover -s tests -v
Uses a temporary database, so your real aicte.db is never touched."""
import os
import sys
import tempfile
import unittest

# Must be set BEFORE importing the backend modules.
_tmp = tempfile.mkdtemp()
os.environ["AICTE_DB"] = os.path.join(_tmp, "test.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import app  # noqa: E402
from ai import risk_score  # noqa: E402
from seed import seed  # noqa: E402


def login(client, email, password="demo123"):
    r = client.post("/api/login", json={"email": email, "password": password})
    return r, ({"Authorization": "Bearer " + r.get_json()["token"]} if r.status_code == 200 else {})


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.c = app.test_client()
        _, cls.admin = login(cls.c, "admin@demo.com")
        _, cls.inst = login(cls.c, "institution1@demo.com")

    def test_login_wrong_password(self):
        r, _ = login(self.c, "admin@demo.com", "wrong")
        self.assertEqual(r.status_code, 401)

    def test_login_ok(self):
        r, _ = login(self.c, "admin@demo.com")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["user"]["role"], "admin")

    def test_requires_login(self):
        self.assertEqual(self.c.get("/api/dashboard").status_code, 401)

    def test_institution_sees_only_own_applications(self):
        apps = self.c.get("/api/applications", headers=self.inst).get_json()
        self.assertTrue(len(apps) > 0)
        self.assertTrue(all(a["institution_id"] == 1 for a in apps))

    def test_institution_cannot_open_audit_or_advance(self):
        self.assertEqual(self.c.get("/api/audit", headers=self.inst).status_code, 403)
        self.assertEqual(self.c.post("/api/applications/1/advance", headers=self.inst).status_code, 403)

    def test_dashboard_numbers_are_consistent(self):
        d = self.c.get("/api/dashboard", headers=self.admin).get_json()
        self.assertEqual(d["total"], d["in_progress"] + d["approved"] + d["rejected"])
        self.assertEqual(sum(d["stage_counts"].values()), d["in_progress"])

    def test_workflow_and_compliance_gate(self):
        r = self.c.post("/api/applications", headers=self.admin, json={"type": "Renewal", "institution_id": 2})
        self.assertEqual(r.status_code, 201)
        app_id = r.get_json()["id"]
        adv = lambda body=None: self.c.post(f"/api/applications/{app_id}/advance", headers=self.admin, json=body or {})

        self.assertEqual(adv().status_code, 200)            # Submitted -> Scrutiny
        blocked = adv()                                      # documents still Pending
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("Pending documents", blocked.get_json()["error"])

        detail = self.c.get(f"/api/applications/{app_id}", headers=self.admin).get_json()
        for d in detail["documents"]:
            r = self.c.post(f"/api/documents/{d['id']}/status", headers=self.admin,
                            json={"status": "Verified", "expiry_date": "2099-01-01"})
            self.assertEqual(r.status_code, 200)
        self.assertEqual(adv().status_code, 200)            # Scrutiny -> EVC
        self.assertEqual(adv().status_code, 200)            # EVC -> Committee
        self.assertEqual(adv().status_code, 200)            # Committee -> Final Decision
        self.assertEqual(adv().status_code, 400)            # needs a decision
        self.assertEqual(adv({"decision": "Approved"}).status_code, 200)
        final = self.c.get(f"/api/applications/{app_id}", headers=self.admin).get_json()
        self.assertEqual(final["application"]["status"], "Approved")

    def test_institution_cannot_verify_documents(self):
        docs = self.c.get("/api/documents", headers=self.inst).get_json()
        r = self.c.post(f"/api/documents/{docs[0]['id']}/status", headers=self.inst, json={"status": "Verified"})
        self.assertEqual(r.status_code, 403)

    def test_alert_engine_is_idempotent(self):
        self.c.post("/api/alerts/refresh", headers=self.admin)
        second = self.c.post("/api/alerts/refresh", headers=self.admin).get_json()
        self.assertEqual(second["created"], 0)


class RiskScoreTests(unittest.TestCase):
    def test_high_risk_case(self):
        app_row = {"status": "In Progress", "current_stage": "Scrutiny", "stage_entered_on": "2026-01-01"}
        docs = [{"name": "A", "status": "Verified", "expiry_date": "2020-01-01"},
                {"name": "B", "status": "Pending", "expiry_date": None},
                {"name": "C", "status": "Pending", "expiry_date": None},
                {"name": "D", "status": "Pending", "expiry_date": None}]
        from datetime import date
        r = risk_score(app_row, docs, today=date(2026, 1, 20))  # 19 days in a 7-day stage
        self.assertEqual(r["level"], "High")
        self.assertLessEqual(r["score"], 100)
        self.assertTrue(len(r["reasons"]) >= 3)

    def test_clean_case_is_low(self):
        app_row = {"status": "In Progress", "current_stage": "EVC", "stage_entered_on": "2026-01-10"}
        docs = [{"name": "A", "status": "Verified", "expiry_date": "2099-01-01"}]
        from datetime import date
        self.assertEqual(risk_score(app_row, docs, today=date(2026, 1, 11))["level"], "Low")


if __name__ == "__main__":
    unittest.main()
