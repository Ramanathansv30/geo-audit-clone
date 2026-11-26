"""Sub-score rules and issue detection for every dimension (SPEC sections 5.2 and 6)."""

from datetime import datetime, timezone
from functools import partial
from itertools import pairwise
from pathlib import Path

import nltk
import textstat
from protego import Protego

import config

# textstat counts syllables with the CMU pronouncing dictionary (an NLTK corpus) and tries to
# download it on first use. The dictionary ships with the project instead, because serverless
# hosts such as Vercel cannot write to the home directory.
NLTK_DATA_DIR = Path(__file__).resolve().parent / "nltk_data"
nltk.data.path.insert(0, str(NLTK_DATA_DIR))
from crawler import FetchResult
from extractor import PageFacts, node_types
from issues import make_issue
from models import BotAccess, DimensionCheck, SubScore
from scoring import band, round_half_up

Penalty = tuple[int, str]


def run_checks(
    facts: PageFacts,
    page: FetchResult,
    bot_access: list[BotAccess],
    now: datetime | None = None,
) -> dict[str, DimensionCheck]:
    """Run every dimension's checks, keyed by dimension."""
    return {
        "answer_first": check_answer_first(facts),
        "technical": check_technical(facts, page, bot_access),
        "authority": check_authority(facts),
        "comprehension": check_comprehension(facts),
        "freshness": check_freshness(facts, now or datetime.now(timezone.utc)),
        "depth": check_depth(facts),
    }


def evaluate_bot_access(robots_txt: str | None, url: str) -> list[BotAccess]:
    """Whether each AI bot may fetch url; a missing robots.txt allows everything."""
    rules = Protego.parse(robots_txt) if robots_txt is not None else None
    return [
        BotAccess(bot=bot, allowed=rules is None or rules.can_fetch(url, bot))
        for bot in config.AI_BOTS
    ]


def _sub_score(dimension: str, key: str, score: int | None, detail: str) -> SubScore:
    name, weight = config.DIMENSIONS[dimension]["sub_scores"][key]
    return SubScore(key=key, name=name, weight=weight, score=score, detail=detail)


def _deduct(penalties: list[Penalty], clean_detail: str) -> tuple[int, str]:
    """Start from the maximum score, subtract penalties (floor 0) and describe them."""
    score = max(0, config.MAX_SCORE - sum(points for points, _ in penalties))
    return score, "; ".join(note for _, note in penalties) or clean_detail


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def check_answer_first(facts: PageFacts) -> DimensionCheck:
    """FAQ / question headings, short intro answer, lists and tables."""
    sub = partial(_sub_score, "answer_first")
    issues = []

    faq_found = config.FAQ_SCHEMA_TYPE in facts.schema_types or any(
        marker in text.lower() for _, text in facts.headings for marker in config.FAQ_HEADING_MARKERS
    )
    if faq_found:
        faq, faq_detail = config.FAQ_FOUND_SCORE, "FAQ section found"
    else:
        questions = sum(
            1
            for level, text in facts.headings
            if level in config.QUESTION_HEADING_LEVELS and text.endswith("?")
        )
        faq = band(questions, config.QUESTION_HEADING_BANDS, config.QUESTION_HEADING_DEFAULT)
        faq_detail = _count(questions, "question heading")
    if faq <= config.FAQ_ISSUE_MAX_SCORE:
        issues.append(make_issue("no_faq"))

    intro_words = facts.first_paragraph_words
    intro = band(intro_words, config.INTRO_BANDS, config.INTRO_DEFAULT)
    if intro < config.MAX_SCORE:
        issues.append(make_issue("long_intro"))

    lists_count = facts.list_table_count
    lists = band(lists_count, config.LIST_TABLE_BANDS, config.LIST_TABLE_DEFAULT)
    if lists_count == 0:
        issues.append(make_issue("no_lists"))

    return DimensionCheck(
        [
            sub("faq", faq, faq_detail),
            sub("intro", intro, f"{intro_words}-word opening paragraph" if intro_words else "No opening paragraph"),
            sub("lists", lists, _count(lists_count, "list/table", "lists/tables")),
        ],
        issues,
    )


def check_technical(facts: PageFacts, page: FetchResult, bot_access: list[BotAccess]) -> DimensionCheck:
    """Crawlability, structured data and meta tags, page speed."""
    sub = partial(_sub_score, "technical")
    issues = []

    crawl_penalties: list[Penalty] = []
    if page.status_code != config.OK_STATUS:
        crawl_penalties.append((config.STATUS_PENALTY, f"HTTP {page.status_code}"))
        issues.append(make_issue("page_error", status=page.status_code))
    if "noindex" in facts.meta_robots:
        crawl_penalties.append((config.NOINDEX_PENALTY, "noindex"))
        issues.append(make_issue("noindex"))
    blocked = [access.bot for access in bot_access if not access.allowed]
    if blocked:
        penalty = sum(config.AI_BOTS[bot]["penalty"] for bot in blocked)
        crawl_penalties.append((penalty, f"robots.txt blocks {', '.join(blocked)}"))
        issues.extend(
            make_issue("bot_blocked", bot=bot, product=config.AI_BOTS[bot]["product"]) for bot in blocked
        )
    crawlability, crawl_detail = _deduct(crawl_penalties, "No crawl blockers found")

    meta_penalties: list[Penalty] = []
    if not facts.json_ld:
        meta_penalties.append((config.NO_JSON_LD_PENALTY, "no JSON-LD"))
        issues.append(make_issue("no_structured_data"))
    if not facts.title:
        meta_penalties.append((config.NO_TITLE_PENALTY, "no title"))
        issues.append(make_issue("missing_title"))
    description = facts.meta_description
    if description is None:
        meta_penalties.append((config.NO_DESCRIPTION_PENALTY, "no meta description"))
        issues.append(make_issue("missing_meta_description"))
    elif len(description) > config.MAX_DESCRIPTION_LENGTH:
        meta_penalties.append((config.LONG_DESCRIPTION_PENALTY, f"{len(description)}-character description"))
        issues.append(make_issue("meta_description_too_long", n=len(description)))
    structured, structured_detail = _deduct(
        meta_penalties, f"{_count(len(facts.json_ld), 'JSON-LD object')}, title and description"
    )

    elapsed = page.elapsed_seconds
    speed = band(elapsed, config.SPEED_BANDS, config.SPEED_DEFAULT)
    if elapsed >= config.SLOW_PAGE_SECONDS:
        issues.append(make_issue("slow_page", t=f"{elapsed:.1f}"))

    return DimensionCheck(
        [
            sub("crawlability", crawlability, crawl_detail),
            sub("structured", structured, structured_detail),
            sub("speed", speed, f"{elapsed:.1f} s to load"),
        ],
        issues,
    )


def check_authority(facts: PageFacts) -> DimensionCheck:
    """Author and publisher signals, outbound sources, numbers and facts."""
    sub = partial(_sub_score, "authority")
    issues = []

    penalties: list[Penalty] = []
    if not facts.has_author:
        penalties.append((config.NO_AUTHOR_PENALTY, "no author"))
        issues.append(make_issue("no_author"))
    if not facts.schema_types & config.ORG_SCHEMA_TYPES:
        penalties.append((config.NO_ORG_SCHEMA_PENALTY, "no Organization or Person schema"))
        issues.append(make_issue("no_org_schema"))
    if not facts.is_https:
        penalties.append((config.NOT_HTTPS_PENALTY, "not HTTPS"))
        issues.append(make_issue("not_https"))
    author, author_detail = _deduct(penalties, "Author, publisher and HTTPS found")

    source_count = len(facts.outbound_domains)
    sources = band(source_count, config.SOURCE_BANDS, config.SOURCE_DEFAULT)
    if source_count == 0:
        issues.append(make_issue("no_outbound_sources"))

    number_count = facts.number_count
    numbers = band(number_count, config.NUMBER_BANDS, config.NUMBER_DEFAULT)
    if number_count == 0:
        issues.append(make_issue("few_numbers"))

    return DimensionCheck(
        [
            sub("author", author, author_detail),
            sub("sources", sources, _count(source_count, "outside domain")),
            sub("numbers", numbers, _count(number_count, "number")),
        ],
        issues,
    )


def readability_score(flesch: float) -> int:
    """Map a Flesch reading-ease value onto 0-100."""
    if flesch >= config.EASY_READING_SCORE:
        return config.MAX_SCORE
    if flesch >= config.HARD_READING_SCORE:
        span = config.EASY_READING_SCORE - config.HARD_READING_SCORE
        return round_half_up(
            config.READABILITY_BASE + (flesch - config.HARD_READING_SCORE) / span * config.READABILITY_RANGE
        )
    return config.HARD_READING_RESULT


def check_comprehension(facts: PageFacts) -> DimensionCheck:
    """Heading structure, readability and page identity."""
    sub = partial(_sub_score, "comprehension")
    issues = []
    levels = [level for level, _ in facts.headings]
    h1_count = levels.count(1)

    penalties: list[Penalty] = []
    if h1_count != 1:
        penalties.append((config.H1_PENALTY, _count(h1_count, "H1")))
        issues.append(make_issue("h1_issue", n=h1_count))
    skipped = sum(1 for previous, level in pairwise(levels) if level > previous + 1)
    if skipped:
        penalty = min(skipped * config.SKIPPED_LEVEL_PENALTY, config.MAX_SKIPPED_LEVEL_PENALTY)
        penalties.append((penalty, _count(skipped, "skipped level")))
        issues.append(make_issue("skipped_heading_levels"))
    h2_count = levels.count(2)
    if facts.word_count > config.LONG_PAGE_WORDS and h2_count < config.MIN_H2_FOR_LONG_PAGE:
        penalties.append((config.FEW_SUBHEADINGS_PENALTY, f"{_count(h2_count, 'H2')} on a long page"))
        issues.append(make_issue("few_subheadings"))
    headings, headings_detail = _deduct(penalties, f"{_count(len(levels), 'heading')}, well nested")

    if facts.word_count < config.MIN_WORDS_FOR_READABILITY:
        readability, readability_detail = None, "Not enough text to measure"
    else:
        flesch = textstat.flesch_reading_ease(facts.main_text)
        readability, readability_detail = readability_score(flesch), f"Flesch {flesch:.0f}"
        if flesch < config.HARD_READING_SCORE:
            issues.append(make_issue("hard_to_read"))

    has_site_name = bool(facts.og_site_name) or any(
        node.get("name") and config.IDENTITY_SCHEMA_TYPES.intersection(node_types(node))
        for node in facts.json_ld_nodes
    )
    signals = [
        ("title", bool(facts.title), config.IDENTITY_TITLE_POINTS),
        ("H1", h1_count > 0, config.IDENTITY_H1_POINTS),
        ("site name", has_site_name, config.IDENTITY_SITE_NAME_POINTS),
    ]
    identity = sum(points for _, present, points in signals if present)
    found = [name for name, present, _ in signals if present]
    identity_detail = f"Has {', '.join(found)}" if found else "No title, H1 or site name"

    return DimensionCheck(
        [
            sub("headings", headings, headings_detail),
            sub("readability", readability, readability_detail),
            sub("identity", identity, identity_detail),
        ],
        issues,
    )


def check_freshness(facts: PageFacts, now: datetime) -> DimensionCheck:
    """Whether dates are shown and how recent the newest one is."""
    sub = partial(_sub_score, "freshness")
    issues = []
    published, modified = facts.date_published, facts.date_modified

    dates = config.DATE_PRESENT_POINTS * ((published is not None) + (modified is not None))
    dates_detail = {
        (True, True): "Published and updated dates",
        (True, False): "Published date only",
        (False, True): "Updated date only",
        (False, False): "No dates",
    }[(published is not None, modified is not None)]

    present = [date for date in (published, modified) if date is not None]
    if present:
        age_days = max(0, (now - max(present)).days)
        recency = band(age_days, config.RECENCY_BANDS, config.RECENCY_DEFAULT)
        recency_detail = f"Newest date is {_count(age_days, 'day')} old"
        if age_days > config.OLD_CONTENT_DAYS:
            issues.append(make_issue("old_content"))
    else:
        recency, recency_detail = config.NO_DATE_RECENCY, "No date found"
        issues.append(make_issue("no_dates"))

    return DimensionCheck(
        [sub("dates", dates, dates_detail), sub("recency", recency, recency_detail)],
        issues,
    )


def check_depth(facts: PageFacts) -> DimensionCheck:
    """Amount of content and image alt text coverage."""
    sub = partial(_sub_score, "depth")
    issues = []

    word_count = facts.word_count
    words = band(word_count, config.WORD_BANDS, config.WORD_DEFAULT)
    if word_count < config.THIN_CONTENT_WORDS:
        issues.append(make_issue("thin_content", n=word_count))

    total, with_alt = facts.images_total, facts.images_with_alt
    if total == 0:
        alt, alt_detail = None, "No images"
    else:
        alt = round_half_up(config.MAX_SCORE * with_alt / total)
        alt_detail = f"{with_alt} of {total} images have alt text"
        if with_alt < total:
            issues.append(make_issue("images_missing_alt", k=total - with_alt, n=total))

    return DimensionCheck(
        [sub("words", words, _count(word_count, "word")), sub("alt", alt, alt_detail)],
        issues,
    )
