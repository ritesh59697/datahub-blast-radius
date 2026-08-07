## 🔴 Blast Radius: `Change orders.order_date`

**This change breaks 1 dashboard, 2 charts, and 16 tables.**

Traced `orders.order_date` through DataHub lineage: **21 downstream entities** across **7 platforms**, up to **6 hops** deep.

### What breaks

| | Asset | Type | Platform | Hops |
|---|---|---|---|---|
| 🔴 | **Order Entry Dashboard** | Dashboard | 👁️ looker | 6 |
| 🟠 | **export_table_orders_to_s3** | Pipeline job | ⚡ spark | 1 |
| 🟠 | **import_table_orders_to_snowflake** | Pipeline job | ⚡ spark | 2 |
| 🟠 | **Orders By Month** | Chart | 📈 tableau | 6 |
| 🟠 | **Orders by Day** | Chart | 👁️ looker | 6 |

<details><summary>Plus 16 downstream tables and views (showing 12)</summary>

| Table | Platform | Hops |
|---|---|---|
| orders | 🪣 s3 | 1 |
| ORDERS | ❄️ snowflake | 2 |
| orders | 🔧 dbt | 3 |
| ORDER_DETAILS | ❄️ snowflake | 3 |
| order_details | 🔧 dbt | 4 |
| order_details | 👁️ looker | 4 |
| ORDER_DETAILS | 📊 powerbi | 4 |
| Customer Analytics Measures | 📊 powerbi | 4 |
| Essential KPI Measures | 📊 powerbi | 4 |
| Geographic Measures | 📊 powerbi | 4 |
| Product Perfromance Measures | 📊 powerbi | 4 |
| Time Inteligence Measures | 📊 powerbi | 4 |
| _…4 more_ | | |

</details>

### Who needs to know

- **Ian Chen** · `ian.chen@example.com` — owns Order Details (looker), order_details (dbt), order_details (looker) +1 more
- **David Kim** · `david.kim@example.com` — owns ORDER_DETAILS (snowflake), Orders By Day (tableau), Orders By Month (tableau) +1 more
- **Data Platform Team** (team) · `data-platform@example.com` — owns Order Details (looker), order_details (dbt), order_details (looker) +1 more
- **Karen Okonkwo** · `karen.okonkwo@example.com` — owns ORDER_DETAILS (powerbi), order_details (dbt)
- **Julia Novak** · `julia.novak@example.com` — owns ORDER_DETAILS (snowflake), order_details (dbt)
- **Fiona Green** · `fiona.green@example.com` — owns order_details (dbt), order_details (looker)

### Why this severity

- 1 dashboard consumes this column (Order Entry Dashboard)
- 2 charts render it directly
- 2 pipeline jobs move it (export_table_orders_to_s3, import_table_orders_to_snowflake)
- impact crosses 7 platforms: dbt, looker, powerbi, s3, snowflake, spark, tableau
- 16 downstream tables/views derive from it

---
<sub>Analysed by [Blast Radius](https://github.com/ritesh59697/datahub-blast-radius) using [DataHub](http://localhost:9002) column-level lineage. Column-precise within the warehouse; entity-level for BI and ML assets. Verdict written back to the DataHub graph.</sub>
