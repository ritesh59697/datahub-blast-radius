"""Render a blast radius as a PR comment.

The comment is the product. A reviewer sees it inline on the diff, so it must
lead with the consequence, name real assets, and stay skimmable.
"""

from __future__ import annotations

from .datahub_client import ColumnBlastRadius
from .severity import Severity, assess, classify_hit

PLATFORM_ICON = {
    "snowflake": "❄️",
    "dbt": "🔧",
    "looker": "👁️",
    "powerbi": "📊",
    "tableau": "📈",
    "postgres": "🐘",
    "s3": "🪣",
    "spark": "⚡",
    "kafka": "📨",
}

TYPE_LABEL = {
    "DASHBOARD": "Dashboard",
    "CHART": "Chart",
    "DATASET": "Table",
    "DATA_JOB": "Pipeline job",
    "DATA_FLOW": "Pipeline",
    "MLMODEL": "ML model",
    "MLFEATURE_TABLE": "Feature table",
}


def _icon(platform: str) -> str:
    return PLATFORM_ICON.get(platform.lower(), "•")


def render_comment(
    radius: ColumnBlastRadius,
    change_description: str,
    datahub_url: str = "http://localhost:9002",
    max_listed: int = 12,
) -> str:
    """Markdown PR comment for one changed column."""
    verdict = assess(radius)
    lines: list[str] = []

    lines.append(f"## {verdict.severity.emoji} Blast Radius: `{change_description}`")
    lines.append("")
    lines.append(f"**{verdict.headline}**")
    lines.append("")

    if not radius.hits:
        lines.append("No downstream consumers found in DataHub. Safe to merge.")
        return "\n".join(lines)

    lines.append(
        f"Traced `{radius.dataset_name}.{radius.column}` through DataHub lineage: "
        f"**{len(radius.hits)} downstream entities** across "
        f"**{len(radius.platforms)} platforms**, up to **{radius.max_depth} hops** deep."
    )
    lines.append("")

    # Highest-severity casualties first — this is what wins or loses attention.
    critical = [h for h in radius.hits if classify_hit(h) is Severity.CRITICAL]
    high = [h for h in radius.hits if classify_hit(h) is Severity.HIGH]

    if critical or high:
        lines.append("### What breaks")
        lines.append("")
        lines.append("| | Asset | Type | Platform | Hops |")
        lines.append("|---|---|---|---|---|")
        for hit in sorted(critical + high, key=lambda h: (-classify_hit(h).rank, h.degree)):
            sev = classify_hit(hit)
            label = TYPE_LABEL.get(hit.entity_type, hit.entity_type.title())
            lines.append(
                f"| {sev.emoji} | **{hit.name}** | {label} | "
                f"{_icon(hit.platform)} {hit.platform} | {hit.degree} |"
            )
        lines.append("")

    datasets = radius.datasets
    if datasets:
        shown = min(len(datasets), max_listed)
        summary = (
            f"Plus {len(datasets)} downstream tables and views"
            if shown == len(datasets)
            else f"Plus {len(datasets)} downstream tables and views (showing {shown})"
        )
        lines.append(f"<details><summary>{summary}</summary>")
        lines.append("")
        lines.append("| Table | Platform | Hops |")
        lines.append("|---|---|---|")
        for hit in sorted(datasets, key=lambda h: h.degree)[:max_listed]:
            lines.append(f"| {hit.name} | {_icon(hit.platform)} {hit.platform} | {hit.degree} |")
        if len(datasets) > max_listed:
            lines.append(f"| _…{len(datasets) - max_listed} more_ | | |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    notify = radius.notify
    if notify:
        lines.append("### Who needs to know")
        lines.append("")
        for owner, affected in notify[:6]:
            kind = "team" if owner.is_group else ""
            contact = f" · `{owner.email}`" if owner.email else ""
            preview = ", ".join(affected[:3])
            more = f" +{len(affected) - 3} more" if len(affected) > 3 else ""
            lines.append(f"- **{owner.label}**{f' ({kind})' if kind else ''}{contact} — owns {preview}{more}")
        lines.append("")

    if verdict.reasons:
        lines.append("### Why this severity")
        lines.append("")
        for reason in verdict.reasons:
            lines.append(f"- {reason}")
        lines.append("")

    lines.append("---")
    lines.append(
        f"<sub>Analysed by [Blast Radius](https://github.com/ritesh59697/datahub-blast-radius) "
        f"using [DataHub]({datahub_url}) column-level lineage. "
        f"Column-precise within the warehouse; entity-level for BI and ML assets. "
        f"Verdict written back to the DataHub graph.</sub>"
    )

    return "\n".join(lines)


def render_terminal(radius: ColumnBlastRadius, change_description: str) -> str:
    """Plain-text version for local runs and CI logs."""
    verdict = assess(radius)
    out: list[str] = []
    bar = "=" * 74
    out.append(bar)
    out.append(f"BLAST RADIUS: {change_description}")
    out.append(bar)
    out.append(f"Severity : {verdict.severity.value.upper()}")
    out.append(f"Verdict  : {verdict.headline}")
    out.append(
        f"Scope    : {len(radius.hits)} entities / "
        f"{len(radius.platforms)} platforms / {radius.max_depth} hops"
    )
    out.append("")

    for group, title in (
        ([h for h in radius.hits if h.entity_type == "DASHBOARD"], "DASHBOARDS"),
        ([h for h in radius.hits if h.entity_type == "CHART"], "CHARTS"),
        (radius.ml_assets, "ML ASSETS"),
        (radius.pipelines, "PIPELINE JOBS"),
        (radius.datasets, "TABLES / VIEWS"),
    ):
        if not group:
            continue
        out.append(f"{title} ({len(group)})")
        for hit in sorted(group, key=lambda h: h.degree):
            out.append(f"  [{classify_hit(hit).value:<8}] hop{hit.degree} {hit.platform:<10} {hit.name}")
        out.append("")

    if radius.notify:
        out.append(f"NOTIFY ({len(radius.notify)})")
        for owner, affected in radius.notify[:8]:
            out.append(f"  {owner.label:<22} {(owner.email or '-'):<28} {len(affected)} affected")
        out.append("")

    out.append(bar)
    return "\n".join(out)
