"""Live comparison values, computed by auditing a fixed set of reference sites and cached in memory."""

import asyncio
import logging
import math
import time
from collections.abc import Sequence
from datetime import datetime, timezone

import httpx

import config
from audit import run_audit
from crawler import AuditError
from models import Benchmarks
from scoring import round_half_up

logger = logging.getLogger(__name__)

SAMPLE_BENCHMARKS = Benchmarks(**config.SAMPLE_BENCHMARKS)


def benchmarks_from_scores(scores: Sequence[int]) -> Benchmarks:
    """Average of all scores, and average of the top fraction of scores."""
    ranked = sorted(scores, reverse=True)
    top_count = math.ceil(len(ranked) * config.BENCHMARK_TOP_FRACTION)
    return Benchmarks(
        industry_average=_average(ranked),
        top_sites=_average(ranked[:top_count]),
        is_sample=False,
        sample_size=len(ranked),
        updated_at=datetime.now(timezone.utc).replace(microsecond=0),
    )


def _average(values: Sequence[int]) -> int:
    return round_half_up(sum(values) / len(values))


async def _reference_score(url: str, client: httpx.AsyncClient, limit: asyncio.Semaphore) -> int | None:
    """Overall score of one reference page, or None if it can't be audited fairly."""
    async with limit:
        try:
            report = await run_audit(url, client)
        except AuditError as exc:
            logger.warning("Benchmark site skipped (%s): %s", url, exc.message)
            return None
    if any(issue.id == "page_error" for dimension in report.dimensions for issue in dimension.issues):
        logger.warning("Benchmark site skipped (%s): page did not return HTTP 200", url)
        return None
    return report.overall_score


async def compute_benchmarks(
    client: httpx.AsyncClient, sites: Sequence[str] = config.BENCHMARK_SITES
) -> Benchmarks | None:
    """Audit every reference site; None when too few of them succeed."""
    limit = asyncio.Semaphore(config.BENCHMARK_CONCURRENCY)
    results = await asyncio.gather(*(_reference_score(url, client, limit) for url in sites))
    scores = [score for score in results if score is not None]
    if len(scores) < config.BENCHMARK_MIN_SITES:
        logger.warning("Benchmarks not updated: only %d of %d sites succeeded", len(scores), len(sites))
        return None
    return benchmarks_from_scores(scores)


class BenchmarkCache:
    """Latest benchmarks for this server process, recomputed when stale.

    Concurrent callers share one computation. After a failed computation the last good
    values (or the sample values) are served, and the next attempt waits a retry interval.
    """

    def __init__(self) -> None:
        self._value: Benchmarks | None = None
        self._next_refresh = 0.0
        self._lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient) -> Benchmarks:
        """Current benchmarks, computing them first if they are missing or stale."""
        if time.monotonic() >= self._next_refresh:
            async with self._lock:
                if time.monotonic() >= self._next_refresh:
                    await self._refresh(client)
        return self._value or SAMPLE_BENCHMARKS

    async def _refresh(self, client: httpx.AsyncClient) -> None:
        try:
            fresh = await compute_benchmarks(client)
        except Exception:
            logger.exception("Benchmark refresh failed")
            fresh = None
        if fresh is None:
            self._next_refresh = time.monotonic() + config.BENCHMARK_RETRY_SECONDS
            return
        self._value = fresh
        self._next_refresh = time.monotonic() + config.BENCHMARK_REFRESH_SECONDS
