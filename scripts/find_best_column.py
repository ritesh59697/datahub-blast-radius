"""Find the column with the richest cross-platform downstream blast radius.

The demo is built around whatever column actually has the best fan-out, chosen
from real graph data rather than guessed. Run this after loading a datapack.

Usage:
    python scripts/find_best_column.py [--limit 40] [--hops 3]
"""

import argparse
import json
from collections import defaultdict

import requests

GMS = "http://localhost:8080"
HEADERS = {"Content-Type": "application/json"}

# Entities that make a demo land: BI assets and ML models a human would recognize.
HIGH_VALUE = {"CHART", "DASHBOARD", "MLMODEL", "MLFEATURE", "MLFEATURE_TABLE", "MLPRIMARY_KEY"}


def gql(query: str, variables: dict) -> dict:
    resp = requests.post(
        f"{GMS}/api/graphql",
        headers=HEADERS,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"], indent=2)[:600])
    return payload["data"]


DATASETS_Q = """
query listDatasets($start: Int!, $count: Int!) {
  search(input: {type: DATASET, query: "*", start: $start, count: $count}) {
    total
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

DOWNSTREAM_Q = """
query downstream($urn: String!, $hops: [String!]) {
  searchAcrossLineage(
    input: {
      urn: $urn
      direction: DOWNSTREAM
      query: "*"
      count: 200
      searchFlags: { skipCache: true }
      orFilters: [{ and: [{ field: "degree", values: $hops }] }]
    }
  ) {
    total
    searchResults {
      degree
      entity {
        urn
        type
        ... on Dataset { name platform { name } }
        ... on Chart { properties { name } platform { name } }
        ... on Dashboard { properties { name } platform { name } }
        ... on MLModel { name platform { name } }
      }
    }
  }
}
"""


def entity_label(entity: dict) -> str:
    props = entity.get("properties") or {}
    name = entity.get("name") or props.get("name") or entity["urn"].split(",")[-2:][0]
    platform = (entity.get("platform") or {}).get("name", "?")
    return f"{entity['type']}::{platform}::{name}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40, help="datasets to probe")
    ap.add_argument("--hops", type=int, default=3, help="max lineage degrees")
    args = ap.parse_args()

    # DataHub degree values are "1", "2", "3+" — there is no "3".
    hops = ["1", "2"][: args.hops] + (["3+"] if args.hops >= 3 else [])

    data = gql(DATASETS_Q, {"start": 0, "count": args.limit})
    results = data["search"]["searchResults"]
    print(f"Scanning {len(results)} of {data['search']['total']} datasets "
          f"(downstream <= {args.hops} hops)\n")

    scored = []
    for item in results:
        ds = item["entity"]
        urn = ds["urn"]
        try:
            down = gql(DOWNSTREAM_Q, {"urn": urn, "hops": hops})["searchAcrossLineage"]
        except Exception as exc:  # noqa: BLE001 - probe script, keep scanning
            print(f"  ! {ds.get('name')}: {str(exc)[:120]}")
            continue

        hits = down["searchResults"]
        if not hits:
            continue

        by_type = defaultdict(int)
        platforms = set()
        labels = []
        for hit in hits:
            ent = hit["entity"]
            by_type[ent["type"]] += 1
            plat = (ent.get("platform") or {}).get("name")
            if plat:
                platforms.add(plat)
            labels.append(entity_label(ent))

        high_value = sum(n for t, n in by_type.items() if t in HIGH_VALUE)
        # Cross-platform reach is what a human reviewer cannot see in one tool.
        score = high_value * 3 + len(platforms) * 5 + down["total"]

        scored.append({
            "urn": urn,
            "name": ds.get("name"),
            "platform": (ds.get("platform") or {}).get("name"),
            "columns": [f["fieldPath"] for f in (ds.get("schemaMetadata") or {}).get("fields", [])],
            "total_downstream": down["total"],
            "high_value": high_value,
            "platforms": sorted(platforms),
            "by_type": dict(by_type),
            "labels": labels[:25],
            "score": score,
        })

    scored.sort(key=lambda r: r["score"], reverse=True)

    print("=" * 78)
    print("TOP BLAST-RADIUS CANDIDATES")
    print("=" * 78)
    for rank, row in enumerate(scored[:8], 1):
        print(f"\n[{rank}] {row['name']}  ({row['platform']})   score={row['score']}")
        print(f"    downstream={row['total_downstream']}  high_value={row['high_value']}")
        print(f"    platforms: {', '.join(row['platforms'])}")
        print(f"    by_type:   {row['by_type']}")
        print(f"    urn: {row['urn']}")
        if row["columns"]:
            print(f"    columns ({len(row['columns'])}): {', '.join(row['columns'][:12])}")
        for label in row["labels"][:6]:
            print(f"      -> {label}")

    with open("scripts/blast_candidates.json", "w") as fh:
        json.dump(scored, fh, indent=2)
    print(f"\nWrote {len(scored)} candidates to scripts/blast_candidates.json")


if __name__ == "__main__":
    main()
