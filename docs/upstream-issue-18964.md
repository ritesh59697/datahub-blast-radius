## Describe the bug

`LineageClient.get_lineage()` raises `InvalidUrnError` whenever column-level lineage
traverses a schema field whose parent is not a Dataset — for example a Tableau chart
field.

`_create_lineage_result` calls `DatasetUrn.from_string()` on the parent of every
`SCHEMA_FIELD` in the returned paths:

https://github.com/datahub-project/datahub/blob/master/metadata-ingestion/src/datahub/sdk/lineage_client.py#L936

```python
if path_entry["type"] == "SCHEMA_FIELD":
    schema_field_urn = SchemaFieldUrn.from_string(path_entry["urn"])
    result.paths.append(
        LineagePath(
            urn=path_entry["urn"],
            entity_name=DatasetUrn.from_string(schema_field_urn.parent).name,  # <-- here
            column_name=schema_field_urn.field_path,
        )
    )
```

A `schemaField` URN can be parented by a chart, not only a dataset. The Tableau connector
emits exactly these, and they appear in `searchAcrossLineage` paths:

```
urn:li:schemaField:(urn:li:chart:(tableau,<id>),ORDERS_COUNT)
```

`DatasetUrn.from_string()` rejects that parent and the whole call fails, so no results are
returned at all — including the dataset-parented ones that parsed fine.

The practical effect is that the columns most worth analysing (the ones that actually
reach a BI asset) are the ones that cannot be queried through the SDK.

## To Reproduce

Against a quickstart instance with the `showcase-ecommerce` datapack loaded:

```bash
datahub docker quickstart
datahub datapack load showcase-ecommerce
```

```python
from datahub.sdk import DataHubClient

client = DataHubClient(server="http://localhost:8080")

client.lineage.get_lineage(
    source_urn="urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
    source_column="order_id",
    direction="downstream",
    max_hops=3,
)
```

```
datahub.utilities.urns.error.InvalidUrnError: Passed an urn of type chart to the
from_string method of DatasetUrn. Use Urn.from_string() or ChartUrn.from_string() instead.
```

```
File ".../datahub/sdk/lineage_client.py", line 739, in get_lineage
    return self._execute_lineage_query(variables, direction)
File ".../datahub/sdk/lineage_client.py", line 896, in _execute_lineage_query
    result = self._create_lineage_result(entity, entry, direction)
File ".../datahub/sdk/lineage_client.py", line 936, in _create_lineage_result
File ".../datahub/utilities/urns/_urn_base.py", line 153, in from_string
    raise InvalidUrnError(...)
```

The same query over raw GraphQL returns all 29 downstream entities, including the 3 charts,
so the data is fine — this is purely SDK-side deserialisation.

`orders.order_id`, `order_items.unit_price` and `order_items.quantity` all reproduce it.
`orders.order_total` does not, because its lineage happens not to reach a chart.

## Expected behavior

`get_lineage()` should return results for column-level lineage that reaches non-dataset
entities.

Note that `DatasetUrn.name` has no direct equivalent on other URN types — `ChartUrn`
exposes `chart_id`, not `name` — so `getattr(parent, "name", ...)` would silently degrade
to the raw URN string. `get_entity_id_as_string()` is defined on the base `Urn` and gives
a usable identifier for all of them:

```python
parent_urn = Urn.from_string(schema_field_urn.parent)
entity_name = (
    parent_urn.name
    if isinstance(parent_urn, DatasetUrn)
    else parent_urn.get_entity_id_as_string()
)
```

At minimum, one unparseable path entry should not discard the entire result set.

## Version

| | |
|---|---|
| `acryl-datahub` | 1.7.0 |
| DataHub GMS | v1.7.0 (quickstart) |
| Python | 3.11.15 |
| OS | macOS 15 (arm64) |

## Additional context

Found while building [Blast Radius](https://github.com/ritesh59697/datahub-blast-radius),
a PR bot that reports the downstream impact of dbt schema changes, for the DataHub Agent
Hackathon. Worked around it by querying `searchAcrossLineage` directly against
`schemaField` URNs.

Happy to open a PR with the fix and a regression test if the suggested approach looks
right.
