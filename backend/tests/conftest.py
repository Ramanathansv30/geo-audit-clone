"""Shared test helpers: HTML fixtures, fake fetch results, fake facts and a mocked API client."""

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from crawler import FetchResult, create_http_client
from extractor import PageFacts, extract_facts
from main import app, get_http_client

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = "https://example.com/page"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
EASY_TEXT = "The cat sat on the mat. " * 150

Route = httpx.Response | Exception | Callable[[httpx.Request], httpx.Response]


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_page(html: str = "", **overrides) -> FetchResult:
    """A FetchResult for a healthy 200 page, with any field overridden."""
    values = {
        "requested_url": PAGE_URL,
        "final_url": PAGE_URL,
        "status_code": 200,
        "headers": httpx.Headers({"content-type": "text/html"}),
        "html": html,
        "elapsed_seconds": 0.5,
        "robots_txt": None,
    }
    return FetchResult(**(values | overrides))


def facts_from_fixture(name: str, **page_overrides) -> PageFacts:
    return extract_facts(make_page(load_fixture(name), **page_overrides))


def make_facts(**overrides) -> PageFacts:
    """PageFacts for a page that passes every rule, with any field overridden."""
    organization = {"@type": "Organization", "name": "Example"}
    values = {
        "title": "Example page",
        "meta_description": "A short description of the page.",
        "meta_robots": "",
        "og_site_name": "Example",
        "headings": [(1, "Example page"), (2, "Frequently asked questions"), (2, "Details")],
        "json_ld": [organization],
        "json_ld_nodes": [organization],
        "schema_types": {"Organization"},
        "main_text": EASY_TEXT,
        "word_count": 900,
        "first_paragraph_words": 50,
        "list_table_count": 3,
        "outbound_domains": {"a.org", "b.org", "c.org"},
        "number_count": 5,
        "images_total": 2,
        "images_with_alt": 2,
        "has_author": True,
        "date_published": NOW,
        "date_modified": NOW,
        "is_https": True,
    }
    return PageFacts(**(values | overrides))


def html_response(html: str, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(status, text=html, headers={"content-type": "text/html; charset=utf-8", **headers})


def mock_http_client(routes: dict[str, Route]) -> httpx.AsyncClient:
    """An AsyncClient whose requests are answered from routes (URL -> response, error or handler)."""

    def handler(request: httpx.Request) -> httpx.Response:
        route = routes.get(str(request.url), httpx.Response(404))
        if isinstance(route, Exception):
            raise route
        return route(request) if callable(route) else route

    return create_http_client(httpx.MockTransport(handler))


@pytest.fixture
def api() -> Iterator[Callable[[dict[str, Route]], TestClient]]:
    """Factory for a TestClient whose outgoing HTTP is served by mocked routes."""
    clients: list[TestClient] = []

    def build(routes: dict[str, Route]) -> TestClient:
        http_client = mock_http_client(routes)
        app.dependency_overrides[get_http_client] = lambda: http_client
        client = TestClient(app)
        clients.append(client)
        return client

    yield build
    app.dependency_overrides.clear()
    for client in clients:
        client.close()
