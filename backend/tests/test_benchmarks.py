import httpx
import pytest

import benchmarks
from benchmarks import SAMPLE_BENCHMARKS, BenchmarkCache, benchmarks_from_scores, compute_benchmarks
from conftest import html_response, load_fixture, mock_http_client
from main import app, get_benchmark_cache

SITES = [f"https://site{i}.example.com/" for i in range(7)]


def test_average_and_top_quarter():
    result = benchmarks_from_scores([10, 90, 20, 80, 30, 70, 40, 60, 50, 0])

    assert result.industry_average == 45
    assert result.top_sites == 80  # top ceil(10 x 0.25) = 3 scores: 90, 80, 70
    assert result.is_sample is False
    assert result.sample_size == 10
    assert result.updated_at is not None


def test_averages_round_half_up():
    assert benchmarks_from_scores([60, 61]).industry_average == 61


async def test_compute_skips_failed_and_error_pages():
    article = html_response(load_fixture("article.html"))
    routes = {url: article for url in SITES[:5]}
    routes[SITES[5]] = httpx.ConnectError("down")
    routes[SITES[6]] = html_response("<h1>Forbidden</h1>", status=403)

    async with mock_http_client(routes) as client:
        result = await compute_benchmarks(client, SITES)

    assert result.sample_size == 5
    assert result.industry_average == result.top_sites


async def test_compute_returns_none_when_too_few_sites_succeed():
    routes = {url: httpx.ConnectError("down") for url in SITES}

    async with mock_http_client(routes) as client:
        assert await compute_benchmarks(client, SITES) is None


@pytest.fixture
def fake_compute(monkeypatch):
    """Replace compute_benchmarks with a queue of results and count the calls."""
    calls = []

    def install(*results):
        queue = list(results)

        async def compute(_client):
            calls.append(1)
            result = queue.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(benchmarks, "compute_benchmarks", compute)
        return calls

    return install


async def test_cache_computes_once_while_fresh(fake_compute):
    live = benchmarks_from_scores([70, 80])
    calls = fake_compute(live)
    cache = BenchmarkCache()

    assert await cache.get(None) == live
    assert await cache.get(None) == live
    assert len(calls) == 1


async def test_cache_serves_sample_values_and_waits_after_failure(fake_compute):
    calls = fake_compute(None)
    cache = BenchmarkCache()

    assert await cache.get(None) == SAMPLE_BENCHMARKS
    assert await cache.get(None) == SAMPLE_BENCHMARKS
    assert len(calls) == 1


async def test_cache_keeps_last_good_values_when_refresh_fails(fake_compute, monkeypatch):
    live = benchmarks_from_scores([70, 80])
    calls = fake_compute(live, RuntimeError("boom"))
    cache = BenchmarkCache()
    await cache.get(None)
    monkeypatch.setattr(cache, "_next_refresh", 0.0)

    assert await cache.get(None) == live
    assert len(calls) == 2


def test_benchmarks_endpoint(api, fake_compute):
    live = benchmarks_from_scores([68, 82])
    fake_compute(live)
    app.dependency_overrides[get_benchmark_cache] = BenchmarkCache

    response = api({}).get("/api/benchmarks")

    assert response.status_code == 200
    assert response.json() == live.model_dump(mode="json")
