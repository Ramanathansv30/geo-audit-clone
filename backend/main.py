"""FastAPI application: routes, CORS and error handling (SPEC section 7)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from audit import run_audit
from benchmarks import BenchmarkCache
from crawler import INVALID_URL, AuditError, create_http_client
from models import AuditRequest, Benchmarks, Report

benchmark_cache = BenchmarkCache()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Share one HTTP client (and its connection pool) across all requests."""
    async with create_http_client() as client:
        app.state.http_client = client
        yield


app = FastAPI(title="GEO Audit Clone", version="1.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency that provides the shared HTTP client; overridden in tests."""
    return request.app.state.http_client


def get_benchmark_cache() -> BenchmarkCache:
    """Dependency that provides the process-wide benchmark cache; overridden in tests."""
    return benchmark_cache


@app.exception_handler(AuditError)
async def handle_audit_error(_: Request, exc: AuditError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": INVALID_URL})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/audit", response_model=Report)
async def audit(body: AuditRequest, client: httpx.AsyncClient = Depends(get_http_client)) -> Report:
    """Validate, fetch, analyse and score a page."""
    return await run_audit(body.url, client)


@app.get("/api/benchmarks", response_model=Benchmarks)
async def benchmarks(
    client: httpx.AsyncClient = Depends(get_http_client),
    cache: BenchmarkCache = Depends(get_benchmark_cache),
) -> Benchmarks:
    """Comparison values from the reference sites (computed on first use, cached for 24 hours)."""
    return await cache.get(client)
