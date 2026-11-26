"""Weighted averages, labels, issue ordering and report assembly (SPEC sections 5.3-5.8 and 7)."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import TypeVar

import config
from issues import CATALOG_ORDER
from models import BotAccess, Dimension, DimensionCheck, Issue, Report

T = TypeVar("T")


def round_half_up(value: float) -> int:
    """Round a non-negative number to the nearest int, with .5 always going up."""
    return int(value + 0.5 + config.ROUNDING_EPSILON)


def band(value: float, bands: Sequence[tuple[float, T]], default: T) -> T:
    """Result of the first band whose upper bound is greater than value, else default."""
    return next((result for upper, result in bands if value < upper), default)


def weighted_score(pairs: Iterable[tuple[int | None, float]]) -> int:
    """Weighted average of (score, weight) pairs, skipping None scores and renormalising."""
    measured = [(score, weight) for score, weight in pairs if score is not None]
    total_weight = sum(weight for _, weight in measured)
    if not total_weight:
        return 0
    return round_half_up(sum(score * weight for score, weight in measured) / total_weight)


def label_for(score: int) -> str:
    """Human label for a 0-100 score."""
    return band(score, config.LABEL_BANDS, config.LABEL_DEFAULT)


def sort_issues(issues: Iterable[Issue]) -> list[Issue]:
    """Highest priority first, then highest severity, then catalog order."""
    return sorted(
        issues,
        key=lambda issue: (
            -issue.priority,
            -config.SEVERITY_POINTS[issue.severity],
            CATALOG_ORDER[issue.id],
        ),
    )


def build_dimension(key: str, check: DimensionCheck) -> Dimension:
    """Score one dimension from its sub-scores and sort its issues."""
    spec = config.DIMENSIONS[key]
    score = weighted_score((sub.score, sub.weight) for sub in check.sub_scores)
    return Dimension(
        key=key,
        name=spec["name"],
        weight=spec["weight"],
        score=score,
        label=label_for(score),
        sub_scores=check.sub_scores,
        issues=sort_issues(check.issues),
    )


def overall_score(dimensions: Iterable[Dimension]) -> int:
    """Weighted average of the dimension scores."""
    return weighted_score((dimension.score, dimension.weight) for dimension in dimensions)


def summary_line(label: str, top_fixes: Sequence[Issue]) -> str:
    """One-sentence verdict shown under the score."""
    if top_fixes:
        return f"{label} overall. Biggest issue: {top_fixes[0].title}."
    return f"{label} overall. No major issues found."


def build_report(
    url: str,
    final_url: str,
    title: str | None,
    checks: Mapping[str, DimensionCheck],
    bot_access: list[BotAccess],
    duration_seconds: float,
) -> Report:
    """Assemble the full report from every dimension's check results."""
    dimensions = [build_dimension(key, checks[key]) for key in config.DIMENSIONS]
    score = overall_score(dimensions)
    label = label_for(score)
    top_fixes = sort_issues(issue for dimension in dimensions for issue in dimension.issues)
    top_fixes = top_fixes[: config.TOP_FIXES_COUNT]
    return Report(
        url=url,
        final_url=final_url,
        title=title,
        analyzed_at=datetime.now(timezone.utc).replace(microsecond=0),
        duration_seconds=round(duration_seconds, 1),
        overall_score=score,
        label=label,
        geo_ready=score >= config.GEO_READY_THRESHOLD,
        summary=summary_line(label, top_fixes),
        bot_access=bot_access,
        dimensions=dimensions,
        top_fixes=top_fixes,
    )
