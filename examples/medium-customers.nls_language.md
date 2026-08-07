## 🟡 Blast Radius: `Change customers.nls_language`

**This change touches 3 downstream tables and 2 pipeline jobs, but no dashboards, charts, or ML models.**

Traced `customers.nls_language` through DataHub lineage: **5 downstream entities** across **4 platforms**, up to **3 hops** deep.

### What breaks

| | Asset | Type | Platform | Hops |
|---|---|---|---|---|
| 🟡 | **export_table_customers_to_s3** | Pipeline job | ⚡ spark | 1 |
| 🟡 | **import_table_customers_to_snowflake** | Pipeline job | ⚡ spark | 2 |

<details><summary>Plus 3 downstream tables and views</summary>

| Table | Platform | Hops |
|---|---|---|
| customers | 🪣 s3 | 1 |
| CUSTOMERS | ❄️ snowflake | 2 |
| customers | 🔧 dbt | 3 |

</details>

### Who needs to know

- **Julia Novak** · `julia.novak@example.com` — owns customers (dbt)
- **Ian Chen** · `ian.chen@example.com` — owns customers (dbt)
- **Data Platform Team** (team) · `data-platform@example.com` — owns customers (dbt)

### Why this severity

- 2 pipeline jobs move it (export_table_customers_to_s3, import_table_customers_to_snowflake)
- impact crosses 4 platforms: dbt, s3, snowflake, spark
- 3 downstream tables/views derive from it
- no dashboards, charts, or ML models consume it

---
<sub>Analysed by [Blast Radius](https://github.com/ritesh59697/datahub-blast-radius) using [DataHub](http://localhost:9002) column-level lineage. Column-precise within the warehouse; entity-level for BI and ML assets. Verdict written back to the DataHub graph.</sub>
