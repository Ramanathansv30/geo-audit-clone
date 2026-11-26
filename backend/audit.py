"""The audit pipeline shared by the API endpoint and the benchmark calculation."""

import time

import httpx
from starlette.concurrency import run_in_threadpool

from checks import evaluate_bot_access, run_checks
from crawler import FetchResult, fetch_page, validate_url
from extractor import extract_facts
from models import Report
from scoring import build_report


async def run_audit(raw_url: str, client: httpx.AsyncClient) -> Report:
    """Validate, fetch, analyse and score one page. Raises AuditError on expected failures."""
    started = time.perf_counter()
    url = validate_url(raw_url)
    page = await fetch_page(url, client)
    return await run_in_threadpool(_analyze_page, url, page, started)


def _analyze_page(url: str, page: FetchResult, started: float) -> Report:
    """CPU-bound analysis, run off the event loop."""
    facts = extract_facts(page)
    bot_access = evaluate_bot_access(page.robots_txt, page.final_url)
    return build_report(
        url=url,
        final_url=page.final_url,
        title=facts.title,
        checks=run_checks(facts, page, bot_access),
        bot_access=bot_access,
        duration_seconds=time.perf_counter() - started,
    )
