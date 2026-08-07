"""Thin GraphQL client for DataHub.

Deliberately does not use datahub.sdk's lineage helpers: as of acryl-datahub
1.7.0, ``client.lineage.get_lineage()`` calls ``DatasetUrn.from_string()`` on
every lineage result, so any column whose lineage reaches a Chart raises

    Passed an urn of type chart to the from_string method of DatasetUrn

which is exactly the set of columns worth analysing. Raw GraphQL has no such
limitation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests

DEFAULT_GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")

# DataHub expresses lineage distance as "1", "2", "3+" — there is no "3".
ALL_DEGREES = ["1", "2", "3+"]


class DataHubError(RuntimeError):
    pass


@dataclass
class LineageHit:
    """One downstream entity discovered from a column."""

    urn: str
    entity_type: str
    name: str
    platform: str
    degree: int

    @property
    def is_bi_asset(self) -> bool:
        return self.entity_type in {"CHART", "DASHBOARD"}

    @property
    def is_ml_asset(self) -> bool:
        return self.entity_type in {"MLMODEL", "MLFEATURE_TABLE", "MLFEATURE"}

    @property
    def is_pipeline(self) -> bool:
        return self.entity_type in {"DATA_JOB", "DATA_FLOW"}


@dataclass(frozen=True)
class Owner:
    urn: str
    username: str
    display_name: str
    email: str | None = None
    is_group: bool = False

    @property
    def label(self) -> str:
        return self.display_name or self.username


@dataclass
class ColumnBlastRadius:
    """Everything that breaks if one column changes."""

    dataset_urn: str
    dataset_name: str
    column: str
    hits: list[LineageHit] = field(default_factory=list)
    owners: list[Owner] = field(default_factory=list)
    #: urn -> owners, for downstream entities that declare their own.
    downstream_owners: dict[str, list[Owner]] = field(default_factory=dict)

    @property
    def notify(self) -> list[tuple[Owner, list[str]]]:
        """Owners to page, each with the names of what breaks for them.

        Ranked by how much of their surface is affected.
        """
        by_owner: dict[Owner, set[str]] = {}
        # Qualify names by platform: three different "order_details" would
        # otherwise collapse into one and understate the impact.
        labels = {h.urn: f"{h.name} ({h.platform})" for h in self.hits}
        for urn, owners in self.downstream_owners.items():
            for owner in owners:
                by_owner.setdefault(owner, set()).add(labels.get(urn, urn))
        for owner in self.owners:
            by_owner.setdefault(owner, set()).add(f"{self.dataset_name} (source)")
        return sorted(
            ((o, sorted(v)) for o, v in by_owner.items()),
            key=lambda kv: (len(kv[1]), kv[0].label),
            reverse=True,
        )

    @property
    def bi_assets(self) -> list[LineageHit]:
        return [h for h in self.hits if h.is_bi_asset]

    @property
    def ml_assets(self) -> list[LineageHit]:
        return [h for h in self.hits if h.is_ml_asset]

    @property
    def pipelines(self) -> list[LineageHit]:
        return [h for h in self.hits if h.is_pipeline]

    @property
    def datasets(self) -> list[LineageHit]:
        return [h for h in self.hits if h.entity_type == "DATASET"]

    @property
    def platforms(self) -> list[str]:
        return sorted({h.platform for h in self.hits if h.platform and h.platform != "?"})

    @property
    def max_depth(self) -> int:
        return max((h.degree for h in self.hits), default=0)


_LINEAGE_Q = """
query blastRadius($urn: String!, $degrees: [String!]!, $count: Int!) {
  searchAcrossLineage(
    input: {
      urn: $urn
      direction: DOWNSTREAM
      query: "*"
      count: $count
      searchFlags: { skipCache: true }
      orFilters: [{ and: [{ field: "degree", values: $degrees }] }]
    }
  ) {
    total
    searchResults {
      degree
      entity {
        urn
        type
        ... on Dataset { name platform { name } }
        ... on Chart { chartId properties { name } platform { name } }
        ... on Dashboard { dashboardId properties { name } platform { name } }
        ... on DataJob { jobId properties { name } }
        ... on DataFlow { flowId properties { name } }
        ... on MLModel { name platform { name } }
        ... on MLFeatureTable { name platform { name } }
      }
    }
  }
}
"""

_DATASET_Q = """
query dataset($urn: String!) {
  dataset(urn: $urn) {
    urn
    name
    platform { name }
    schemaMetadata { fields { fieldPath nativeDataType } }
    ownership {
      owners {
        type
        ownershipType { info { name } }
        owner {
          __typename
          ... on CorpUser {
            urn
            username
            properties { displayName email }
          }
          ... on CorpGroup {
            urn
            name
            properties { displayName email }
          }
        }
      }
    }
  }
}
"""

_ENTITY_OWNERS_Q = """
query entityOwners($urns: [String!]!) {
  entities(urns: $urns) {
    urn
    type
    ... on Dataset { name ownership { owners { owner { __typename ... on CorpUser { urn username properties { displayName email } } ... on CorpGroup { urn name properties { displayName email } } } } } }
    ... on Chart { properties { name } ownership { owners { owner { __typename ... on CorpUser { urn username properties { displayName email } } ... on CorpGroup { urn name properties { displayName email } } } } } }
    ... on Dashboard { properties { name } ownership { owners { owner { __typename ... on CorpUser { urn username properties { displayName email } } ... on CorpGroup { urn name properties { displayName email } } } } } }
  }
}
"""

_SEARCH_DATASET_Q = """
query findDataset($query: String!) {
  search(input: { type: DATASET, query: $query, start: 0, count: 20 }) {
    searchResults {
      entity {
        urn
        ... on Dataset {
          name
          platform { name }
          schemaMetadata { fields { fieldPath } }
        }
      }
    }
  }
}
"""


def _platform_from_urn(urn: str) -> str:
    if "dataPlatform:" in urn:
        return urn.split("dataPlatform:")[1].split(",")[0]
    if urn.startswith("urn:li:dataJob:(urn:li:dataFlow:("):
        return urn.split("dataFlow:(")[1].split(",")[0]
    return "?"


class DataHubClient:
    def __init__(self, server: str = DEFAULT_GMS, token: str | None = None) -> None:
        self.server = server.rstrip("/")
        self.session = requests.Session()
        headers = {"Content-Type": "application/json"}
        token = token or os.environ.get("DATAHUB_GMS_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.session.post(
                f"{self.server}/api/graphql",
                json={"query": query, "variables": variables},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise DataHubError(f"Cannot reach DataHub at {self.server}: {exc}") from exc

        if resp.status_code != 200:
            raise DataHubError(f"DataHub returned HTTP {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        if "errors" in payload:
            raise DataHubError(f"GraphQL error: {str(payload['errors'])[:300]}")
        return payload["data"]

    def health(self) -> bool:
        try:
            r = self.session.get(f"{self.server}/health", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def schema_field_urn(self, dataset_urn: str, column: str) -> str:
        return f"urn:li:schemaField:({dataset_urn},{column})"

    def get_dataset(self, dataset_urn: str) -> dict[str, Any] | None:
        return self.gql(_DATASET_Q, {"urn": dataset_urn}).get("dataset")

    def find_dataset(self, name: str, platform: str | None = None) -> list[dict[str, Any]]:
        """Resolve a table name (e.g. from a dbt model) to candidate datasets."""
        results = self.gql(_SEARCH_DATASET_Q, {"query": name})["search"]["searchResults"]
        out = [r["entity"] for r in results]
        if platform:
            out = [e for e in out if (e.get("platform") or {}).get("name") == platform]
        return out

    @staticmethod
    def _parse_owners(ownership: dict[str, Any] | None) -> list[Owner]:
        if not ownership:
            return []
        owners: list[Owner] = []
        for entry in ownership.get("owners", []):
            o = entry.get("owner") or {}
            if not o.get("urn"):
                continue
            props = o.get("properties") or {}
            raw_name = o.get("username") or o.get("name") or ""
            # The showcase datapack encodes usernames as "b2fd91.sam@example.com";
            # the human-readable identity lives in properties.
            display = props.get("displayName") or raw_name.split(".", 1)[-1]
            owners.append(Owner(
                urn=o["urn"],
                username=raw_name,
                display_name=display,
                email=props.get("email"),
                is_group=o.get("__typename") == "CorpGroup",
            ))
        return owners

    def get_owners(self, dataset_urn: str) -> list[Owner]:
        ds = self.get_dataset(dataset_urn)
        return self._parse_owners((ds or {}).get("ownership"))

    def get_owners_for(self, urns: list[str]) -> dict[str, list[Owner]]:
        """Owners of downstream entities — the people a breaking change pages."""
        if not urns:
            return {}
        out: dict[str, list[Owner]] = {}
        # Batch to keep the query well under GMS limits.
        for i in range(0, len(urns), 25):
            chunk = urns[i:i + 25]
            try:
                entities = self.gql(_ENTITY_OWNERS_Q, {"urns": chunk}).get("entities", [])
            except DataHubError:
                continue
            for ent in entities:
                if not ent:
                    continue
                parsed = self._parse_owners(ent.get("ownership"))
                if parsed:
                    out[ent["urn"]] = parsed
        return out

    def blast_radius(
        self,
        dataset_urn: str,
        column: str,
        degrees: list[str] | None = None,
        count: int = 200,
    ) -> ColumnBlastRadius:
        """Every downstream entity that depends on one column."""
        field_urn = self.schema_field_urn(dataset_urn, column)
        data = self.gql(_LINEAGE_Q, {
            "urn": field_urn,
            "degrees": degrees or ALL_DEGREES,
            "count": count,
        })["searchAcrossLineage"]

        hits = []
        for result in data["searchResults"]:
            entity = result["entity"]
            props = entity.get("properties") or {}
            name = (
                entity.get("name")
                or props.get("name")
                or entity.get("chartId")
                or entity.get("dashboardId")
                or entity.get("jobId")
                or entity["urn"].split(",")[-2]
            )
            platform = (entity.get("platform") or {}).get("name") or _platform_from_urn(entity["urn"])
            hits.append(LineageHit(
                urn=entity["urn"],
                entity_type=entity["type"],
                name=name,
                platform=platform,
                degree=result["degree"],
            ))

        ds = self.get_dataset(dataset_urn)
        # Owners of the things that break matter more than owners of the source.
        impacted = [h.urn for h in hits if h.is_bi_asset or h.is_ml_asset or h.entity_type == "DATASET"]
        return ColumnBlastRadius(
            dataset_urn=dataset_urn,
            dataset_name=(ds or {}).get("name", dataset_urn.split(",")[1] if "," in dataset_urn else dataset_urn),
            column=column,
            hits=hits,
            owners=self._parse_owners((ds or {}).get("ownership")),
            downstream_owners=self.get_owners_for(impacted),
        )
