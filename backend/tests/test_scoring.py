import pytest

import config
from issues import make_issue
from models import DimensionCheck, SubScore
from scoring import build_report, label_for, round_half_up, sort_issues, weighted_score

REFERENCE_SUB_SCORES = {
    "answer_first": {"faq": 50, "intro": 100, "lists": 70},
    "technical": {"crawlability": 75, "structured": 30, "speed": 80},
    "authority": {"author": 40, "sources": 60, "numbers": 70},
    "comprehension": {"headings": 90, "readability": 87, "identity": 70},
    "freshness": {"dates": 50, "recency": 75},
    "depth": {"words": 70, "alt": 50},
}
REFERENCE_DIMENSION_SCORES = {
    "answer_first": 73,
    "technical": 63,
    "authority": 55,
    "comprehension": 85,
    "freshness": 65,
    "depth": 62,
}
REFERENCE_ISSUES = [
    make_issue("bot_blocked", bot="GPTBot", product="ChatGPT"),
    make_issue("no_structured_data"),
    make_issue("meta_description_too_long", n=180),
    make_issue("no_faq"),
    make_issue("no_author"),
    make_issue("no_org_schema"),
    make_issue("skipped_heading_levels"),
    make_issue("images_missing_alt", k=1, n=2),
]


def reference_checks(**score_overrides: int) -> dict[str, DimensionCheck]:
    """The SPEC 5.8 example as check results, with optional sub-score overrides."""
    result = {}
    for dimension, sub_scores in REFERENCE_SUB_SCORES.items():
        definitions = config.DIMENSIONS[dimension]["sub_scores"]
        result[dimension] = DimensionCheck(
            sub_scores=[
                SubScore(
                    key=key,
                    name=definitions[key][0],
                    weight=definitions[key][1],
                    score=score_overrides.get(key, score),
                    detail="",
                )
                for key, score in sub_scores.items()
            ],
            issues=[issue for issue in REFERENCE_ISSUES if issue.dimension == dimension],
        )
    return result


def report_for(checks: dict[str, DimensionCheck]):
    return build_report(
        url="https://example.com/",
        final_url="https://example.com/",
        title="Example",
        checks=checks,
        bot_access=[],
        duration_seconds=1.23,
    )


def test_reference_example():
    report = report_for(reference_checks())

    assert {d.key: d.score for d in report.dimensions} == REFERENCE_DIMENSION_SCORES
    assert report.overall_score == 67
    assert report.label == "Good"
    assert report.geo_ready is False


def test_reference_example_with_full_crawlability():
    report = report_for(reference_checks(crawlability=100))

    assert next(d.score for d in report.dimensions if d.key == "technical") == 75
    assert report.overall_score == 70
    assert report.geo_ready is True


def test_reference_top_fixes_and_summary():
    report = report_for(reference_checks())

    assert [issue.id for issue in report.top_fixes] == [
        "bot_blocked",
        "no_author",
        "no_structured_data",
        "no_faq",
        "meta_description_too_long",
    ]
    assert report.summary == "Good overall. Biggest issue: AI bot blocked: GPTBot."


def test_report_shape():
    report = report_for(reference_checks())

    assert [d.key for d in report.dimensions] == list(config.DIMENSIONS)
    assert report.duration_seconds == 1.2
    assert report.analyzed_at.microsecond == 0


def test_summary_without_issues():
    checks = {key: check._replace(issues=[]) for key, check in reference_checks().items()}

    assert report_for(checks).summary == "Good overall. No major issues found."


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (0.5, 1), (62.5, 63), (84.8, 85), (67.25, 67), (69.65, 70)])
def test_round_half_up(value, expected):
    assert round_half_up(value) == expected


def test_round_half_up_absorbs_float_noise():
    assert round_half_up(2.4999999999999996) == 3
    assert round_half_up(2.49) == 2


def test_weighted_score_skips_none_and_renormalises():
    assert weighted_score([(80, 0.6), (None, 0.4)]) == 80
    assert weighted_score([(None, 0.5), (None, 0.5)]) == 0


@pytest.mark.parametrize(
    ("score", "label"),
    [(0, "Poor"), (39, "Poor"), (40, "Needs work"), (59, "Needs work"), (60, "Good"), (79, "Good"), (80, "Excellent"), (100, "Excellent")],
)
def test_labels(score, label):
    assert label_for(score) == label


def test_issue_priority_values():
    assert make_issue("bot_blocked", bot="GPTBot", product="ChatGPT").priority == 3.0
    assert make_issue("no_structured_data").priority == 1.5
    assert make_issue("slow_page", t="2.5").priority == 0.33
    assert make_issue("thin_content", n=10).priority == 0.67


def test_sort_ties_use_severity_then_catalog_order():
    unordered = [make_issue("no_lists"), make_issue("long_intro"), make_issue("no_faq")]

    assert [issue.id for issue in sort_issues(unordered)] == ["no_faq", "long_intro", "no_lists"]
