"""URL validation and page fetching (SPEC sections 4.1 and 4.2)."""

import asyncio
import time
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

import httpx
from bs4 import UnicodeDammit

import config

INVALID_URL = "Please enter a valid web address"
UNSUPPORTED_SCHEME = "Only http and https links work"
NOT_HTML = "This link isn't a web page"
TOO_LARGE = "This page is too large to analyze"
TIMED_OUT = f"Couldn't reach this page (timed out after {config.FETCH_TIMEOUT_SECONDS} s)"
UNREACHABLE = "Couldn't reach this page"

ALLOWED_SCHEMES = ("http", "https")


class AuditError(Exception):
    """An expected failure that is returned to the client as {"detail": message}."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    headers: httpx.Headers
    html: str
    elapsed_seconds: float
    robots_txt: str | None


def create_http_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Build the shared HTTP client; tests pass a MockTransport."""
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=True,
        max_redirects=config.MAX_REDIRECTS,
        timeout=config.FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": config.USER_AGENT},
    )


def validate_url(raw_url: str) -> str:
    """Normalise user input into an http(s) URL or raise AuditError(400)."""
    url = raw_url.strip()
    if "://" not in url:
        url = f"https://{url}"
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError as exc:
        raise AuditError(400, INVALID_URL) from exc
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise AuditError(400, UNSUPPORTED_SCHEME)
    if not host or "." not in host or any(char.isspace() for char in host):
        raise AuditError(400, INVALID_URL)
    return url


async def fetch_page(url: str, client: httpx.AsyncClient) -> FetchResult:
    """Download the page and its robots.txt, translating failures into AuditError."""
    try:
        page = await asyncio.wait_for(_fetch_html(url, client), config.FETCH_TIMEOUT_SECONDS)
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise AuditError(504, TIMED_OUT) from exc
    except httpx.HTTPError as exc:
        raise AuditError(502, UNREACHABLE) from exc
    return replace(page, robots_txt=await fetch_robots_txt(page.final_url, client))


async def _fetch_html(url: str, client: httpx.AsyncClient) -> FetchResult:
    """Stream the main page, enforcing the content-type and size limits."""
    started = time.perf_counter()
    async with client.stream("GET", url) as response:
        if "text/html" not in response.headers.get("content-type", "").lower():
            raise AuditError(502, NOT_HTML)
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > config.MAX_PAGE_BYTES:
                raise AuditError(502, TOO_LARGE)
        elapsed = time.perf_counter() - started
        return FetchResult(
            requested_url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            html=_decode_html(bytes(body), response.charset_encoding),
            elapsed_seconds=elapsed,
            robots_txt=None,
        )


def _decode_html(body: bytes, header_charset: str | None) -> str:
    """Decode HTML using the header charset first, then the page's own meta charset."""
    known = [header_charset] if header_charset else []
    return UnicodeDammit(body, known_definite_encodings=known, is_html=True).unicode_markup or ""


async def fetch_robots_txt(page_url: str, client: httpx.AsyncClient) -> str | None:
    """Return robots.txt for the page's host, or None when it is missing or unreachable."""
    parts = urlsplit(page_url)
    try:
        response = await client.get(
            f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=config.ROBOTS_TIMEOUT_SECONDS
        )
    except httpx.HTTPError:
        return None
    return response.text if response.status_code == config.OK_STATUS else None
