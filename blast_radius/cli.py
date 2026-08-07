"""Blast Radius CLI.

    blast-radius analyze --diff pr.diff
    blast-radius analyze --column orders.order_date
    blast-radius analyze --diff pr.diff --post-pr 7 --repo owner/name
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .datahub_client import ColumnBlastRadius, DataHubClient, DataHubError
from .diff_parser import ColumnChange, parse_diff
from .render import render_comment, render_terminal
from .severity import Severity, assess
from .writeback import write_verdict


def _resolve_dataset(client: DataHubClient, table: str, platform: str | None) -> str | None:
    """Map a dbt model name to a DataHub dataset URN."""
    candidates = client.find_dataset(table, platform=platform)
    if not candidates:
        return None
    # Prefer an exact leaf-name match over a fuzzy search hit.
    for entity in candidates:
        if entity.get("name", "").split(".")[-1].lower() == table.lower():
            return entity["urn"]
    return candidates[0]["urn"]


def _analyze_change(
    client: DataHubClient,
    change: ColumnChange,
    platform: str | None,
) -> tuple[ColumnBlastRadius, str] | None:
    dataset_urn = _resolve_dataset(client, change.table, platform)
    if not dataset_urn:
        print(f"  ! no DataHub dataset matches '{change.table}' — skipping", file=sys.stderr)
        return None
    radius = client.blast_radius(dataset_urn, change.column)
    return radius, change.describe()


def cmd_analyze(args: argparse.Namespace) -> int:
    client = DataHubClient(server=args.gms)
    if not client.health():
        print(f"error: DataHub not reachable at {args.gms}", file=sys.stderr)
        print("hint: run `datahub docker quickstart` first", file=sys.stderr)
        return 2

    analyses: list[tuple[ColumnBlastRadius, str]] = []

    if args.column:
        if "." not in args.column:
            print("error: --column must be TABLE.COLUMN", file=sys.stderr)
            return 2
        table, column = args.column.rsplit(".", 1)
        urn = args.dataset_urn or _resolve_dataset(client, table, args.platform)
        if not urn:
            print(f"error: no dataset found for '{table}'", file=sys.stderr)
            return 2
        analyses.append((client.blast_radius(urn, column), f"Change {table}.{column}"))
    else:
        diff_text = (
            Path(args.diff).read_text()
            if args.diff != "-"
            else sys.stdin.read()
        )
        changes = [c for c in parse_diff(diff_text) if c.breaking]
        if not changes:
            print("No breaking column changes detected in diff.")
            return 0
        print(f"Detected {len(changes)} breaking change(s):", file=sys.stderr)
        for change in changes:
            print(f"  - {change.describe()}", file=sys.stderr)
            result = _analyze_change(client, change, args.platform)
            if result:
                analyses.append(result)

    if not analyses:
        print("Nothing to report — no changed columns resolved to DataHub datasets.")
        return 0

    worst = Severity.LOW
    sections: list[str] = []
    for radius, description in analyses:
        verdict = assess(radius)
        if verdict.severity.rank > worst.rank:
            worst = verdict.severity
        if args.format == "markdown":
            sections.append(render_comment(radius, description, datahub_url=args.datahub_url))
        else:
            sections.append(render_terminal(radius, description))

    body = "\n\n".join(sections)
    print(body)

    if args.writeback:
        for radius, description in analyses:
            try:
                url = write_verdict(client, radius, description)
                print(f"\n✓ verdict written to DataHub: {url}", file=sys.stderr)
            except DataHubError as exc:
                print(f"\n! writeback failed: {exc}", file=sys.stderr)

    if args.post_pr:
        markdown = body if args.format == "markdown" else "\n\n".join(
            render_comment(r, d, datahub_url=args.datahub_url) for r, d in analyses
        )
        cmd = ["gh", "pr", "comment", str(args.post_pr), "--body", markdown]
        if args.repo:
            cmd += ["--repo", args.repo]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"! failed to post comment: {result.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"\n✓ posted to PR #{args.post_pr}", file=sys.stderr)

    # Non-zero exit lets CI block a merge on a critical finding.
    if args.fail_on_critical and worst is Severity.CRITICAL:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="blast-radius",
        description="Report the real downstream impact of a data schema change.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="analyze a diff or a single column")
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff", help="path to a unified diff, or '-' for stdin")
    source.add_argument("--column", help="analyze one column directly, as TABLE.COLUMN")

    analyze.add_argument("--dataset-urn", help="skip lookup and use this dataset URN")
    analyze.add_argument("--platform", help="restrict dataset lookup to a platform")
    analyze.add_argument("--gms", default="http://localhost:8080", help="DataHub GMS URL")
    analyze.add_argument("--datahub-url", default="http://localhost:9002", help="DataHub UI URL")
    analyze.add_argument("--format", choices=["terminal", "markdown"], default="terminal")
    analyze.add_argument("--post-pr", type=int, metavar="N", help="post the report to PR #N")
    analyze.add_argument("--repo", help="owner/name, when posting outside the current repo")
    analyze.add_argument("--writeback", action="store_true",
                         help="persist the verdict to the DataHub graph")
    analyze.add_argument("--fail-on-critical", action="store_true",
                         help="exit non-zero on a critical finding, to block CI")
    analyze.set_defaults(func=cmd_analyze)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DataHubError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
