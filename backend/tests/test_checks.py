from datetime import timedelta

import pytest

import checks
import config
from checks import (
    check_answer_first,
    check_authority,
    check_comprehension,
    check_depth,
    check_freshness,
    check_technical,
    evaluate_bot_access,
    readability_score,
    run_checks,
)
from conftest import NOW, PAGE_URL, make_facts, make_page

ALL_ALLOWED = evaluate_bot_access(None, PAGE_URL)


def scores(result) -> dict:
    return {sub.key: sub.score for sub in result.sub_scores}


def issue_ids(result) -> list[str]:
    return [issue.id for issue in result.issues]


def technical(facts=None, robots_txt=None, **page_overrides):
    page = make_page(robots_txt=robots_txt, **page_overrides)
    return check_technical(facts or make_facts(), page, evaluate_bot_access(robots_txt, page.final_url))


def test_perfect_page_has_no_issues():
    results = run_checks(make_facts(), make_page(), ALL_ALLOWED, now=NOW)

    all_scores = {sub.key: sub.score for result in results.values() for sub in result.sub_scores}
    assert all(not result.issues for result in results.values())
    assert all_scores.pop("sources") == config.SOURCE_DEFAULT
    assert set(all_scores.values()) == {100}


# --- answer_first ----------------------------------------------------------------

@pytest.mark.parametrize(
    ("headings", "schema_types", "expected", "has_issue"),
    [
        ([(2, "Details")], {"FAQPage"}, 100, False),
        ([(2, "Frequently Asked Questions")], set(), 100, False),
        ([(3, "Our FAQ")], set(), 100, False),
        ([(2, "Why?"), (4, "How?")], set(), 70, False),
        ([(2, "Why?"), (5, "How?")], set(), 50, True),
        ([(2, "Details")], set(), 30, True),
    ],
)
def test_faq(headings, schema_types, expected, has_issue):
    result = check_answer_first(make_facts(headings=headings, schema_types=schema_types))

    assert scores(result)["faq"] == expected
    assert ("no_faq" in issue_ids(result)) is has_issue


@pytest.mark.parametrize(
    ("words", "expected"),
    [(0, 40), (19, 40), (20, 100), (80, 100), (81, 70), (150, 70), (151, 40)],
)
def test_intro(words, expected):
    result = check_answer_first(make_facts(first_paragraph_words=words))

    assert scores(result)["intro"] == expected
    assert ("long_intro" in issue_ids(result)) is (expected < 100)


@pytest.mark.parametrize(("count", "expected"), [(0, 40), (1, 70), (2, 70), (3, 100)])
def test_lists(count, expected):
    result = check_answer_first(make_facts(list_table_count=count))

    assert scores(result)["lists"] == expected
    assert ("no_lists" in issue_ids(result)) is (count == 0)


# --- technical -------------------------------------------------------------------

def test_robots_blocking_gptbot():
    result = technical(robots_txt="User-agent: GPTBot\nDisallow: /\n")

    assert scores(result)["crawlability"] == 75
    assert issue_ids(result) == ["bot_blocked"]
    assert result.issues[0].title == "AI bot blocked: GPTBot"
    assert result.sub_scores[0].detail == "robots.txt blocks GPTBot"


def test_bot_access_order_and_wildcard_block():
    access = evaluate_bot_access("User-agent: *\nDisallow: /\n", PAGE_URL)

    assert [item.bot for item in access] == ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"]
    assert not any(item.allowed for item in access)


def test_crawlability_penalties_floor_at_zero():
    result = technical(
        facts=make_facts(meta_robots="noindex, nofollow"),
        robots_txt="User-agent: *\nDisallow: /\n",
        status_code=404,
    )

    assert scores(result)["crawlability"] == 0
    assert issue_ids(result).count("bot_blocked") == 5
    assert {"page_error", "noindex"} <= set(issue_ids(result))
    assert result.issues[0].title == "Page returned HTTP 404"


@pytest.mark.parametrize(
    ("overrides", "expected", "issue"),
    [
        ({"json_ld": []}, 40, "no_structured_data"),
        ({"title": None}, 80, "missing_title"),
        ({"meta_description": None}, 80, "missing_meta_description"),
        ({"meta_description": "x" * 160}, 100, None),
        ({"meta_description": "x" * 161}, 90, "meta_description_too_long"),
        ({"json_ld": [], "title": None, "meta_description": None}, 0, "no_structured_data"),
    ],
)
def test_structured(overrides, expected, issue):
    result = technical(facts=make_facts(**overrides))

    assert scores(result)["structured"] == expected
    assert (issue in issue_ids(result)) if issue else not result.issues


def test_long_description_title_includes_length():
    result = technical(facts=make_facts(meta_description="x" * 161))

    assert result.issues[0].title == "Meta description is 161 characters (keep under 160)"


@pytest.mark.parametrize(
    ("elapsed", "expected", "slow"),
    [(0.99, 100, False), (1.0, 80, False), (1.99, 80, False), (2.0, 60, True), (3.99, 60, True), (4.0, 40, True)],
)
def test_speed(elapsed, expected, slow):
    result = technical(elapsed_seconds=elapsed)

    assert scores(result)["speed"] == expected
    assert ("slow_page" in issue_ids(result)) is slow


# --- authority -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("overrides", "expected", "issues"),
    [
        ({"has_author": False}, 60, ["no_author"]),
        ({"schema_types": {"Article"}}, 80, ["no_org_schema"]),
        ({"schema_types": {"Person"}}, 100, []),
        ({"is_https": False}, 60, ["not_https"]),
        ({"has_author": False, "schema_types": set(), "is_https": False}, 0, ["no_author", "no_org_schema", "not_https"]),
    ],
)
def test_author(overrides, expected, issues):
    result = check_authority(make_facts(**overrides))

    assert scores(result)["author"] == expected
    assert issue_ids(result) == issues


@pytest.mark.parametrize(("count", "expected"), [(0, 30), (1, 60), (2, 60), (3, 90)])
def test_sources(count, expected):
    result = check_authority(make_facts(outbound_domains={f"site{i}.org" for i in range(count)}))

    assert scores(result)["sources"] == expected
    assert ("no_outbound_sources" in issue_ids(result)) is (count == 0)


@pytest.mark.parametrize(("count", "expected"), [(0, 40), (1, 70), (4, 70), (5, 100)])
def test_numbers(count, expected):
    result = check_authority(make_facts(number_count=count))

    assert scores(result)["numbers"] == expected
    assert ("few_numbers" in issue_ids(result)) is (count == 0)


# --- comprehension ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("levels", "word_count", "expected", "issues"),
    [
        ([1, 2, 2], 900, 100, []),
        ([2, 2], 900, 80, ["h1_issue"]),
        ([1, 1, 2, 2], 900, 80, ["h1_issue"]),
        ([1, 3, 2], 400, 90, ["skipped_heading_levels"]),
        ([3, 1, 2, 2], 900, 100, []),
        ([1, 3, 2, 4, 2, 4, 2, 5], 400, 70, ["skipped_heading_levels"]),
        ([1, 2], 501, 85, ["few_subheadings"]),
        ([1, 2], 500, 100, []),
    ],
)
def test_headings(levels, word_count, expected, issues):
    facts = make_facts(headings=[(level, "Heading") for level in levels], word_count=word_count)
    result = check_comprehension(facts)

    assert scores(result)["headings"] == expected
    assert issue_ids(result) == issues


def test_h1_issue_title_includes_count():
    result = check_comprehension(make_facts(headings=[(2, "A")]))

    assert result.issues[0].title == "Page should have exactly one H1 (found 0)"


@pytest.mark.parametrize(
    ("flesch", "expected"),
    [(80, 100), (60, 100), (59.9, 100), (52.2, 87), (45, 75), (30, 50), (29.9, 40), (-10, 40)],
)
def test_readability_score(flesch, expected):
    assert readability_score(flesch) == expected


def test_readability_needs_enough_words():
    result = check_comprehension(make_facts(word_count=49))

    assert scores(result)["readability"] is None
    assert "hard_to_read" not in issue_ids(result)


def test_hard_to_read_issue(monkeypatch):
    monkeypatch.setattr(checks.textstat, "flesch_reading_ease", lambda text: 20.0)
    result = check_comprehension(make_facts())

    assert scores(result)["readability"] == 40
    assert issue_ids(result) == ["hard_to_read"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, 100),
        ({"og_site_name": None, "json_ld_nodes": []}, 70),
        ({"og_site_name": None, "json_ld_nodes": [{"@type": "WebSite", "name": "Site"}]}, 100),
        ({"og_site_name": None, "json_ld_nodes": [{"@type": "WebSite"}]}, 70),
        ({"title": None, "headings": [(2, "A")], "og_site_name": None, "json_ld_nodes": []}, 0),
    ],
)
def test_identity(overrides, expected):
    assert scores(check_comprehension(make_facts(**overrides)))["identity"] == expected


# --- freshness -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("published_days", "modified_days", "dates", "recency", "issues"),
    [
        (10, 5, 100, 100, []),
        (90, None, 50, 100, []),
        (None, 91, 50, 75, []),
        (365, None, 50, 75, []),
        (366, None, 50, 50, ["old_content"]),
        (731, None, 50, 25, ["old_content"]),
        (None, None, 0, 40, ["no_dates"]),
    ],
)
def test_freshness(published_days, modified_days, dates, recency, issues):
    def days_ago(days):
        return None if days is None else NOW - timedelta(days=days)

    facts = make_facts(date_published=days_ago(published_days), date_modified=days_ago(modified_days))
    result = check_freshness(facts, NOW)

    assert scores(result) == {"dates": dates, "recency": recency}
    assert issue_ids(result) == issues


# --- depth -----------------------------------------------------------------------

@pytest.mark.parametrize(("count", "expected"), [(0, 40), (299, 40), (300, 70), (799, 70), (800, 100)])
def test_words(count, expected):
    result = check_depth(make_facts(word_count=count))

    assert scores(result)["words"] == expected
    assert ("thin_content" in issue_ids(result)) is (count < 300)


def test_no_images_gives_none():
    result = check_depth(make_facts(images_total=0, images_with_alt=0))

    assert scores(result)["alt"] is None
    assert result.sub_scores[1].detail == "No images"


def test_missing_alt_text():
    result = check_depth(make_facts(images_total=4, images_with_alt=3))

    assert scores(result)["alt"] == 75
    assert result.issues[0].title == "1 of 4 images have no alt text"
