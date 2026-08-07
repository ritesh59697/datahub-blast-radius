"""Probe whether column-level lineage actually resolves in the loaded graph.

This is the make-or-break check for the demo: table-level fan-out is easy, but
the pitch depends on tracing a *specific column* downstream.
"""

import json
import sys

from datahub.sdk import DataHubClient

CANDIDATES = [
    ("urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.customers,PROD)",
     ["customer_id", "cust_email", "credit_limit", "dob"]),
    ("urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
     ["order_id", "customer_id", "order_total", "order_status"]),
    ("urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.order_items,PROD)",
     ["order_id", "product_id", "unit_price", "quantity"]),
]


def main() -> None:
    client = DataHubClient(server="http://localhost:8080")
    findings = []

    for urn, columns in CANDIDATES:
        table = urn.split(",")[1].split(".")[-1]
        print(f"\n=== {table} ===")
        for col in columns:
            try:
                results = client.lineage.get_lineage(
                    source_urn=urn,
                    source_column=col,
                    direction="downstream",
                    max_hops=3,
                )
            except Exception as exc:  # noqa: BLE001 - probe, keep going
                print(f"  {col:<16} ERROR {str(exc)[:100]}")
                continue

            with_paths = [r for r in results if getattr(r, "paths", None)]
            print(f"  {col:<16} downstream={len(results):<4} with_column_paths={len(with_paths)}")

            for r in with_paths[:3]:
                for p in (r.paths or [])[:1]:
                    hops = [u.split(",")[-1].rstrip(")") for u in p] if isinstance(p, list) else [str(p)]
                    print(f"      path: {' -> '.join(hops[:6])}")

            findings.append({
                "table": table,
                "column": col,
                "downstream": len(results),
                "column_paths": len(with_paths),
                "sample": [
                    {"urn": r.urn, "type": getattr(r, "type", None), "hops": getattr(r, "hops", None)}
                    for r in results[:5]
                ],
            })

    with open("scripts/column_lineage_probe.json", "w") as fh:
        json.dump(findings, fh, indent=2, default=str)

    best = sorted(findings, key=lambda f: (f["column_paths"], f["downstream"]), reverse=True)
    print("\n" + "=" * 70)
    print("RANKED BY COLUMN-LEVEL REACH")
    print("=" * 70)
    for f in best[:8]:
        print(f"  {f['table']}.{f['column']:<16} downstream={f['downstream']:<4} column_paths={f['column_paths']}")

    if not any(f["column_paths"] for f in findings):
        print("\n!! No column-level paths found. Demo must use table-level lineage.")
        sys.exit(3)


if __name__ == "__main__":
    main()
