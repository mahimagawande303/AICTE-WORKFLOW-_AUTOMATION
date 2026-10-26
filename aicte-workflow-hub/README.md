# AICTE Workflow Hub (Hackathon Prototype)

Approval workflow automation + compliance monitoring + alert management.
**All data is synthetic demo data. This is not an official AICTE system and uses no AICTE API.**
Full explanation (problem, architecture, AI, pitch, Q&A): see `GUIDE.md`.

## Run in VS Code (Windows / Mac / Linux)

1. Install Python 3.10+ (check: `python --version`) and VS Code. Open this folder in VS Code (File > Open Folder).
2. Open the terminal in VS Code (Ctrl + `) and create a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. Install Flask: `pip install -r requirements.txt`
4. Start the app: `cd backend` then `python app.py`
   (first run auto-creates `aicte.db` with demo data)
5. Open http://127.0.0.1:5000 in your browser.

Reset demo data any time: `cd backend` then `python seed.py`.

## Demo logins (password for all: `demo123`)
| Email | Role | Can do |
|---|---|---|
| admin@demo.com | admin | everything |
| official1@demo.com | official | move stages, verify documents, resolve alerts |
| institution1@demo.com | institution | only its own applications; create application, upload (simulated) documents |

## Run tests
From the project root: `python -m unittest discover -s tests -v`

## Folder map
```
backend/db.py      schema, stages, SLA days, required documents
backend/seed.py    synthetic data generator
backend/ai.py      risk score + completion-date estimate
backend/engine.py  alert engine
backend/app.py     Flask REST API
frontend/          index.html, style.css, app.js (no build step)
tests/test_api.py  automated tests
```
