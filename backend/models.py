"""Pydantic models for the API request and the audit report (SPEC section 7)."""

from datetime import datetime
from typing import Literal, NamedTuple

from pydantic import BaseModel

Level = Literal["High", "Medium", "Low"]


class AuditRequest(BaseModel):
    url: str


class Issue(BaseModel):
    id: str
    dimension: str
    title: str
    explanation: str
    how_to_fix: str
    severity: Level
    effort: Level
    priority: float


class SubScore(BaseModel):
    key: str
    name: str
    weight: float
    score: int | None
    detail: str


class Dimension(BaseModel):
    key: str
    name: str
    weight: float
    score: int
    label: str
    sub_scores: list[SubScore]
    issues: list[Issue]


class BotAccess(BaseModel):
    bot: str
    allowed: bool


class Benchmarks(BaseModel):
    industry_average: int
    top_sites: int
    is_sample: bool
    sample_size: int
    updated_at: datetime | None


class Report(BaseModel):
    url: str
    final_url: str
    title: str | None
    analyzed_at: datetime
    duration_seconds: float
    overall_score: int
    label: str
    geo_ready: bool
    summary: str
    bot_access: list[BotAccess]
    dimensions: list[Dimension]
    top_fixes: list[Issue]


class DimensionCheck(NamedTuple):
    """Raw output of one dimension's rule checks, before scoring."""

    sub_scores: list[SubScore]
    issues: list[Issue]
