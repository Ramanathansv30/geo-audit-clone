# CLAUDE.md

## Project

A local clone of Geoptie's Free GEO Audit page. SPEC.md is the source of truth: read it before every task and follow it exactly. If the spec is unclear or seems wrong, stop and ask; don't guess.

## Who I am

I'm an intern and this is my first project. After each piece of work, explain in simple words what you built and why, so I can understand and present it.

## How to work

- Work on only what the current prompt asks.
- Before writing code for a larger change, give a short plan (files and what each will do) and wait for my OK.
- Keep code simple and readable. Use clear names and small functions, with a docstring on each public function. Avoid clever tricks.
- Reuse existing helpers (for example `scoring.band`, `checks._deduct`, `issues.make_issue`, `extractor.normalize`, the `Pill` and `IssueItem` components) instead of writing new ones.
- Put every number (weights, points, thresholds, timeouts) in `backend/config.py`. Never hard-code them in logic.
- Don't add libraries beyond SPEC.md section 2 without asking.
- Don't build anything listed as out of scope in SPEC.md section 1.
- No LLM/AI API calls and no API keys anywhere.
- No emojis in code, UI text or docs.

## Commands

Windows PowerShell 5.1 does not support `&&`; run the commands below on separate lines.

Backend (from `backend/`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
pytest -q
```

Frontend (from `frontend/`):

```powershell
npm install
npm run dev                           # http://localhost:5173
```

## Rules for tests

- Tests must not hit the real internet. Use HTML fixture files and mock httpx (see `tests/conftest.py`: `mock_http_client` and the `api` fixture).
- Run `pytest -q` after every backend change and show the result.
- Never weaken or delete a test just to make it pass. If a test and the spec disagree, tell me.

## Git

- Suggest a commit message at the end of each piece of work. Don't push.
- Keep `.venv/`, `node_modules/`, `__pycache__/`, `.env` in `.gitignore`.
