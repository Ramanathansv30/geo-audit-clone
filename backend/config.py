"""Every tunable number used by the audit: fetch limits, weights, points and thresholds.

Band tables are tuples of (upper_bound, score) checked in order: the first entry whose
upper bound is greater than the value wins. Values beyond the last bound use the
matching *_DEFAULT. See scoring.band().
"""

# --- HTTP / fetching -------------------------------------------------------------
USER_AGENT = "GEOAuditClone/1.0 (local intern project)"
FETCH_TIMEOUT_SECONDS = 15
ROBOTS_TIMEOUT_SECONDS = 5
MAX_REDIRECTS = 5
MAX_PAGE_BYTES = 5 * 1024 * 1024
CORS_ORIGINS = ["http://localhost:5173"]

# --- General scoring -------------------------------------------------------------
MAX_SCORE = 100
ROUNDING_EPSILON = 1e-9
GEO_READY_THRESHOLD = 70
TOP_FIXES_COUNT = 5

# score < upper -> label
LABEL_BANDS = ((40, "Poor"), (60, "Needs work"), (80, "Good"))
LABEL_DEFAULT = "Excellent"

# --- Benchmarks (comparison strip) --------------------------------------------------
# Fallback shown until live values are available (marked as sample values in the UI).
SAMPLE_BENCHMARKS = {
    "industry_average": 65,
    "top_sites": 85,
    "is_sample": True,
    "sample_size": 0,
    "updated_at": None,
}

# Live values are the scores of these reference pages, audited with the same rules.
BENCHMARK_SITES = (
    "https://en.wikipedia.org/wiki/Search_engine_optimization",
    "https://developer.mozilla.org/en-US/docs/Web/HTML",
    "https://www.python.org/",
    "https://www.bbc.com/news",
    "https://docs.github.com/en/get-started",
    "https://www.gov.uk/",
    "https://www.nasa.gov/",
    "https://www.who.int/",
    "https://www.w3.org/",
    "https://www.nationalgeographic.com/",
)
BENCHMARK_REFRESH_SECONDS = 24 * 60 * 60
BENCHMARK_RETRY_SECONDS = 10 * 60
BENCHMARK_CONCURRENCY = 5
BENCHMARK_MIN_SITES = 5
BENCHMARK_TOP_FRACTION = 0.25

# --- Dimensions and sub-scores (order matters: it is the report order) -----------
DIMENSIONS = {
    "answer_first": {
        "name": "Answer First Content",
        "weight": 0.20,
        "sub_scores": {
            "faq": ("FAQ / question headings", 1 / 3),
            "intro": ("Short intro answer", 1 / 3),
            "lists": ("Lists & tables", 1 / 3),
        },
    },
    "technical": {
        "name": "Technical Optimization",
        "weight": 0.20,
        "sub_scores": {
            "crawlability": ("Crawlability", 0.5),
            "structured": ("Structured data & meta", 0.3),
            "speed": ("Page speed", 0.2),
        },
    },
    "authority": {
        "name": "Citation Authority",
        "weight": 0.15,
        "sub_scores": {
            "author": ("Author signals", 0.4),
            "sources": ("Outbound sources", 0.3),
            "numbers": ("Numbers & facts", 0.3),
        },
    },
    "comprehension": {
        "name": "AI Comprehension",
        "weight": 0.15,
        "sub_scores": {
            "headings": ("Heading structure", 0.4),
            "readability": ("Readability", 0.4),
            "identity": ("Page identity", 0.2),
        },
    },
    "freshness": {
        "name": "Content Freshness",
        "weight": 0.15,
        "sub_scores": {
            "dates": ("Dates present", 0.4),
            "recency": ("Recency", 0.6),
        },
    },
    "depth": {
        "name": "Content Depth",
        "weight": 0.15,
        "sub_scores": {
            "words": ("Word count", 0.6),
            "alt": ("Image alt text", 0.4),
        },
    },
}

# --- answer_first ----------------------------------------------------------------
FAQ_FOUND_SCORE = 100
FAQ_HEADING_MARKERS = ("faq", "frequently asked")
FAQ_SCHEMA_TYPE = "FAQPage"
QUESTION_HEADING_LEVELS = (2, 3, 4)
QUESTION_HEADING_BANDS = ((1, 30), (2, 50))
QUESTION_HEADING_DEFAULT = 70
FAQ_ISSUE_MAX_SCORE = 50

INTRO_BANDS = ((20, 40), (81, 100), (151, 70))
INTRO_DEFAULT = 40

LIST_TABLE_BANDS = ((1, 40), (3, 70))
LIST_TABLE_DEFAULT = 100

# --- technical -------------------------------------------------------------------
OK_STATUS = 200
STATUS_PENALTY = 50
NOINDEX_PENALTY = 50

# Bot name -> crawlability penalty and the product it feeds. Order is the report order.
AI_BOTS = {
    "GPTBot": {"penalty": 25, "product": "ChatGPT"},
    "ClaudeBot": {"penalty": 15, "product": "Claude"},
    "PerplexityBot": {"penalty": 15, "product": "Perplexity"},
    "Google-Extended": {"penalty": 15, "product": "Google's Gemini"},
    "CCBot": {"penalty": 5, "product": "Common Crawl, a dataset many AI models learn from"},
}

NO_JSON_LD_PENALTY = 60
NO_TITLE_PENALTY = 20
NO_DESCRIPTION_PENALTY = 20
LONG_DESCRIPTION_PENALTY = 10
MAX_DESCRIPTION_LENGTH = 160

SPEED_BANDS = ((1, 100), (2, 80), (4, 60))
SPEED_DEFAULT = 40
SLOW_PAGE_SECONDS = 2

# --- authority -------------------------------------------------------------------
NO_AUTHOR_PENALTY = 40
NO_ORG_SCHEMA_PENALTY = 20
NOT_HTTPS_PENALTY = 40
ORG_SCHEMA_TYPES = frozenset(
    {"Organization", "Corporation", "LocalBusiness", "NewsMediaOrganization", "Person"}
)

SOURCE_BANDS = ((1, 30), (3, 60))
SOURCE_DEFAULT = 90

NUMBER_BANDS = ((1, 40), (5, 70))
NUMBER_DEFAULT = 100

# --- comprehension ---------------------------------------------------------------
H1_PENALTY = 20
SKIPPED_LEVEL_PENALTY = 10
MAX_SKIPPED_LEVEL_PENALTY = 30
LONG_PAGE_WORDS = 500
MIN_H2_FOR_LONG_PAGE = 2
FEW_SUBHEADINGS_PENALTY = 15

MIN_WORDS_FOR_READABILITY = 50
EASY_READING_SCORE = 60
HARD_READING_SCORE = 30
HARD_READING_RESULT = 40
READABILITY_BASE = 50
READABILITY_RANGE = 50

IDENTITY_TITLE_POINTS = 40
IDENTITY_H1_POINTS = 30
IDENTITY_SITE_NAME_POINTS = 30
IDENTITY_SCHEMA_TYPES = frozenset({"Organization", "WebSite"})

# --- freshness -------------------------------------------------------------------
DATE_PRESENT_POINTS = 50
RECENCY_BANDS = ((91, 100), (366, 75), (731, 50))
RECENCY_DEFAULT = 25
NO_DATE_RECENCY = 40
OLD_CONTENT_DAYS = 365

# --- depth -----------------------------------------------------------------------
THIN_CONTENT_WORDS = 300
WORD_BANDS = ((THIN_CONTENT_WORDS, 40), (800, 70))
WORD_DEFAULT = 100

# --- issues ----------------------------------------------------------------------
SEVERITY_POINTS = {"High": 3, "Medium": 2, "Low": 1}
EFFORT_COST = {"Low": 1, "Medium": 2, "High": 3}
