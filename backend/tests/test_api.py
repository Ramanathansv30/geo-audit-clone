import httpx
import pytest

import config
from conftest import html_response, load_fixture
from crawler import validate_url

PAGE = "https://example.com/page"
ROBOTS = "https://example.com/robots.txt"


def post_audit(client, url):
    return client.post("/api/audit", json={"url": url})


def test_health(api):
    response = api({}).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_audit_success(api):
    client = api({
        PAGE: html_response(load_fixture("article.html")),
        ROBOTS: httpx.Response(200, text="User-agent: GPTBot\nDisallow: /\n"),
    })
    response = post_audit(client, "example.com/page")

    assert response.status_code == 200
    report = response.json()
    assert report["url"] == PAGE
    assert report["title"] == "How to Choose Running Shoes | XYZ Sports"
    assert 0 <= report["overall_score"] <= 100
    assert report["bot_access"] == [
        {"bot": "GPTBot", "allowed": False},
        {"bot": "ClaudeBot", "allowed": True},
        {"bot": "PerplexityBot", "allowed": True},
        {"bot": "Google-Extended", "allowed": True},
        {"bot": "CCBot", "allowed": True},
    ]
    assert [d["key"] for d in report["dimensions"]] == list(config.DIMENSIONS)
    assert report["top_fixes"][0]["id"] == "bot_blocked"
    assert len(report["top_fixes"]) <= config.TOP_FIXES_COUNT
    assert report["analyzed_at"].endswith("Z")
    assert report["summary"].startswith(f"{report['label']} overall.")


def test_audit_follows_redirects_and_keeps_error_status(api):
    client = api({
        "https://example.com/old": httpx.Response(301, headers={"location": PAGE}),
        PAGE: html_response("<h1>Gone</h1>", status=404),
    })
    report = post_audit(client, "https://example.com/old").json()

    assert report["final_url"] == PAGE
    assert report["top_fixes"][0]["title"] == "Page returned HTTP 404"
    assert all(item["allowed"] for item in report["bot_access"])


@pytest.mark.parametrize(
    ("url", "detail"),
    [
        ("hello world", "Please enter a valid web address"),
        ("", "Please enter a valid web address"),
        ("https://localhost/page", "Please enter a valid web address"),
        ("ftp://x.com", "Only http and https links work"),
        ("file:///etc/passwd", "Only http and https links work"),
    ],
)
def test_invalid_urls(api, url, detail):
    response = post_audit(api({}), url)

    assert response.status_code == 400
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("body", [{}, {"url": 42}, None])
def test_invalid_body_is_400(api, body):
    response = api({}).post("/api/audit", json=body)

    assert response.status_code == 400
    assert response.json() == {"detail": "Please enter a valid web address"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  example.com ", "https://example.com"),
        ("example.com:8080/x", "https://example.com:8080/x"),
        ("http://example.com", "http://example.com"),
    ],
)
def test_validate_url_normalises(raw, expected):
    assert validate_url(raw) == expected


@pytest.mark.parametrize(
    ("route", "status", "detail"),
    [
        (httpx.Response(200, text="{}", headers={"content-type": "application/json"}), 502, "This link isn't a web page"),
        (httpx.ConnectError("refused"), 502, "Couldn't reach this page"),
        (httpx.RemoteProtocolError("bad"), 502, "Couldn't reach this page"),
        (httpx.ReadTimeout("slow"), 504, "Couldn't reach this page (timed out after 15 s)"),
    ],
)
def test_fetch_errors(api, route, status, detail):
    response = post_audit(api({PAGE: route}), PAGE)

    assert response.status_code == status
    assert response.json() == {"detail": detail}


def test_too_many_redirects(api):
    loop = httpx.Response(302, headers={"location": PAGE})
    response = post_audit(api({PAGE: loop}), PAGE)

    assert response.status_code == 502
    assert response.json() == {"detail": "Couldn't reach this page"}


def test_page_too_large(api, monkeypatch):
    monkeypatch.setattr(config, "MAX_PAGE_BYTES", 100)
    response = post_audit(api({PAGE: html_response("<p>" + "x" * 200 + "</p>")}), PAGE)

    assert response.status_code == 502
    assert response.json() == {"detail": "This page is too large to analyze"}


def test_robots_failure_allows_everything(api):
    client = api({PAGE: html_response("<h1>Hi</h1>"), ROBOTS: httpx.ConnectError("down")})
    report = post_audit(client, PAGE).json()

    assert all(item["allowed"] for item in report["bot_access"])
