"""Turn fetched HTML into PageFacts (SPEC section 4.3)."""

import copy
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from crawler import ALLOWED_SCHEMES, FetchResult

HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
ALWAYS_REMOVED_TAGS = ["script", "style", "noscript", "nav", "aside", "svg", "iframe"]
PAGE_CHROME_TAGS = ["header", "footer"]
CONTENT_CONTAINER_TAGS = ["main", "article"]
LIST_TABLE_TAGS = ["ul", "ol", "table"]
JSON_LD_TYPE = re.compile(r"^\s*application/ld\+json\s*$", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)*%?")


@dataclass(frozen=True)
class PageFacts:
    title: str | None
    meta_description: str | None
    meta_robots: str
    og_site_name: str | None
    headings: list[tuple[int, str]]
    json_ld: list[dict]
    json_ld_nodes: list[dict]
    schema_types: set[str]
    main_text: str
    word_count: int
    first_paragraph_words: int
    list_table_count: int
    outbound_domains: set[str]
    number_count: int
    images_total: int
    images_with_alt: int
    has_author: bool
    date_published: datetime | None
    date_modified: datetime | None
    is_https: bool


def extract_facts(page: FetchResult) -> PageFacts:
    """Parse the page HTML and collect every fact the checks need."""
    soup = BeautifulSoup(page.html, "lxml")
    json_ld = parse_json_ld(soup)
    nodes = list(iter_json_ld_nodes(json_ld))
    main = select_main_content(soup)
    main_text = normalize(main.get_text(" ")) or ""
    images = main.find_all("img")
    meta_robots = [meta_content(soup, "name", "robots"), page.headers.get("x-robots-tag")]
    first_time = soup.find("time", attrs={"datetime": True})

    return PageFacts(
        title=normalize(soup.title.get_text(" ")) if soup.title else None,
        meta_description=meta_content(soup, "name", "description"),
        meta_robots=", ".join(part for part in meta_robots if part).lower(),
        og_site_name=meta_content(soup, "property", "og:site_name"),
        headings=[
            (int(tag.name[1]), normalize(tag.get_text(" ")) or "")
            for tag in soup.find_all(HEADING_TAGS)
        ],
        json_ld=json_ld,
        json_ld_nodes=nodes,
        schema_types={schema_type for node in nodes for schema_type in node_types(node)},
        main_text=main_text,
        word_count=count_words(main_text),
        first_paragraph_words=first_paragraph_words(main),
        list_table_count=len(main.find_all(LIST_TABLE_TAGS)),
        outbound_domains=outbound_domains(main, page.final_url),
        number_count=len(NUMBER_PATTERN.findall(main_text)),
        images_total=len(images),
        images_with_alt=sum(1 for image in images if normalize(image.get("alt"))),
        has_author=has_author(soup, nodes),
        date_published=first_date(
            [
                *(node.get("datePublished") for node in nodes),
                meta_content(soup, "property", "article:published_time"),
                first_time["datetime"] if first_time else None,
            ]
        ),
        date_modified=first_date(
            [
                *(node.get("dateModified") for node in nodes),
                meta_content(soup, "property", "article:modified_time"),
            ]
        ),
        is_https=urlsplit(page.final_url).scheme == "https",
    )


def normalize(value: str | None) -> str | None:
    """Collapse whitespace; return None for missing or blank values."""
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def count_words(text: str) -> int:
    """Number of whitespace-separated tokens."""
    return len(text.split())


def meta_content(soup: BeautifulSoup, attribute: str, value: str) -> str | None:
    """Content of the first <meta> whose attribute matches value (case-insensitive)."""
    pattern = re.compile(f"^{re.escape(value)}$", re.IGNORECASE)
    tag = soup.find("meta", attrs={attribute: pattern})
    return normalize(tag.get("content")) if tag else None


def parse_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Top-level JSON-LD objects, with lists and @graph arrays flattened."""
    objects: list[dict] = []
    for script in soup.find_all("script", attrs={"type": JSON_LD_TYPE}):
        try:
            objects.extend(_flatten_json_ld(json.loads(script.get_text())))
        except ValueError:
            continue
    return objects


def _flatten_json_ld(data: object) -> Iterator[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _flatten_json_ld(item)
    elif isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            yield from _flatten_json_ld(graph)
        else:
            yield data


def iter_json_ld_nodes(value: object) -> Iterator[dict]:
    """Every JSON-LD object at any depth, parents before children."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_ld_nodes(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_ld_nodes(item)


def node_types(node: dict) -> list[str]:
    """The @type of a JSON-LD node as a list of strings."""
    value = node.get("@type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def select_main_content(soup: BeautifulSoup) -> Tag:
    """A cleaned copy of the page's main content area."""
    content = copy.copy(soup)
    for tag in content.find_all(ALWAYS_REMOVED_TAGS):
        if not tag.decomposed:
            tag.decompose()
    for tag in content.find_all(PAGE_CHROME_TAGS):
        if not tag.decomposed and tag.find_parent(CONTENT_CONTAINER_TAGS) is None:
            tag.decompose()
    return content.find("main") or content.find("article") or content.body or content


def first_paragraph_words(main: Tag) -> int:
    """Words in the first non-empty paragraph after the first H1 (or anywhere if no H1)."""
    after_h1 = main.find("h1") is None
    for element in main.find_all(["h1", "p"]):
        if element.name == "h1":
            after_h1 = True
        elif after_h1 and (words := count_words(element.get_text(" "))):
            return words
    return 0


def bare_host(url: str) -> str | None:
    """Lowercase hostname of an absolute http(s) URL without a leading www."""
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in ALLOWED_SCHEMES or not host:
        return None
    return host.removeprefix("www.")


def outbound_domains(main: Tag, page_url: str) -> set[str]:
    """Distinct external hostnames linked from the main content."""
    page_host = bare_host(page_url)
    hosts = (bare_host(link["href"]) for link in main.find_all("a", href=True))
    return {host for host in hosts if host and host != page_host}


def has_author(soup: BeautifulSoup, nodes: list[dict]) -> bool:
    """True when the page names an author anywhere."""
    return bool(
        meta_content(soup, "name", "author")
        or any(node.get("author") for node in nodes)
        or soup.select_one('a[rel~="author"], [itemprop~="author"]')
    )


def parse_date(value: object) -> datetime | None:
    """Parse an ISO date or datetime string into an aware datetime (UTC if naive)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def first_date(candidates: Iterable[object]) -> datetime | None:
    """The first candidate that parses as a date."""
    return next((date for date in map(parse_date, candidates) if date), None)
