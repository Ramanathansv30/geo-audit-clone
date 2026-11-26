"""The issue catalog (SPEC section 6). Dictionary order is the catalog order used for sorting."""

from typing import NamedTuple

import config
from models import Issue, Level


class IssueTemplate(NamedTuple):
    dimension: str
    severity: Level
    effort: Level
    title: str
    explanation: str
    how_to_fix: str


CATALOG: dict[str, IssueTemplate] = {
    "page_error": IssueTemplate(
        "technical", "High", "Low",
        "Page returned HTTP {status}",
        "The server answered with status {status} instead of 200, so AI crawlers may skip this page.",
        "Make the URL return 200, or link to the final working address directly.",
    ),
    "noindex": IssueTemplate(
        "technical", "High", "Low",
        "Page is set to noindex",
        "A robots meta tag or X-Robots-Tag header asks search and AI engines not to index this page.",
        "Remove noindex from the robots meta tag and the X-Robots-Tag header if this page should be found.",
    ),
    "bot_blocked": IssueTemplate(
        "technical", "High", "Low",
        "AI bot blocked: {bot}",
        "Your robots.txt blocks {bot}, so {product} can't read this page.",
        "Remove the Disallow rule for {bot} in robots.txt.",
    ),
    "not_https": IssueTemplate(
        "authority", "High", "Medium",
        "Page is not using HTTPS",
        "The page loads over plain HTTP, which AI engines and browsers treat as less trustworthy.",
        "Install a TLS certificate and redirect every HTTP URL to its HTTPS version.",
    ),
    "missing_title": IssueTemplate(
        "technical", "Medium", "Low",
        "Missing page title",
        "There is no <title> tag, so AI engines have no short name to show when they cite the page.",
        "Add a <title> of 50-60 characters that names the page topic and your brand.",
    ),
    "missing_meta_description": IssueTemplate(
        "technical", "Medium", "Low",
        "Missing meta description",
        "There is no meta description, so engines have to guess what the page is about.",
        'Add <meta name="description"> with a one or two sentence summary under 160 characters.',
    ),
    "meta_description_too_long": IssueTemplate(
        "technical", "Low", "Low",
        "Meta description is {n} characters (keep under 160)",
        "Long descriptions get cut off, so the most important part of the summary may be lost.",
        "Shorten the meta description to 160 characters or fewer, leading with the key point.",
    ),
    "no_structured_data": IssueTemplate(
        "technical", "High", "Medium",
        "No structured data (JSON-LD)",
        "The page has no JSON-LD, so AI engines can't reliably tell what kind of content it is or who published it.",
        "Add a JSON-LD block with a fitting schema.org type such as Article, Product or Organization.",
    ),
    "slow_page": IssueTemplate(
        "technical", "Low", "High",
        "Page is slow ({t} s to load)",
        "Slow pages are crawled less often and may time out for AI crawlers.",
        "Compress images, enable caching and reduce server response time to get under 2 seconds.",
    ),
    "no_faq": IssueTemplate(
        "answer_first", "Medium", "Medium",
        "No FAQ or question-style headings",
        "AI answers are built around questions, and this page has few headings phrased as questions.",
        "Add an FAQ section, or rewrite key subheadings as the questions your readers ask.",
    ),
    "long_intro": IssueTemplate(
        "answer_first", "Low", "Low",
        "Opening paragraph doesn't give a short answer",
        "The first paragraph after the main heading is missing, too short or too long to quote as an answer.",
        "Start with a 20-80 word paragraph that answers the page's main question directly.",
    ),
    "no_lists": IssueTemplate(
        "answer_first", "Low", "Low",
        "No lists or tables",
        "Lists and tables are easy for AI engines to extract, and this page has none.",
        "Turn steps, features or comparisons into bulleted lists or a table.",
    ),
    "no_author": IssueTemplate(
        "authority", "Medium", "Low",
        "No author shown",
        "No author is named, which makes the content harder to trust and cite.",
        'Show the author\'s name on the page and add an "author" field to your JSON-LD.',
    ),
    "no_org_schema": IssueTemplate(
        "authority", "Low", "Low",
        "No Organization or Person structured data",
        "Engines can't confirm which organization or person stands behind this page.",
        "Add Organization (or Person) JSON-LD with your name, logo and official profiles.",
    ),
    "no_outbound_sources": IssueTemplate(
        "authority", "Low", "Low",
        "No links to outside sources",
        "The main content doesn't link to any external source to back up its claims.",
        "Link to a few trustworthy sources such as studies, official docs or data providers.",
    ),
    "few_numbers": IssueTemplate(
        "authority", "Low", "Medium",
        "No numbers or facts to back up claims",
        "The text has no figures, dates or statistics, which AI engines like to quote.",
        "Add concrete numbers such as prices, measurements, dates or survey results.",
    ),
    "h1_issue": IssueTemplate(
        "comprehension", "Medium", "Low",
        "Page should have exactly one H1 (found {n})",
        "A single H1 tells engines what the page is about; none or several makes that unclear.",
        "Use exactly one H1 for the page title and H2-H6 for sections.",
    ),
    "skipped_heading_levels": IssueTemplate(
        "comprehension", "Low", "Low",
        "Heading levels are skipped",
        "Headings jump levels (for example H2 to H4), which breaks the page outline.",
        "Nest headings in order: H2 under H1, H3 under H2, and so on.",
    ),
    "few_subheadings": IssueTemplate(
        "comprehension", "Low", "Low",
        "Long page with few subheadings",
        "This is a long page with fewer than two H2 sections, so it is hard to split into answers.",
        "Break the content into sections with descriptive H2 headings.",
    ),
    "hard_to_read": IssueTemplate(
        "comprehension", "Low", "Medium",
        "Text is hard to read",
        "Long sentences and complex words make the text hard to understand and summarise.",
        "Use shorter sentences and plainer words; aim for a Flesch score above 60.",
    ),
    "no_dates": IssueTemplate(
        "freshness", "Medium", "Low",
        "No published or updated date",
        "Without dates, AI engines can't tell whether the information is current.",
        "Show published and updated dates, and add datePublished and dateModified to JSON-LD.",
    ),
    "old_content": IssueTemplate(
        "freshness", "Low", "Medium",
        "Content looks out of date",
        "The newest date on the page is more than a year old, so engines may prefer fresher sources.",
        "Review and update the content, then update dateModified.",
    ),
    "thin_content": IssueTemplate(
        "depth", "Medium", "High",
        "Thin content ({n} words)",
        "The main content is short, so there is little for AI engines to quote or learn from.",
        "Expand the page to at least 300 words of useful detail, examples and answers.",
    ),
    "images_missing_alt": IssueTemplate(
        "depth", "Low", "Low",
        "{k} of {n} images have no alt text",
        "Images without alt text can't be understood by crawlers or screen readers.",
        "Add a short, descriptive alt attribute to every meaningful image.",
    ),
}

CATALOG_ORDER = {issue_id: position for position, issue_id in enumerate(CATALOG)}


def priority_for(severity: Level, effort: Level) -> float:
    """Severity points divided by effort cost, rounded for display."""
    return round(config.SEVERITY_POINTS[severity] / config.EFFORT_COST[effort], 2)


def make_issue(issue_id: str, **values: object) -> Issue:
    """Build an Issue from the catalog, filling {placeholders} with values."""
    template = CATALOG[issue_id]
    return Issue(
        id=issue_id,
        dimension=template.dimension,
        title=template.title.format(**values),
        explanation=template.explanation.format(**values),
        how_to_fix=template.how_to_fix.format(**values),
        severity=template.severity,
        effort=template.effort,
        priority=priority_for(template.severity, template.effort),
    )
