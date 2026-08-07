"""Write the verdict back into the DataHub graph.

The hackathon's top criterion asks submissions to "go beyond reading metadata
and contribute back to the graph". A blast-radius analysis is expensive to
produce and immediately useful to the next person or agent who touches the
same column, so it is persisted as a documentation link on the dataset rather
than living only in a PR comment that scrolls away.
"""

from __future__ import annotations

import datetime as _dt

from .datahub_client import ColumnBlastRadius, DataHubClient, DataHubError
from .severity import assess

_ADD_LINK = """
mutation addLink($input: AddLinkInput!) {
  addLink(input: $input)
}
"""

_REMOVE_LINK = """
mutation removeLink($input: RemoveLinkInput!) {
  removeLink(input: $input)
}
"""

_EXISTING_LINKS = """
query links($urn: String!) {
  dataset(urn: $urn) {
    institutionalMemory { elements { label url } }
  }
}
"""

_ADD_TAG = """
mutation addTag($input: TagAssociationInput!) {
  addTag(input: $input)
}
"""

_CREATE_TAG = """
mutation createTag($input: CreateTagInput!) {
  createTag(input: $input)
}
"""


def _tag_urn(name: str) -> str:
    return f"urn:li:tag:{name}"


def ensure_tag(client: DataHubClient, name: str, description: str) -> str:
    """Create a tag if it does not exist; return its URN."""
    urn = _tag_urn(name)
    try:
        client.gql(_CREATE_TAG, {"input": {"id": name, "name": name, "description": description}})
    except DataHubError:
        # Already exists — that is the normal path after the first run.
        pass
    return urn


def write_verdict(
    client: DataHubClient,
    radius: ColumnBlastRadius,
    change_description: str,
    pr_url: str | None = None,
) -> str:
    """Persist the verdict to the dataset. Returns the DataHub entity URL."""
    verdict = assess(radius)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    label = (
        f"Blast Radius [{verdict.severity.value}] {change_description} — "
        f"{len(radius.hits)} downstream across {len(radius.platforms)} platforms ({stamp})"
    )

    # A link is the one writeback that carries the full finding and survives
    # in the UI where the next engineer will look.
    link_url = pr_url or "https://github.com/ritesh59697/datahub-blast-radius#blast-radius"

    # DataHub rejects a duplicate (url, label) pair, and this tool is expected
    # to run on every push. Clear our previous verdicts for this column so the
    # graph shows the current finding rather than an append-only pile.
    marker = f"Blast Radius ["
    column_marker = f"{radius.dataset_name}.{radius.column}"
    try:
        existing = client.gql(_EXISTING_LINKS, {"urn": radius.dataset_urn})
        elements = ((existing.get("dataset") or {}).get("institutionalMemory") or {}).get("elements", [])
        for element in elements:
            if element["label"].startswith(marker) and column_marker in element["label"]:
                client.gql(_REMOVE_LINK, {
                    "input": {"linkUrl": element["url"], "resourceUrn": radius.dataset_urn}
                })
    except DataHubError:
        # Cleanup is best-effort; a stale link must not block the new verdict.
        pass

    try:
        client.gql(_ADD_LINK, {
            "input": {
                "linkUrl": link_url,
                "label": label,
                "resourceUrn": radius.dataset_urn,
            }
        })
    except DataHubError as exc:
        # An identical verdict already on the entity is success, not failure.
        if "already exists" not in str(exc):
            raise

    # Tag the dataset so the finding is discoverable by search, not just by
    # opening the entity page.
    if verdict.blocking:
        tag = ensure_tag(
            client,
            "HighBlastRadius",
            "Changes to this dataset break downstream dashboards, ML models, or reports.",
        )
        try:
            client.gql(_ADD_TAG, {
                "input": {"tagUrn": tag, "resourceUrn": radius.dataset_urn}
            })
        except DataHubError:
            pass

    return f"http://localhost:9002/dataset/{radius.dataset_urn}"
