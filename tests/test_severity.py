from blast_radius.datahub_client import ColumnBlastRadius, LineageHit
from blast_radius.severity import Severity, assess, classify_hit


def hit(entity_type: str, name: str = "thing", platform: str = "dbt", degree: int = 1) -> LineageHit:
    return LineageHit(
        urn=f"urn:li:{entity_type.lower()}:{name}",
        entity_type=entity_type,
        name=name,
        platform=platform,
        degree=degree,
    )


def radius(*hits: LineageHit) -> ColumnBlastRadius:
    return ColumnBlastRadius(
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:postgres,db.orders,PROD)",
        dataset_name="orders",
        column="order_date",
        hits=list(hits),
    )


def test_no_downstream_is_low():
    verdict = assess(radius())
    assert verdict.severity is Severity.LOW
    assert "Safe to merge" in verdict.headline
    assert not verdict.blocking


def test_dashboard_is_critical():
    verdict = assess(radius(hit("DASHBOARD", "Order Entry Dashboard", "looker")))
    assert verdict.severity is Severity.CRITICAL
    assert verdict.blocking


def test_ml_model_is_critical():
    assert assess(radius(hit("MLMODEL", "churn", "sagemaker"))).severity is Severity.CRITICAL


def test_chart_is_high():
    assert assess(radius(hit("CHART", "Orders by Day", "looker"))).severity is Severity.HIGH


def test_only_tables_is_medium():
    verdict = assess(radius(hit("DATASET", "orders_staging"), hit("DATASET", "orders_mart")))
    assert verdict.severity is Severity.MEDIUM
    assert not verdict.blocking


def test_replication_jobs_alone_do_not_escalate_to_high():
    """Table-level copy jobs pass a renamed column through without breaking.

    Rating them HIGH made every column in the warehouse HIGH.
    """
    verdict = assess(radius(
        hit("DATA_JOB", "export_table_orders_to_s3", "spark"),
        hit("DATA_JOB", "import_table_orders_to_snowflake", "spark"),
        hit("DATASET", "orders", "s3"),
    ))
    assert verdict.severity is Severity.MEDIUM


def test_many_platforms_alone_do_not_escalate():
    """Breadth is not severity: a wide fan-out of plain tables stays MEDIUM."""
    verdict = assess(radius(
        hit("DATASET", "a", "dbt"),
        hit("DATASET", "b", "snowflake"),
        hit("DATASET", "c", "s3"),
        hit("DATASET", "d", "powerbi"),
        hit("DATASET", "e", "tableau"),
        hit("DATASET", "f", "looker"),
    ))
    assert verdict.severity is Severity.MEDIUM


def test_dashboard_outranks_many_tables():
    """One dashboard beats twenty tables — severity is about what, not how many."""
    tables = [hit("DATASET", f"t{i}") for i in range(20)]
    only_tables = assess(radius(*tables))
    with_dashboard = assess(radius(*tables, hit("DASHBOARD", "Exec KPIs", "looker")))
    assert only_tables.severity is Severity.MEDIUM
    assert with_dashboard.severity is Severity.CRITICAL


def test_medium_headline_states_the_absence_of_bi_impact():
    verdict = assess(radius(hit("DATASET", "orders_staging")))
    assert "no dashboards, charts, or ML models" in verdict.headline


def test_reasons_explain_why_it_is_not_worse():
    verdict = assess(radius(hit("DATASET", "orders_staging")))
    assert any("no dashboards, charts, or ML models consume it" in r for r in verdict.reasons)


def test_per_hit_labels_never_exceed_the_overall_verdict():
    """A hit shown as HIGH inside a MEDIUM verdict reads as self-contradiction.

    This regressed once: pipeline jobs were labelled HIGH while the verdict
    they appeared under said MEDIUM.
    """
    cases = [
        radius(hit("DATA_JOB", "export_table_x_to_s3", "spark"), hit("DATASET", "x", "s3")),
        radius(hit("DATASET", "staging")),
        radius(hit("CHART", "Orders by Day", "looker")),
        radius(hit("DASHBOARD", "Exec KPIs", "looker")),
    ]
    for case in cases:
        overall = assess(case).severity
        for h in case.hits:
            assert classify_hit(h).rank <= overall.rank, (
                f"{h.entity_type} labelled {classify_hit(h).value} "
                f"inside a {overall.value} verdict"
            )


def test_pipeline_job_hit_is_medium():
    assert classify_hit(hit("DATA_JOB", "export", "spark")) is Severity.MEDIUM


def test_singular_plural_agreement():
    one = assess(radius(hit("DASHBOARD", "D1", "looker")))
    assert "1 dashboard consumes this column" in " ".join(one.reasons)
    two = assess(radius(hit("DASHBOARD", "D1", "looker"), hit("DASHBOARD", "D2", "looker")))
    assert "2 dashboards consume this column" in " ".join(two.reasons)
