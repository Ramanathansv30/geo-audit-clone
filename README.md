# GEO Audit Clone

A local clone of the main feature of [Geoptie's Free GEO Audit](https://geoptie.com/free-geo-audit). Paste a page URL, click **Analyze**, and get:

- an overall GEO score from 0 to 100, with a label (Excellent, Good, Needs work, Poor)
- 6 dimension scores, each with sub-scores and issues
- which AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot) robots.txt allows
- the top 5 fixes, ranked by impact versus effort

All scoring uses fixed, documented rules. There are no AI/LLM calls and no API keys. The full specification is in [SPEC.md](SPEC.md).

## Project structure

```
geo-audit-clone/
├── backend/     Python FastAPI service that fetches and scores a page
│   ├── main.py        routes, CORS, error handling
│   ├── audit.py       the audit pipeline shared by the API and the benchmarks
│   ├── benchmarks.py  live comparison values from reference sites
│   ├── crawler.py     URL validation, page and robots.txt fetching
│   ├── extractor.py   HTML -> PageFacts
│   ├── checks.py      sub-score rules and issue detection
│   ├── issues.py      issue catalog
│   ├── scoring.py     weighted scores, labels, report assembly
│   ├── config.py      every weight, threshold and limit
│   ├── models.py      API request and report models
│   └── tests/         pytest suite (no real network access)
└── frontend/    React + Vite single page app
```

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer

## Run the backend

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Check it at http://localhost:8000/api/health (should return `{"status":"ok"}`). Interactive API docs are at http://localhost:8000/docs.

## Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To point the frontend at a different backend, set `VITE_API_URL` (for example in `frontend/.env.local`: `VITE_API_URL=http://localhost:9000`).

## Run the tests

```bash
cd backend
pytest -q
```

The tests use HTML fixtures and a mocked HTTP transport, so they never touch the internet. They include the reference scoring example from SPEC.md section 5.8.

## API

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/health` | none | `{"status": "ok"}` |
| POST | `/api/audit` | `{"url": "example.com/page"}` | Report JSON (SPEC.md section 7) |
| GET | `/api/benchmarks` | none | Comparison values (SPEC.md section 5.6) |

Errors always come back as `{"detail": "message"}`:

| Status | When |
|---|---|
| 400 | Invalid address, non-http(s) scheme, or malformed request body |
| 502 | Not an HTML page, page over 5 MB, or the site could not be reached |
| 504 | The page took longer than 15 seconds |

## How the score is calculated

1. **Fetch**: the backend downloads the page (15 s limit, 5 MB limit, up to 5 redirects) and the site's robots.txt.
2. **Extract**: it reads the title, meta tags, headings, JSON-LD structured data, dates, and the main content (navigation, sidebars and page-level header/footer are ignored).
3. **Check**: each of the 6 dimensions has 2 or 3 sub-scores from 0 to 100, produced by fixed rules:

| Dimension | Weight | Sub-scores |
|---|---|---|
| Answer First Content | 20% | FAQ / question headings, short intro answer, lists & tables |
| Technical Optimization | 20% | crawlability (status, noindex, AI bots), structured data & meta, page speed |
| Citation Authority | 15% | author signals, outbound sources, numbers & facts |
| AI Comprehension | 15% | heading structure, readability (Flesch), page identity |
| Content Freshness | 15% | dates present, recency |
| Content Depth | 15% | word count, image alt text |

4. **Score**: a dimension score is the weighted average of its sub-scores (sub-scores that can't be measured, such as alt text on a page with no images, are skipped). The overall score is the weighted average of the dimensions. A page is "GEO-Ready" at 70 or above.
5. **Prioritise**: every failed rule becomes an issue with a severity and an effort. Priority is severity points divided by effort cost, and the top 5 become "Fix these first".

## Comparison values (benchmarks)

The "Reference average" and "Top reference sites" numbers are calculated live, without a database:

- The first call to `GET /api/benchmarks` audits the 10 reference pages listed in `BENCHMARK_SITES` in `config.py`, using the same rules as any audit, and caches the result in memory for 24 hours. The frontend makes this call when the page loads.
- **Reference average** is the mean score of the sites that succeeded. **Top reference sites** is the mean of the best 25% of them.
- Sites that fail, or don't return HTTP 200, are skipped. If fewer than 5 succeed (for example, offline), the last good values are kept.
- The first calculation takes about 20 seconds; later calls are instant. While it runs, the comparison strip shows "*Loading comparison values...".

These numbers depend on which sites are in the list, so they are a reference point, not a true industry average. Edit `BENCHMARK_SITES` to compare against a different set.

## Deploy to Vercel

The repository is set up for [Vercel Services](https://vercel.com/docs/services) (currently in beta): `vercel.json` defines a `frontend` service (the Vite app) and a `backend` service (the FastAPI app, `main:app`), and sends `/api/*` requests to the backend.

1. Push the repository to GitHub.
2. In Vercel, choose **Add New... > Project**, import the repository, and click **Deploy**. Leave Root Directory as the repository root (where `vercel.json` is).
3. Open the deployment URL and run an audit.

The readability check needs the CMU pronouncing dictionary. It is included in `backend/nltk_data/`, so nothing is downloaded at runtime.

On Vercel the backend runs Python 3.12 (from `backend/.python-version`) and installs `backend/requirements.txt`. The frontend calls the API on the same domain, so no CORS settings or environment variables are needed.

## Known limitations

- Sites behind bot protection (for example Cloudflare) often return 403 to the crawler, which shows up as a "Page returned HTTP 403" issue.
- Pages that build their content with JavaScript are analysed as served, so they may look thin.
- Readability uses the English Flesch formula.
