# GEO Audit Clone: Specification

This is the single source of truth for the project. If something isn't written here, ask before inventing it.

## 1. Goal

A local clone of the main feature of https://geoptie.com/free-geo-audit:

- The user pastes a page URL and clicks Analyze.
- They see a loading card with 5 steps.
- They get a report: an overall GEO score (0-100), 6 dimension scores with sub-scores and issues, AI-bot access, and the top 5 fixes.
- It runs on a laptop only. All scoring is done with fixed rules: no AI/LLM calls, no API keys.

### Out of scope (do NOT build)

- Nav items: Free tools, Resources, Pricing, Get a Demo, Get Started, language switch
- "More free GEO tools" section
- Sign-up wall, "Unlock report", weekly tracking, upsells
- Big footer with link lists
- Database, job queue, Docker, auth, deployment, LLM calls

## 2. Tech stack

| Part | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| HTTP | httpx (async) |
| HTML parsing | beautifulsoup4 + lxml |
| robots.txt | protego |
| Readability | textstat |
| Tests | pytest, pytest-asyncio |
| Frontend | React + Vite (JavaScript, not TypeScript), plain CSS, no UI library |

Use no other libraries unless asked. JSON-LD is parsed with BeautifulSoup + Python's json module.

## 3. Folder structure

```
geo-audit-clone/
├── SPEC.md
├── CLAUDE.md
├── README.md
├── vercel.json            # Vercel deployment: frontend + backend services, /api routing
├── backend/
│   ├── main.py            # FastAPI app, CORS, routes, error handlers
│   ├── audit.py           # the audit pipeline: validate -> fetch -> extract -> checks -> report
│   ├── benchmarks.py      # live comparison values from reference sites (section 5.6)
│   ├── models.py          # Pydantic models for the report (section 7)
│   ├── crawler.py         # URL validation, fetch page + robots.txt, return FetchResult
│   ├── extractor.py       # HTML -> PageFacts (section 4)
│   ├── checks.py          # sub-score rules + issues (sections 5 and 6)
│   ├── issues.py          # issue catalog (section 6)
│   ├── scoring.py         # weighted averages, labels, priority, report assembly
│   ├── config.py          # ALL weights, points, thresholds, benchmark sites and fallback values
│   ├── requirements.txt   # runtime libraries (installed on Vercel)
│   ├── requirements-dev.txt # runtime + test libraries (local development)
│   ├── .python-version    # 3.12, the Python version used on Vercel
│   ├── nltk_data/         # CMU pronouncing dictionary used by textstat (bundled, never downloaded)
│   ├── pytest.ini
│   └── tests/
│       ├── conftest.py    # shared fixtures and helpers
│       ├── fixtures/      # small hand-written HTML files
│       ├── test_extractor.py
│       ├── test_checks.py
│       ├── test_scoring.py
│       ├── test_benchmarks.py
│       └── test_api.py
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── labels.js       # label -> CSS class helper shared by components
        ├── styles.css
        └── components/
            Header.jsx, Hero.jsx, PlatformStrip.jsx, LoadingCard.jsx,
            ResultHeader.jsx, ScoreRing.jsx, ComparisonStrip.jsx,
            DimensionCard.jsx, BotAccess.jsx, TopFixes.jsx, IssueItem.jsx,
            Pill.jsx, HowItWorks.jsx, Faq.jsx, Footer.jsx
```

## 4. Backend pipeline

### 4.1 URL validation

- Trim whitespace. If the input does not contain `://`, prepend `https://`. (Do not rely on `urlparse` to detect a scheme: it reads `example.com:8080` as scheme `example.com`.)
- The scheme must be http or https, and the URL must have a hostname that contains a dot and no whitespace. Otherwise return HTTP 400 with `{"detail": "Please enter a valid web address"}`.
- Other schemes (ftp, file, ...): 400 with `{"detail": "Only http and https links work"}`.
- A request body that is missing `url` or is not valid JSON also returns 400 with `{"detail": "Please enter a valid web address"}` (never FastAPI's default 422 list).

### 4.2 Fetch (`crawler.py`)

- One shared `httpx.AsyncClient` is created at app startup with `follow_redirects=True`, `max_redirects=5`, a 15 s timeout, and User-Agent `GEOAuditClone/1.0 (local intern project)`. The client is provided to the route through a FastAPI dependency so tests can replace it with one that uses `httpx.MockTransport`.
- The 15 s limit is a total deadline for the main page fetch (headers and body), enforced with `asyncio.wait_for`, because httpx timeouts apply per operation.
- If the content-type does not contain `text/html`, return 502 with "This link isn't a web page" (checked before reading the body).
- Stream the body and stop if it exceeds 5 MB. Then return 502 with "This page is too large to analyze".
- Measure `elapsed_seconds` for the main page fetch (start of request to end of body).
- On timeout, return 504 with "Couldn't reach this page (timed out after 15 s)".
- On any other httpx error (connection error, too many redirects, protocol error, decoding error), return 502 with "Couldn't reach this page".
- Non-200 final status is not an error. Keep it; it affects crawlability.
- Fetch robots.txt from `{scheme}://{host}/robots.txt` of the **final** URL, with a 5 s timeout. A non-200 response or any failure gives `robots_txt = None`, which means everything is allowed.
- Return a FetchResult: requested_url, final_url, status_code, headers, html, elapsed_seconds, robots_txt.

### 4.3 Extract facts (`extractor.py`)

Text values are stripped and whitespace-collapsed. An empty value counts as missing (None).

Return a PageFacts dataclass with:

- `title`: `<title>` text, or None
- `meta_description`: `<meta name="description">` content, or None
- `meta_robots`: lowercased `<meta name="robots">` content plus the X-Robots-Tag header (joined), or ""
- `og_site_name`: `<meta property="og:site_name">` content, or None
- `headings`: list of (level:int, text:str) for h1-h6 in document order (from the full document)
- `json_ld`: list of dicts parsed from every `<script type="application/ld+json">`
  - Flatten top-level lists and `@graph` arrays into one list of objects.
  - Ignore blocks that fail to parse.
- `json_ld_nodes`: every JSON-LD object at any depth, including nested ones such as an Article's `publisher` or `author`. Used for `schema_types`, author, dates and identity.
- `schema_types`: set of all `@type` values (strings, or each item if a list) across `json_ld_nodes`
- Main content:
  - Work on a copy of the soup.
  - Remove script, style, noscript, nav, aside, svg, iframe everywhere.
  - Remove header and footer only when they are not inside a `<main>` or `<article>` (an article's own header usually holds its H1).
  - Do not remove `<form>` (some sites wrap the whole page in one).
  - Use the first `<main>` if present, else the first `<article>`, else `<body>`.
- `main_text`: text of main content, joined with spaces and whitespace collapsed
- `word_count`: number of whitespace-separated tokens in main_text
- `first_paragraph_words`: word count of the first non-empty `<p>` after the first `<h1>` of the main content, in document order. If the main content has no h1, use the first non-empty `<p>` in main content. 0 if none.
- `list_table_count`: count of ul, ol, table inside main content
- `outbound_domains`: set of hostnames (strip a leading `www.`) of absolute http(s) `<a href>` links in main content whose hostname differs from the page's final hostname (also stripped of `www.`)
- `number_count`: number of regex matches of `\b\d+(?:[.,]\d+)*%?` in main_text
- `images_total`, `images_with_alt`: `<img>` in main content; "with alt" means a non-empty alt after strip
- `has_author`: true if any of these exist in the full document:
  - `<meta name="author">` with content
  - a non-empty `author` key in any JSON-LD node
  - `a[rel=author]`
  - any element with `itemprop="author"`
- `date_published`, `date_modified`: datetimes or None. Candidates are tried in order and the first one that parses wins.
  - Published: JSON-LD `datePublished` values, `<meta property="article:published_time">`, then the first `<time datetime>`.
  - Modified: JSON-LD `dateModified` values, then `<meta property="article:modified_time">`.
  - Parse with `datetime.fromisoformat` after replacing a trailing Z with +00:00; this also accepts plain YYYY-MM-DD. Unparseable means skip to the next candidate. Treat naive datetimes as UTC.
- `is_https`: final URL scheme is https

## 5. Scoring rules

All numbers live in config.py. A sub-score is an int 0-100, or None meaning "not measurable, skip it".

Rounding everywhere: `round_half_up(x) = int(x + 0.5 + 1e-9)` for x >= 0. The tiny epsilon protects against floating-point results such as 62.49999999 that should be 62.5. Never use Python's round() for scores.

### 5.1 Dimensions and weights (overall)

| key | name | weight |
|---|---|---|
| answer_first | Answer First Content | 0.20 |
| technical | Technical Optimization | 0.20 |
| authority | Citation Authority | 0.15 |
| comprehension | AI Comprehension | 0.15 |
| freshness | Content Freshness | 0.15 |
| depth | Content Depth | 0.15 |

### 5.2 Sub-scores

**answer_first** (weights 1/3 each)

- faq (FAQ / question headings):
  - FAQ found -> 100. "FAQ found" means FAQPage is in schema_types, OR any heading text contains "faq" or "frequently asked" (case-insensitive).
  - Otherwise, count h2-h4 headings whose text ends with "?": 2+ -> 70, 1 -> 50, 0 -> 30.
- intro (Short intro answer): first_paragraph_words 20-80 -> 100; 81-150 -> 70; anything else (including 0) -> 40
- lists (Lists & tables): list_table_count 0 -> 40; 1-2 -> 70; 3+ -> 100

**technical** (crawlability 0.5, structured 0.3, speed 0.2)

- crawlability: start at 100.
  - status_code != 200: -50
  - "noindex" in meta_robots: -50
  - For each bot blocked by robots.txt (protego `can_fetch(final_url, bot)` is False): GPTBot -25, ClaudeBot -15, PerplexityBot -15, Google-Extended -15, CCBot -5
  - Minimum 0
- structured (Structured data & meta): start at 100.
  - no JSON-LD objects: -60
  - no title: -20
  - no meta description: -20
  - meta description longer than 160 characters: -10
  - Minimum 0
- speed (Page speed), from elapsed_seconds: < 1 -> 100; < 2 -> 80; < 4 -> 60; else 40

**authority** (author 0.4, sources 0.3, numbers 0.3)

- author (Author signals): start at 100.
  - not has_author: -40
  - schema_types has none of {Organization, Corporation, LocalBusiness, NewsMediaOrganization, Person}: -20
  - not is_https: -40
  - Minimum 0
- sources (Outbound sources): len(outbound_domains) 0 -> 30; 1-2 -> 60; 3+ -> 90
- numbers (Numbers & facts): number_count 0 -> 40; 1-4 -> 70; 5+ -> 100

**comprehension** (headings 0.4, readability 0.4, identity 0.2)

- headings (Heading structure): start at 100.
  - number of h1 != 1: -20
  - each skipped level (a heading whose level > previous heading level + 1; the first heading has no previous heading and never counts): -10 each, capped at -30 total
  - word_count > 500 and number of h2 < 2: -15
- readability: if word_count < 50, None. Otherwise f = `textstat.flesch_reading_ease(main_text)`:
  - f >= 60 -> 100
  - 30 <= f < 60 -> round_half_up(50 + (f - 30) / 30 x 50)
  - f < 30 -> 40
- identity (Page identity): title present +40; any h1 present +30; og_site_name present, or any JSON-LD node of type Organization/WebSite with a name, +30

**freshness** (dates 0.4, recency 0.6)

- dates (Dates present): 50 if date_published + 50 if date_modified
- recency: newest of the two dates, in whole days before now (UTC): <= 90 -> 100; <= 365 -> 75; <= 730 -> 50; older -> 25; no date -> 40

**depth** (words 0.6, alt 0.4)

- words (Word count): < 300 -> 40; 300-799 -> 70; 800+ -> 100
- alt (Image alt text): if images_total == 0, None. Otherwise round_half_up(100 x images_with_alt / images_total)

### 5.3 Dimension score

Weighted average of the non-None sub-scores, renormalising their weights: `round_half_up(sum(s*w) / sum(w))`. If all are None, the score is 0.

### 5.4 Overall score

`round_half_up(sum(dimension_score x dimension_weight))`. The weights sum to 1.0.

### 5.5 Labels

- 80-100 "Excellent"
- 60-79 "Good"
- 40-59 "Needs work"
- 0-39 "Poor"

`geo_ready = overall_score >= 70`.

### 5.6 Benchmarks

Benchmarks are computed live by auditing the reference pages in `config.BENCHMARK_SITES` with the same pipeline and rules as any other audit. No database is used; values are kept in memory.

- They are served by `GET /api/benchmarks`. The first request audits the reference sites (5 at a time) and caches the result in memory for 24 hours; concurrent requests share one computation. There is no background job, so this also works on serverless hosting.
- A site is skipped if the audit fails or the page does not return HTTP 200.
- `industry_average` = round_half_up(mean of all successful overall scores).
- `top_sites` = round_half_up(mean of the top 25% of those scores, rounded up in count; 10 sites -> top 3).
- `is_sample = false`, `sample_size` = number of successful sites, `updated_at` = UTC time of the calculation.
- If fewer than 5 sites succeed (or the computation errors), the previous values are kept and the next attempt waits 10 minutes. Before the first successful run, the endpoint returns the fallback sample values from config: `industry_average = 65`, `top_sites = 85`, `is_sample = true`, `sample_size = 0`, `updated_at = null`.
- These are averages of the chosen reference sites, not a true industry average, and the UI labels them that way.

### 5.7 Summary line

- If there is at least one issue: `"{label} overall. Biggest issue: {top_fixes[0].title}."`
- Otherwise: `"{label} overall. No major issues found."`

### 5.8 Reference example (must be a unit test in `test_scoring.py`)

Feed these sub-scores straight into the scoring functions.

| Dimension | Sub-scores | Expected score |
|---|---|---|
| answer_first | faq 50, intro 100, lists 70 | 73 |
| technical | crawlability 75, structured 30, speed 80 | 63 |
| authority | author 40, sources 60, numbers 70 | 55 |
| comprehension | headings 90, readability 87, identity 70 | 85 |
| freshness | dates 50, recency 75 | 65 |
| depth | words 70, alt 50 | 62 |

Expected overall: 67, label "Good", geo_ready false.
With crawlability changed to 100: technical 75, overall 70, geo_ready true.

The issues this example implies are: bot_blocked (GPTBot), no_structured_data, meta_description_too_long, no_faq, no_author, no_org_schema, skipped_heading_levels, images_missing_alt. Sorted, the top 5 must be: bot_blocked, no_author, no_structured_data, no_faq, meta_description_too_long.

## 6. Issues

Each issue has: id, dimension, title, explanation, how_to_fix, severity (High|Medium|Low), effort (Low|Medium|High), priority.

Severity points: High 3, Medium 2, Low 1. Effort cost: Low 1, Medium 2, High 3.

`priority = round(severity_points / effort_cost, 2)`. This is a display value; normal round is fine here.

Sort order for top fixes: priority desc, then severity points desc, then catalog order (the order of the table below). `top_fixes` = first 5.
Each dimension's issues list uses the same sort.

Catalog, in this exact order. `{...}` marks values to fill in.

| id | dimension | trigger | severity | effort | title |
|---|---|---|---|---|---|
| page_error | technical | status != 200 | High | Low | Page returned HTTP {status} |
| noindex | technical | noindex found | High | Low | Page is set to noindex |
| bot_blocked | technical | per blocked bot (one issue each) | High | Low | AI bot blocked: {bot} |
| not_https | authority | not https | High | Medium | Page is not using HTTPS |
| missing_title | technical | no title | Medium | Low | Missing page title |
| missing_meta_description | technical | no meta description | Medium | Low | Missing meta description |
| meta_description_too_long | technical | description > 160 chars | Low | Low | Meta description is {n} characters (keep under 160) |
| no_structured_data | technical | no JSON-LD | High | Medium | No structured data (JSON-LD) |
| slow_page | technical | elapsed >= 2 s | Low | High | Page is slow ({t} s to load) |
| no_faq | answer_first | faq sub-score <= 50 | Medium | Medium | No FAQ or question-style headings |
| long_intro | answer_first | intro sub-score < 100 | Low | Low | Opening paragraph doesn't give a short answer |
| no_lists | answer_first | list_table_count == 0 | Low | Low | No lists or tables |
| no_author | authority | not has_author | Medium | Low | No author shown |
| no_org_schema | authority | no org/person type | Low | Low | No Organization or Person structured data |
| no_outbound_sources | authority | 0 outbound domains | Low | Low | No links to outside sources |
| few_numbers | authority | number_count == 0 | Low | Medium | No numbers or facts to back up claims |
| h1_issue | comprehension | h1 count != 1 | Medium | Low | Page should have exactly one H1 (found {n}) |
| skipped_heading_levels | comprehension | >= 1 skipped level | Low | Low | Heading levels are skipped |
| few_subheadings | comprehension | > 500 words and < 2 h2 | Low | Low | Long page with few subheadings |
| hard_to_read | comprehension | Flesch < 30 (only when readability is measurable) | Low | Medium | Text is hard to read |
| no_dates | freshness | neither date | Medium | Low | No published or updated date |
| old_content | freshness | newest date > 365 days | Low | Medium | Content looks out of date |
| thin_content | depth | word_count < 300 | Medium | High | Thin content ({n} words) |
| images_missing_alt | depth | images_with_alt < images_total | Low | Low | {k} of {n} images have no alt text |

Write a short plain-English explanation and a concrete how_to_fix for each. Example for bot_blocked:

- explanation: "Your robots.txt blocks GPTBot, so ChatGPT can't read this page."
- how_to_fix: "Remove the Disallow rule for GPTBot in robots.txt."

## 7. API contract

CORS: allow origin http://localhost:5173.

`GET /api/health` returns `{"status": "ok"}`.

`POST /api/audit` takes body `{"url": "string"}`. It returns 200 with the Report below, or an error `{"detail": "message"}` with status 400, 502 or 504 (section 4).

`GET /api/benchmarks` returns the comparison values (section 5.6):

```json
{ "industry_average": 68, "top_sites": 82, "is_sample": false, "sample_size": 10, "updated_at": "2026-11-26T06:25:25Z" }
```

Report (all keys snake_case):

```json
{
  "url": "https://xyzsports.com/running-shoes",
  "final_url": "https://xyzsports.com/running-shoes",
  "title": "Running Shoes | XYZ Sports",
  "analyzed_at": "2026-11-24T10:00:00Z",
  "duration_seconds": 4.2,
  "overall_score": 67,
  "label": "Good",
  "geo_ready": false,
  "summary": "Good overall. Biggest issue: AI bot blocked: GPTBot.",
  "bot_access": [ { "bot": "GPTBot", "allowed": false }, { "bot": "ClaudeBot", "allowed": true } ],
  "dimensions": [
    {
      "key": "technical",
      "name": "Technical Optimization",
      "weight": 0.2,
      "score": 63,
      "label": "Good",
      "sub_scores": [
        { "key": "crawlability", "name": "Crawlability", "weight": 0.5, "score": 75, "detail": "robots.txt blocks GPTBot" }
      ],
      "issues": [ { "id": "bot_blocked", "dimension": "technical", "title": "AI bot blocked: GPTBot",
                    "explanation": "...", "how_to_fix": "...", "severity": "High", "effort": "Low", "priority": 3.0 } ]
    }
  ],
  "top_fixes": [ "...up to 5 Issue objects..." ]
}
```

More rules for the Report:

- `url` is the validated, normalised URL; `title` may be null.
- `analyzed_at` is UTC, to the second.
- `duration_seconds` is the total server-side audit time (validation to report), rounded to 1 decimal.
- `bot_access` lists all 5 bots, in this order: GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot.
- `dimensions` is always all 6, in the order of section 5.1.
- Each `detail` is a short human string explaining the sub-score (e.g. "2 lists/tables", "Flesch 52", "No images").

## 8. Frontend

One page with three states: landing -> loading -> results (plus an error message).

- **Header**: the text logo "GEO Audit" on the left. Nothing else.
- **Hero**:
  - Title "Free GEO Audit".
  - Subtitle "Analyze your website's readiness for AI search engines."
  - URL input (placeholder `https://example.com/your-page`) and an Analyze button. Enter submits.
  - The button is disabled while loading.
- **PlatformStrip**: the caption "Checks readiness across", then pills: ChatGPT, Perplexity, Claude, Gemini, Google AI (text pills, no logos).
- **LoadingCard**:
  - Shows "Analyzing" and the URL, a percentage, a progress bar, and 5 steps: Preparing analysis, Crawling website, Processing data, Analyzing content, Finalizing report.
  - On a timer, advance one step about every 1.2 s, raising the % (10, 35, 60, 90). Stay on "Analyzing content" until the response arrives.
  - Then mark all steps done, jump to 100%, and show the results after about 400 ms.
- **Results** (in this order):
  - ResultHeader: title, URL, summary, a ScoreRing (SVG circle; colour by label), the label text, a "GEO-Ready" badge if true, and a "New Analysis" button that resets to landing.
  - ComparisonStrip: Your score / Reference average* / Top reference sites*, with the footnote "*Average of {sample_size} reference sites, updated {date}", or "*Sample values" when `is_sample` is true. Values come from `GET /api/benchmarks`, fetched once on page load; while loading the values show an em dash and the footnote reads "*Loading comparison values...", and on failure "*Comparison values are unavailable right now".
  - TopFixes: "Fix these first", numbered, each with title, severity and effort pills, and how_to_fix.
  - BotAccess: each bot with Allowed (green) / Blocked (red).
  - DimensionCard x6 in a responsive grid. Each shows name, score, label, the summary of sub-scores (name, score or an em dash for null, detail), and an issues list (title, explanation, how_to_fix, severity/effort pills).
- **HowItWorks**: 4 steps: Enter your URL, We crawl & analyze, Get your GEO score, Fix what matters. Shown on the landing state.
- **Faq**: 4 accordion items (What is GEO? / What does this audit check? / How is the score calculated? / How can I improve my score?), shown on landing.
- **Footer**: one line, "GEO Audit Clone: intern project".
- **Errors**: show the API detail in red under the input. On a network failure: "Can't reach the backend. Is it running on port 8000?"
- **API base URL**: `VITE_API_URL` if set; otherwise `http://localhost:8000` in development and same-origin relative paths (`/api/...`) in production builds.
- **Network error message**: "Can't reach the backend. Is it running on port 8000?" in development; "Can't reach the server. Please try again in a moment." in production.
- The Vite dev server uses port 5173 with `strictPort: true`, so it never silently moves to a port CORS doesn't allow.

**Style** (Geoptie-like, our own CSS, no copied assets):

- White background, near-black text (#111827), teal accent (#2A9D8F), light grey cards (#F8FAFA) with 12px radius and 1px borders (#E5E7EB).
- System font stack. Max content width 1100px, centred. Mobile friendly at 375px.
- Label colours: Excellent #16A34A, Good #2A9D8F, Needs work #F59E0B, Poor #DC2626.

## 9. Definition of done

- pytest passes in backend/, including the section 5.8 reference test.
- The steps in README.md (install and run backend and frontend) work on a fresh machine.
- Auditing 5 real sites shows complete reports with no crashes. Invalid input shows friendly errors.
- No out-of-scope features from section 1 exist in the UI.

## Revision notes

Changes from the original implementation plan:

1. Scheme detection uses `://` instead of `urlparse` (4.1).
2. header/footer are only removed outside main/article, and form is kept (4.3).
3. JSON-LD types, author, dates and identity look at nested objects (`json_ld_nodes`, 4.3).
4. The 15 s fetch limit is a true total deadline (4.2).
5. Every other httpx error maps to 502 (4.2).
6. Invalid request bodies return 400 with a plain message instead of 422 (4.1).
7. Decided open points: `duration_seconds` definition, robots.txt from the final host, first heading never counts as skipped, H1 for the intro comes from the main content, date candidates fall back in order, empty values count as missing, hard_to_read needs a measurable readability, explicit issue list for the top-5 test, no localhost exception, injectable HTTP client, Vite strictPort.
8. Benchmarks are computed live from reference sites instead of being fixed sample values (5.6), with the audit pipeline moved to `audit.py` so the API and the benchmark calculation share it.
9. Prepared for Vercel: benchmarks moved from a background job to a cached `GET /api/benchmarks` endpoint and out of the Report, `vercel.json` added, production builds call the API on the same domain, and test-only libraries moved to `requirements-dev.txt`.
10. The CMU pronouncing dictionary that textstat needs is bundled in `backend/nltk_data/` and added to NLTK's search path in `checks.py`, because textstat otherwise downloads it into the home directory on first use, which fails on read-only serverless hosts.
