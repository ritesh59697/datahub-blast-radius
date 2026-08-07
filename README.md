# Blast Radius

**A one-line dbt change looks harmless. This bot tells you it breaks the dashboard your
exec team reads on Monday — before you merge it.**

```
🔴 Blast Radius: Rename orders.order_date to order_dt

This change breaks 1 dashboard, 2 charts, and 16 tables.

Traced orders.order_date through DataHub lineage: 21 downstream entities
across 7 platforms, up to 6 hops deep.

  🔴  Order Entry Dashboard             Dashboard   looker     6 hops
  🟠  Orders By Month                   Chart       tableau    6 hops
  🟠  Orders by Day                     Chart       looker     6 hops
  🟠  export_table_orders_to_s3         Pipeline    spark      1 hop

Who needs to know
  Ian Chen · ian.chen@example.com — owns Order Details (looker) +3 more
  David Kim · david.kim@example.com — owns ORDER_DETAILS (snowflake) +3 more
```

**[See it on a real pull request →](https://github.com/ritesh59697/demo-analytics/pull/1)**

---

## The problem

Your reviewer approves the rename. They read the diff, not the lineage graph.

Nobody in that pull request can see that `order_date` flows through S3, into Snowflake,
through three dbt models, into a Looker explore, a PowerBI dataset, four Tableau
worksheets — and finally into the dashboard someone presents on Monday. No single tool
shows all of that at once.

DataHub already knows. It just isn't in the pull request, which is where the decision
gets made.

## What it does

1. Parses a PR diff for column-level schema changes — renames, drops, type changes
2. Resolves each changed column to its DataHub `schemaField` URN
3. Walks column-level lineage downstream, up to 6+ hops across platforms
4. Ranks the casualties by what actually breaks
5. Resolves the humans who own each broken asset
6. Posts the verdict as a PR comment
7. **Writes the finding back into DataHub**, so the next person — or the next agent —
   inherits it instead of rediscovering it

## Severity means something

A reviewer who sees a red banner on every pull request stops reading them. Severity is
driven by *what* breaks, not how much:

| Level | Trigger | Example |
|---|---|---|
| 🔴 CRITICAL | A dashboard or ML model consumes the column | `orders.order_date` |
| 🟠 HIGH | A chart renders it | `orders.order_id` |
| 🟡 MEDIUM | Only derived tables and replication jobs | `customers.nls_language` |
| ⚪ LOW | Nothing downstream depends on it | — |

In this warehouse nearly every column fans out to 3+ platforms, so counting platforms or
downstream totals rates *everything* HIGH and the signal disappears. One dashboard
breaking outranks twenty staging tables changing. The MEDIUM verdict states the absence
of BI impact explicitly, because a reviewer has to trust the quiet ratings as much as the
loud ones.

See [`examples/`](examples/) for one generated artifact per severity level.

## Writing back to the graph

Reading lineage is the easy half. A blast-radius analysis is expensive to produce and
immediately useful to whoever touches that column next, so it is persisted to DataHub:

- an **institutional-memory link** on the dataset carrying the verdict and scope
- a **`HighBlastRadius` tag** so the finding is discoverable by search

Writeback is idempotent — prior verdicts for the same column are cleared before the new
one lands, so running on every push doesn't pile up duplicates.

```bash
blast-radius analyze --column orders.order_date --writeback
```

## Quick start

Requires Docker and Python 3.9+.

```bash
# 1. Start DataHub and load the sample graph
pip install 'acryl-datahub[datahub-rest]'
datahub docker quickstart
datahub datapack load showcase-ecommerce

# 2. Install Blast Radius
git clone https://github.com/ritesh59697/datahub-blast-radius
cd datahub-blast-radius
pip install -e .

# 3. Analyze a column
blast-radius analyze --column orders.order_date --platform postgres
```

Analyze a real pull request:

```bash
gh pr diff 1 > pr.diff
blast-radius analyze --diff pr.diff --repo-root ../my-dbt-project \
  --platform postgres --format markdown --post-pr 1
```

Block a merge in CI:

```bash
blast-radius analyze --diff pr.diff --fail-on-critical
```

Generate a migration plan:

```bash
blast-radius analyze --diff pr.diff --migration ./migrations/
```

## How it uses DataHub

| DataHub capability | Used for |
|---|---|
| `searchAcrossLineage` on `schemaField` URNs | Column-level downstream traversal |
| Entity graph (Chart, Dashboard, DataJob, MLModel) | Identifying what actually breaks |
| Ownership aspect | Resolving who to notify |
| `addLink` / institutional memory | Persisting the verdict |
| `createTag` / `addTag` | Making findings searchable |

### Scope, stated honestly

DataHub's column-level lineage is dataset-to-dataset. Blast Radius reports **column-precise
paths inside the warehouse** and **entity-level casualties** for BI assets and ML models.
It does not claim column-precision into Looker or Tableau, and the generated migration SQL
is a reviewable starting point — DataHub knows *that* a column is consumed, not the shape
of every query consuming it.

### A note on the DataHub Python SDK

This project queries GraphQL directly rather than using `datahub.sdk`'s lineage helpers.
As of `acryl-datahub` 1.7.0, `client.lineage.get_lineage()` calls `DatasetUrn.from_string()`
on every result, so any column whose lineage reaches a Chart raises:

```
Passed an urn of type chart to the from_string method of DatasetUrn
```

That is exactly the set of columns worth analysing. Raw GraphQL against the same
`schemaField` URN returns all results, charts included.

Root cause: `_create_lineage_result` calls `DatasetUrn.from_string()` on the parent of
every `SCHEMA_FIELD` in the returned paths, but the Tableau connector legitimately emits
chart-parented schema fields like
`urn:li:schemaField:(urn:li:chart:(tableau,<id>),ORDERS_COUNT)`. One unparseable entry
discards the entire result set.

Reported upstream with a reproduction and suggested fix:
**[datahub-project/datahub#18964](https://github.com/datahub-project/datahub/issues/18964)**

## Development

```bash
pip install -e '.[dev]'
pytest
```

23 tests cover the diff parser (renames, drops, aliases, dbt YAML, and the cases that must
*not* register — column reordering, cross-hunk pairing) and the severity model (that
breadth alone never escalates, and one dashboard outranks twenty tables).

## Built for

[Build with DataHub: The Agent Hackathon](https://datahub.devpost.com/) — Metadata-Aware
Code Generation & Development.

## License

Apache 2.0 — see [LICENSE](LICENSE).
