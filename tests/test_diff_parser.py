from blast_radius.diff_parser import ChangeKind, parse_diff


def test_detects_rename_in_sql_model():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -3,7 +3,7 @@ select
     order_id,
-    order_date,
+    order_dt,
     customer_id
"""
    changes = parse_diff(diff)
    assert len(changes) == 1
    change = changes[0]
    assert change.kind is ChangeKind.RENAMED
    assert change.table == "orders"
    assert change.column == "order_date"
    assert change.new_column == "order_dt"
    assert change.breaking


def test_detects_rename_with_alias():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -1,4 +1,4 @@ select
-    o.created_at as order_date,
+    o.created_at as order_dt,
"""
    changes = parse_diff(diff)
    assert len(changes) == 1
    assert changes[0].column == "order_date"
    assert changes[0].new_column == "order_dt"


def test_detects_drop():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -3,6 +3,5 @@ select
     order_id,
-    order_date,
     customer_id
"""
    changes = parse_diff(diff)
    assert [c.kind for c in changes] == [ChangeKind.DROPPED]
    assert changes[0].column == "order_date"


def test_added_column_is_not_breaking():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -3,5 +3,6 @@ select
     order_id,
+    order_channel,
     customer_id
"""
    changes = parse_diff(diff)
    assert [c.kind for c in changes] == [ChangeKind.ADDED]
    assert not changes[0].breaking


def test_parses_dbt_yaml_schema():
    diff = """\
--- a/models/marts/schema.yml
+++ b/models/marts/schema.yml
@@ -5,7 +5,7 @@ models:
       columns:
-      - name: order_date
+      - name: order_dt
"""
    changes = parse_diff(diff)
    assert len(changes) == 1
    assert changes[0].column == "order_date"
    assert changes[0].new_column == "order_dt"


def test_separate_hunks_do_not_pair_into_a_rename():
    """Two unrelated hunks are a drop and an add, not one rename."""
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -3,4 +3,3 @@ select
-    order_date,
@@ -20,3 +19,4 @@ select
+    shipping_zone,
"""
    changes = parse_diff(diff)
    kinds = {c.kind for c in changes}
    assert kinds == {ChangeKind.DROPPED, ChangeKind.ADDED}


def test_ignores_sql_keywords():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -1,5 +1,5 @@
-select
-from
+select
+from
"""
    assert parse_diff(diff) == []


def test_reordering_columns_is_not_a_change():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -1,4 +1,4 @@ select
-    order_id,
-    order_date,
+    order_date,
+    order_id,
"""
    assert parse_diff(diff) == []


def test_multiple_files_are_scoped_to_their_own_tables():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -1,3 +1,3 @@ select
-    order_date,
+    order_dt,
--- a/models/marts/customers.sql
+++ b/models/marts/customers.sql
@@ -1,3 +1,3 @@ select
-    cust_email,
+    email_address,
"""
    changes = parse_diff(diff)
    tables = {c.table: c for c in changes}
    assert set(tables) == {"orders", "customers"}
    assert tables["orders"].new_column == "order_dt"
    assert tables["customers"].new_column == "email_address"


def test_describe_is_human_readable():
    diff = """\
--- a/models/marts/orders.sql
+++ b/models/marts/orders.sql
@@ -1,3 +1,3 @@ select
-    order_date,
+    order_dt,
"""
    assert parse_diff(diff)[0].describe() == "Rename orders.order_date to order_dt"
