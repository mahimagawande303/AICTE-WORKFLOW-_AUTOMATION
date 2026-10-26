# AICTE Workflow Hub: Complete Hackathon Guide (Hinglish)

> **Important honesty note:** Problem statement ka "Description" field khali tha. Isliye neeche ki saari requirements meri *assumptions* hain, title ke basis par. AICTE ke asli rules, SLA days aur document lists kuch bhi official nahi hain. Presentation me bolna: "demo rules, configurable".

---

## 1. Problem statement in simple Hinglish

**Title:** Integrated AICTE Approval Workflow Automation, Compliance Monitoring and Alert Management System

Simple matlab: Colleges AICTE se approval (naya college, renewal, expansion) lete hain. Ye process kaafi steps aur documents ka hota hai. Hume ek **ek jagah wala system** banana hai jo:
1. Approval process ko **automatic aur trackable** banaye (workflow automation),
2. Documents/rules follow ho rahe hain ya nahi, ye **dekhta rahe** (compliance monitoring),
3. Deadline miss ya document expire hone se pehle **chetavni de** (alert management).

## 2. Actual problem and root causes

| Problem | Root cause |
|---|---|
| Application kis stage me atki hai pata nahi | Status email/Excel/files me bikhra hota hai |
| Deadlines miss hoti hain | Koi automatic reminder ya SLA tracking nahi |
| Documents expire ho jaate hain (lease, certificate) | Expiry date koi track nahi karta |
| Incomplete application aage chali jaati hai | Stage badalte waqt checklist ka rule enforce nahi hota |
| "Kisne kya kab kiya?" ka jawab nahi | Audit trail nahi |
| Officials ko pata nahi pehle kaunsa case dekhna hai | Priority/risk ka concept nahi |

## 3. Target users and their difficulties

- **Institution (college) staff:** Kaunse documents baaki hain, status kya hai, bar-bar call karna padta hai.
- **AICTE official / scrutiny officer:** Bahut saari files, kaunsi urgent hai, manual follow-up.
- **Admin / senior authority:** Poore system ka overview, bottleneck kahan hai (e.g. EVC stage me 9 files ruki hain).

## 4. Proposed solution and how it works

Ek web portal jisme:
1. Institution **application banata hai** → system required documents ki checklist **khud banata hai**.
2. Application 5 stages se guzarti hai: **Submitted → Scrutiny → EVC → Committee → Final Decision**.
3. Har stage ke liye **time limit (SLA)** hai. Zyada time lagne par application "overdue" ho jaati hai.
4. **Compliance rule:** Scrutiny se EVC jaane se pehle sab documents Pending se bahar hone chahiye, warna system rok deta hai.
5. **Alert engine** overdue, expired, expiring-soon aur missing-document alerts banata hai (duplicate nahi banata, problem solve hone par auto-resolve karta hai).
6. **Risk score** batata hai kaunsi application sabse risky hai, aur *kyun*.
7. Har action **audit log** me save hota hai.

## 5. Unique selling points (USP)

- **Explainable risk score:** Sirf "High" nahi, har point ka reason dikhta hai (judges ko trust milta hai).
- **Compliance gate:** Rules system khud enforce karta hai, insaan ki yaad par depend nahi.
- **Self-resolving alerts:** Problem fix hote hi alert band; alert fatigue kam.
- **Completion-date forecast:** Past data ke average se expected finish date.
- **Role-based view:** College sirf apna data dekhta hai.
- **Zero-cost, simple stack:** Python + SQLite, install me 1 command.

## 6. AI/ML integration: kya hai, kya nahi

**Sach batana zaroori hai:** Prototype me **koi trained ML model nahi hai**.

| Feature | Status | Kaise kaam karta hai | AI kyun chahiye |
|---|---|---|---|
| Risk scoring | ✅ **Implemented** (rule-based, `ai.py`) | Overdue days, expired/expiring/pending docs ko points dekar 0-100 score | Officials ko priority list chahiye, 100 files manually nahi dekh sakte |
| Completion-date estimate | ✅ **Implemented** (statistics, `ai.py`) | Past completed stages ka average time + bache hue stages ka average | Applicants/officials ko realistic expectation |
| Smart alerts | ✅ **Implemented** (rules, `engine.py`) | Daily scan, dedupe, auto-resolve | Delay proactively pakadna |
| ML delay prediction | 🔶 Proposed | Real historical data par scikit-learn (e.g. gradient boosting) train karna | Rules se aage, hidden patterns |
| Document OCR + auto-verify | 🔶 Proposed | PDF/scan se expiry date aur certificate no. nikalna | Manual data entry hatana |
| LLM assistant (summary, "status batao") | 🔶 Proposed | Application ka summary, officer ko draft remarks | Time bachana |
| Anomaly detection (suspicious pattern) | 🔶 Proposed | Unusual approval speed / repeated rejections | Fraud/bias detection |

Rule-based se start karna isliye sahi hai kyunki **real data abhi nahi hai**, aur ML ko data chahiye hota hai.

## 7. Tech stack

| Layer | Choice | Kyun |
|---|---|---|
| Frontend | HTML + CSS + plain JavaScript | Beginner friendly, build step nahi |
| Backend | Python **Flask** | Chhota, samajhne me aasan |
| Database | **SQLite** | Install nahi karna padta, ek file |
| Auth | Signed token (`itsdangerous`) + password hash | Simple, secure basics |
| Tests | `unittest` (Python built-in) | Extra install nahi |

**API endpoints (sab implemented):**
`POST /api/login`, `GET /api/config`, `GET /api/dashboard`, `GET/POST /api/applications`, `GET /api/applications/<id>`, `POST /api/applications/<id>/advance`, `GET /api/documents`, `POST /api/documents/<id>/status`, `GET /api/alerts`, `POST /api/alerts/refresh`, `POST /api/alerts/<id>/resolve`, `GET /api/institutions`, `GET /api/audit`.

**Koi external API integrated nahi hai** (AICTE portal, email, SMS, payment: kuch nahi).

## 8. System architecture and user workflow

```
Browser (HTML/CSS/JS)
   │  fetch() JSON + Bearer token
   ▼
Flask API (app.py)  ── role check (admin / official / institution)
   ├── ai.py      risk score, completion estimate
   ├── engine.py  alert generation + auto-resolve
   └── db.py      SQLite (aicte.db)
```

**Workflow:**
1. Institution login → "New Application" (type choose) → system documents ki checklist banata hai.
2. Institution documents "upload" karta hai (prototype me sirf status badalta hai, real file upload nahi).
3. Official application ko Scrutiny me le jaata hai → documents **Verify** karta hai.
4. Sab docs ok → "Move to next stage" chalta hai (warna 409 error + missing docs ke naam).
5. EVC → Committee → Final Decision me **Approved/Rejected** record hota hai.
6. Har step par audit log + alerts recompute.

## 9. Database schema and sample data

**Tables (7):** `institutions`, `users`, `applications`, `stage_history`, `documents`, `alerts`, `audit_log` (exact SQL: `backend/db.py`).

```
applications(id, app_code, institution_id→institutions, type, current_stage, status,
             submitted_on, stage_entered_on, assigned_to→users)
stage_history(id, application_id→applications, stage, entered_on, completed_on)
documents(id, application_id→applications, name, status[Pending|Submitted|Verified],
          submitted_on, expiry_date)
alerts(id, application_id, kind, severity, message, dedupe_key UNIQUE, created_on, resolved)
```

**Sample data (SYNTHETIC, `seed.py` se random generate, seed=42):** 10 made-up institutions (naam me Demo/Sample/Test), 4 users, 36 applications, unke documents aur stage history. Ek real generated example:

> APP-2026-018 · Demo Polytechnic Institute · Re-scrutiny · stage EVC (26 din, limit 14) · documents: Faculty List (Verified, 5 din me expire), Building Plan (Pending) → risk **53 / Medium**.

Data ki dates *aaj ki date ke relative* banti hain, isliye alerts hamesha demo me dikhte hain.

## 10. UI/UX design and pages

Aapke 12-screen concept me se ye **implemented** hain:

| Page | Status |
|---|---|
| Login (demo account buttons ke saath) | ✅ |
| Dashboard (KPIs, donut, stage bars, top-risk table) | ✅ |
| Applications list (search + filters, new application) | ✅ |
| Application Details + Workflow stepper + risk + forecast | ✅ (concept ke screen 4 aur 5 ek page me) |
| Compliance & Documents | ✅ |
| Alerts | ✅ (list + run engine + resolve) |
| Institutions | ✅ |
| Audit Log | ✅ |
| Workflow Rules | ✅ read-only |
| Workflow **Configuration editor** | 🔶 Proposed |
| Reports & Analytics (exportable) | 🔶 Proposed |
| User Profile & Settings (notification preferences) | 🔶 Proposed |

**UX principles:** consistent navy/blue theme, status colours (green/amber/red), ek page par ek kaam, error toast messages, mobile par sidebar upar aa jaata hai (basic responsive; poori tarah mobile-tested nahi).

## 11. Development roadmap (step by step)

1. **Din 1:** Requirements + database schema + seed data.
2. **Din 2:** Flask API (login, applications, advance) + tests.
3. **Din 3:** Documents + alert engine + risk score.
4. **Din 4:** Frontend pages (login → dashboard → list → detail).
5. **Din 5:** Compliance, alerts, audit pages; polish.
6. **Din 6:** Testing, README, demo rehearsal, slides.

Beginner tip: Pehle API ko tests/curl se chalao, **phir** frontend banao.

## 12. Complete code (file by file)

Saara code zip me hai. Har file ka kaam:

| File | Kaam |
|---|---|
| `backend/db.py` | Tables, stages, SLA, required docs |
| `backend/seed.py` | Synthetic data banata hai |
| `backend/ai.py` | `risk_score()`, `predict_completion()` |
| `backend/engine.py` | `generate_alerts()` |
| `backend/app.py` | Saare API routes + login + role checks |
| `frontend/index.html` | Page shell |
| `frontend/style.css` | Styling |
| `frontend/app.js` | Pages, routing, buttons |
| `tests/test_api.py` | 11 automated tests |

**Code samajhne ke 3 important concepts:**
- **REST API:** Browser server se JSON maangta hai (`/api/applications`), server JSON deta hai.
- **Token auth:** Login ke baad server ek signed token deta hai; har request me bheja jaata hai taaki server pehchane.
- **Dedupe key:** Alert ka unique naam (e.g. `OVERDUE:18:EVC`) taaki same alert dobara na bane.

## 13. Run in VS Code

Step-by-step `README.md` me hai. Short version:
```
python -m venv venv
venv\Scripts\activate        (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
cd backend
python app.py
```
Phir browser me `http://127.0.0.1:5000`. Login: `admin@demo.com` / `demo123`.

**Common errors:** `python not found` → Python install karke "Add to PATH" tick karo. `Address already in use` → port 5000 par dusra app chal raha hai, band karo. Login fail → `python seed.py` chalao.

## 14. Testing and *actual* outputs

**Maine ye chalaya aur ye result aaya:**

- `python -m unittest discover -s tests -v` → **Ran 11 tests ... OK** (login, role access, institution data isolation, dashboard consistency, full workflow with compliance gate, risk scoring, alert idempotency).
- Headless Chromium se real app chalayi: login → dashboard → applications → detail → alerts pages khule, **browser console me 0 errors**. Detail page par "Move to next stage" click karne par toast aaya: `APP-2026-018 moved EVC -> Committee`.
- Seeded dashboard numbers (is run me): total 36, in progress 23, approved 10, rejected 3, overdue 9, expiring docs 5, open alerts 28.

**Jo test NAHI hua:** Firefox/Safari, asli mobile phone, load/performance, security audit, bahut saare users ek saath. Isko "tested" mat bolna.

**Aap khud kaise test karo (demo checklist):**
1. Admin se login → dashboard dekho.
2. New Application banao → Scrutiny me move karo → dobara move karne par **rok** dikhna chahiye (pending docs).
3. Documents Verify karo → ab move ho jaana chahiye.
4. Institution account se login → sirf apni applications dikhengi, Audit Log menu nahi.

## 15. Limitations, challenges, future scope

**Limitations (honest):**
- Synthetic data, official AICTE rules/SLA nahi.
- Real file upload nahi (sirf status change). Email/SMS alerts nahi.
- ML model nahi; risk score rules par hai, weights hamari assumption.
- SQLite + Flask dev server: production ke liye nahi. Secret key demo wali hai.
- Alert engine tab chalta hai jab koi action ho ya "Run alert engine" dabao; automatic daily scheduler nahi.
- Workflow rules code me fixed hain (UI se editable nahi).

**Challenges:** real data access, AICTE portal integration permissions, document verification trust, data privacy.

**Future scope:** real file upload + OCR, email/SMS/WhatsApp alerts, scheduler (daily scan), ML delay prediction jab data mile, admin workflow editor, reports export (PDF/Excel), multi-language (Hindi), PostgreSQL + deployment, SSO/DigiLocker-type integration (sirf agar official access mile).

## 16. Hackathon presentation script (5 minutes) + Judge Q&A

**Script**
1. **(30s) Problem:** "Approval files kai stages me atakti hain, documents expire ho jaate hain, aur kisi ko pata nahi kaun si file risky hai."
2. **(30s) Solution:** "AICTE Workflow Hub: workflow + compliance + alerts ek jagah."
3. **(2 min) Live demo:** Dashboard → ek high-risk application kholo, reasons dikhao → move karne ki koshish, system rok de (compliance gate) → document verify → move ho jaaye → Alerts page → institution login se role-based view.
4. **(45s) Smart features:** "Risk score explainable hai, har point ka reason dikhta hai. Alerts khud resolve hote hain."
5. **(30s) Honesty:** "Data synthetic hai, rules assumed aur configurable hain. ML next phase hai jab real data milega."
6. **(30s) Future + ask:** Real data pilot, notifications, ML.

**Judge Q&A**

- **Q: Isme AI kahan hai?** A: Abhi explainable rule-based risk scoring aur statistical forecast hai. Trained ML real historical data milne ke baad planned hai. Rules se start isliye kiya kyunki data nahi hai aur officials ko reasons chahiye.
- **Q: Data real hai?** A: Nahi, synthetic hai (fixed seed se generate), institutions ke naam bhi made-up hain.
- **Q: AICTE ke asli rules follow karte ho?** A: Problem statement me details nahi thi; stages, SLA aur document lists assumed hain aur ek jagah configure hoti hain.
- **Q: Security kaisi hai?** A: Password hashing, signed tokens, role-based access aur institution data isolation implemented hain. Production ke liye HTTPS, secret management, rate limiting, audit chahiye; security audit nahi hua.
- **Q: Scale karega?** A: Prototype SQLite par hai. Production me PostgreSQL, background scheduler aur proper server lagega.
- **Q: Alert kaise bhejte ho?** A: Abhi in-app. Email/SMS integration proposed hai.
- **Q: Duplicate alerts?** A: Unique dedupe key se nahi banti; aur problem solve hote hi auto-resolve.
- **Q: Existing system se alag kya?** A: Ek jagah workflow + compliance gate + explainable risk + auto-resolving alerts.
- **Q: Aage kya?** A: Real document upload + OCR, notifications, scheduler, ML, admin rule editor.
