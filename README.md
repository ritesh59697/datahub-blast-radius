# Blast Radius

**A one-line dbt change looks harmless. This bot tells you it breaks 14 dashboards, 3 ML
models, and the report your CFO reads on Monday — before you merge it.**

Rename a column in a dbt model, open the pull request, and Blast Radius comments with the
real downstream damage: the column's path through your warehouse, every BI asset and ML model
that consumes it, and the owners who need to know. Then it writes that verdict back into
DataHub, so the next person — or the next agent — inherits the finding instead of rediscovering it.

Built for [Build with DataHub: The Agent Hackathon](https://datahub.devpost.com/) —
Metadata-Aware Code Generation & Development.

---

> **Status: in development.** This README describes the target. Sections marked _(pending)_
> are not implemented yet and will be updated as they land.

## The problem

Your reviewer approves the rename. They read the diff, not the lineage graph. Nobody in the
PR can see that `customer_id` feeds a Snowflake view, three dbt models, a Looker explore, a
PowerBI report, and a churn model's feature table — because no single tool shows all of that
at once.

DataHub already knows. It just isn't in the pull request, which is where the decision happens.

## How it works _(pending)_

1. Parse the diff for schema-level changes — renames, drops, type changes
2. Resolve each touched column to its DataHub URN
3. Walk column-level lineage downstream through the warehouse
4. Query `scrollAcrossLineage` for consuming Charts, Dashboards, and ML models
5. Rank casualties by severity, resolve owners from DataHub
6. Post the verdict as a PR comment, and persist it to the dataset in DataHub

**Scope note, stated honestly:** DataHub's column-level lineage is dataset-to-dataset.
Blast Radius reports *column-precise* paths inside the warehouse and *entity-level*
casualties for BI assets and ML models. It does not claim column-precision into Looker.

## Built with

- [DataHub](https://datahub.com/) OSS + Python SDK
- DataHub MCP Server / Agent Context Kit
- `showcase-ecommerce` datapack — 1,049 entities across Snowflake, dbt, Looker, PowerBI,
  Tableau, Spark, PostgreSQL, S3
- GitHub CLI for PR integration

## Quick start _(pending)_

Setup instructions will be added once the pipeline runs end to end.

## Examples _(pending)_

Sample generated artifacts will live in `examples/`.

## License

Apache 2.0 — see [LICENSE](LICENSE).
