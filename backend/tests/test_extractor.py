from datetime import datetime, timezone

import httpx
import pytest

from conftest import facts_from_fixture, make_page
from extractor import extract_facts, parse_date


def test_article_page_facts():
    facts = facts_from_fixture("article.html")

    assert facts.title == "How to Choose Running Shoes | XYZ Sports"
    assert facts.meta_description.startswith("A short guide")
    assert facts.og_site_name == "XYZ Sports"
    assert facts.headings == [
        (1, "How to Choose Running Shoes"),
        (2, "Why does fit matter?"),
        (3, "Signs of a good fit"),
        (2, "Comparing cushioning levels"),
    ]
    assert facts.first_paragraph_words == 34
    assert facts.list_table_count == 2
    assert facts.outbound_domains == {"example-research.org", "runnersworld.com", "pubmed.ncbi.nlm.nih.gov"}
    assert facts.number_count == 4
    assert (facts.images_total, facts.images_with_alt) == (3, 2)
    assert facts.has_author is True
    assert facts.is_https is True


def test_article_header_inside_main_is_kept_but_site_chrome_is_not():
    facts = facts_from_fixture("article.html")

    assert facts.main_text.startswith("How to Choose Running Shoes By Jamie Lee")
    for excluded in ("Home", "Twitter", "Related", "Copyright"):
        assert excluded not in facts.main_text


def test_json_ld_graph_is_flattened_and_nested_nodes_are_found():
    facts = facts_from_fixture("jsonld_graph.html")

    assert [obj.get("@type") for obj in facts.json_ld] == [
        "WebSite",
        ["Article", "NewsArticle"],
        "BreadcrumbList",
    ]
    assert facts.schema_types == {
        "WebSite", "Article", "NewsArticle", "Organization", "Person", "BreadcrumbList",
    }
    assert facts.has_author is True
    assert facts.date_published == datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    assert facts.date_modified == datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_bare_page_has_missing_values():
    facts = facts_from_fixture("bare.html")

    assert facts.title is None
    assert facts.meta_description is None
    assert facts.headings == [(2, "Welcome")]
    assert facts.first_paragraph_words == 5
    assert facts.json_ld == []
    assert (facts.images_total, facts.images_with_alt) == (0, 0)
    assert facts.has_author is False
    assert facts.date_published is None and facts.date_modified is None


def test_page_chrome_is_ignored_and_form_content_is_kept():
    facts = facts_from_fixture(
        "page_chrome.html", headers=httpx.Headers({"X-Robots-Tag": "noarchive"})
    )

    assert facts.main_text == (
        "Real page title This paragraph is the real content of the page. One Partner"
    )
    assert facts.first_paragraph_words == 9
    assert facts.list_table_count == 1
    assert facts.outbound_domains == {"partner.example.org"}
    assert facts.headings == [(1, "Site banner"), (1, "Real page title")]
    assert facts.meta_robots == "noindex, follow, noarchive"


def test_unparseable_date_falls_back_to_next_candidate():
    html = """
        <script type="application/ld+json">{"@type": "Article", "datePublished": "last week"}</script>
        <meta property="article:published_time" content="2025-05-04T10:00:00+02:00">
        <time datetime="2020-01-01">old</time>
    """
    facts = extract_facts(make_page(html))

    assert facts.date_published == datetime.fromisoformat("2025-05-04T10:00:00+02:00")
    assert facts.date_modified is None


def test_http_page_is_not_https():
    assert extract_facts(make_page("<p>x</p>", final_url="http://example.com/")).is_https is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-02", datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ("2026-01-02T03:04:05Z", datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        ("not a date", None),
        (None, None),
        (20260102, None),
    ],
)
def test_parse_date(value, expected):
    assert parse_date(value) == expected
