## 🟠 Blast Radius: `Change orders.order_id`

**This change breaks 3 charts, and 24 tables.**

Traced `orders.order_id` through DataHub lineage: **29 downstream entities** across **7 platforms**, up to **6 hops** deep.

### What breaks

| | Asset | Type | Platform | Hops |
|---|---|---|---|---|
| 🟠 | **export_table_orders_to_s3** | Pipeline job | ⚡ spark | 1 |
| 🟠 | **import_table_orders_to_snowflake** | Pipeline job | ⚡ spark | 2 |
| 🟠 | **Popular Products Categories** | Chart | 📈 tableau | 6 |
| 🟠 | **Promotions** | Chart | 📈 tableau | 6 |
| 🟠 | **Order Mode** | Chart | 📈 tableau | 6 |

<details><summary>Plus 24 downstream tables and views (showing 12)</summary>

| Table | Platform | Hops |
|---|---|---|
| orders | 🪣 s3 | 1 |
| ORDERS | ❄️ snowflake | 2 |
| orders | 🔧 dbt | 3 |
| ORDER_DETAILS | ❄️ snowflake | 3 |
| order_details | 🔧 dbt | 4 |
| order_history | 🔧 dbt | 4 |
| order_details | 👁️ looker | 4 |
| ORDER_DETAILS | 📊 powerbi | 4 |
| ORDER_HISTORY | ❄️ snowflake | 4 |
| Customer Analytics Measures | 📊 powerbi | 4 |
| Essential KPI Measures | 📊 powerbi | 4 |
| Geographic Measures | 📊 powerbi | 4 |
| _…12 more_ | | |

</details>

### Who needs to know

- **David Kim** · `david.kim@example.com` — owns ORDER_DETAILS (snowflake), Order Mode (tableau), Orders By Day (tableau) +4 more
- **Ian Chen** · `ian.chen@example.com` — owns Order Details (looker), order_details (dbt), order_details (looker) +1 more
- **Data Platform Team** (team) · `data-platform@example.com` — owns Order Details (looker), order_details (dbt), order_details (looker) +1 more
- **Karen Okonkwo** · `karen.okonkwo@example.com` — owns ORDER_DETAILS (powerbi), order_details (dbt)
- **Julia Novak** · `julia.novak@example.com` — owns ORDER_DETAILS (snowflake), order_details (dbt)
- **Fiona Green** · `fiona.green@example.com` — owns order_details (dbt), order_details (looker)

### Why this severity

- 3 charts render it directly
- 2 pipeline jobs move it (export_table_orders_to_s3, import_table_orders_to_snowflake)
- impact crosses 7 platforms: dbt, looker, powerbi, s3, snowflake, spark, tableau
- 24 downstream tables/views derive from it

---
<sub>Analysed by [Blast Radius](https://github.com/ritesh59697/datahub-blast-radius) using [DataHub](http://localhost:9002) column-level lineage. Column-precise within the warehouse; entity-level for BI and ML assets. Verdict written back to the DataHub graph.</sub>
