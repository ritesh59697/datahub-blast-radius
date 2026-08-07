"""Severity model.

Not every downstream entity is equally alarming. A staging table breaking is a
Tuesday; the executive dashboard breaking is an incident. Severity is driven by
what a human would actually care about being paged for.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .datahub_client import ColumnBlastRadius, LineageHit


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def emoji(self) -> str:
        return {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "⚪",
        }[self]

    @property
    def rank(self) -> int:
        return {
            Severity.CRITICAL: 3,
            Severity.HIGH: 2,
            Severity.MEDIUM: 1,
            Severity.LOW: 0,
        }[self]


@dataclass
class Verdict:
    severity: Severity
    headline: str
    reasons: list[str]

    @property
    def blocking(self) -> bool:
        return self.severity in (Severity.CRITICAL, Severity.HIGH)


def classify_hit(hit: LineageHit) -> Severity:
    """Severity of a single downstream entity breaking."""
    if hit.entity_type == "DASHBOARD":
        return Severity.CRITICAL
    if hit.entity_type in ("CHART", "MLMODEL", "MLFEATURE_TABLE"):
        return Severity.HIGH
    if hit.is_pipeline:
        return Severity.HIGH
    return Severity.MEDIUM


def assess(radius: ColumnBlastRadius) -> Verdict:
    """Turn a blast radius into a verdict a reviewer can act on."""
    dashboards = [h for h in radius.hits if h.entity_type == "DASHBOARD"]
    charts = [h for h in radius.hits if h.entity_type == "CHART"]
    ml = radius.ml_assets
    pipelines = radius.pipelines
    datasets = radius.datasets
    platforms = radius.platforms

    reasons: list[str] = []
    if dashboards:
        plural = len(dashboards) != 1
        reasons.append(
            f"{len(dashboards)} dashboard{'s' if plural else ''} "
            f"{'consume' if plural else 'consumes'} this column "
            f"({', '.join(d.name for d in dashboards[:3])})"
        )
    if charts:
        plural = len(charts) != 1
        reasons.append(f"{len(charts)} chart{'s' if plural else ''} {'render' if plural else 'renders'} it directly")
    if ml:
        plural = len(ml) != 1
        reasons.append(f"{len(ml)} ML asset{'s' if plural else ''} {'depend' if plural else 'depends'} on it")
    if pipelines:
        plural = len(pipelines) != 1
        reasons.append(
            f"{len(pipelines)} pipeline job{'s' if plural else ''} {'move' if plural else 'moves'} it "
            f"({', '.join(p.name for p in pipelines[:2])})"
        )
    if len(platforms) >= 3:
        reasons.append(f"impact crosses {len(platforms)} platforms: {', '.join(platforms)}")
    if datasets:
        reasons.append(f"{len(datasets)} downstream tables/views derive from it")

    if dashboards or ml:
        severity = Severity.CRITICAL
    elif charts or len(platforms) >= 4:
        severity = Severity.HIGH
    elif datasets or pipelines:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    if severity is Severity.LOW:
        headline = f"`{radius.column}` has no known downstream consumers."
    else:
        bits = []
        if dashboards:
            bits.append(f"{len(dashboards)} dashboard{'s' if len(dashboards) != 1 else ''}")
        if charts:
            bits.append(f"{len(charts)} chart{'s' if len(charts) != 1 else ''}")
        if ml:
            bits.append(f"{len(ml)} ML model{'s' if len(ml) != 1 else ''}")
        if datasets:
            bits.append(f"{len(datasets)} table{'s' if len(datasets) != 1 else ''}")
        if not bits:
            bits.append(f"{len(radius.hits)} downstream entities")

        if len(bits) > 1:
            listed = ", ".join(bits[:-1]) + f", and {bits[-1]}"
        else:
            listed = bits[0]
        headline = f"This change breaks {listed}."

    return Verdict(severity=severity, headline=headline, reasons=reasons)
