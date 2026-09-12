# Databricks — querying good events

**The decision this doc helps you make:** how to reach into a self-describing event or entity column
correctly on Databricks, so an analysis query returns the real values instead of a silent NULL from a
cast that only errors in certain workspace configurations.

## Column layout

- `contexts_<vendor>_<name>_<major>` — an entity, e.g. `contexts_com_acme_product_1` — is an **ARRAY
  of STRUCT**. Expand it with `LATERAL VIEW EXPLODE`, then read fields with dot access; alternatively, use `inline()` when you want all struct fields as columns in one step.
- `unstruct_event_<vendor>_<name>_<major>` — the self-describing event — is a single STRUCT, read
  directly with dot access, no explode needed.
- Tables are addressed with **Unity Catalog three-part naming**: `catalog.schema.events`.
- A field whose schema crossed a major version lives in several `_<major>` columns — COALESCE across
  them per `schema-versions.md`.

**ANSI-mode cast strictness:** whether a bad `CAST` errors or silently returns NULL depends on the
workspace's SQL mode. Under ANSI mode a cast that can't succeed **errors**; outside ANSI mode it
**returns NULL** instead — so a query that runs cleanly is not by itself proof the casts held. Know
which mode the workspace runs (`spark.sql.ansi.enabled`) before trusting an unchecked cast.

## Unnest and join

```sql
SELECT e.event_id, p.product_id
FROM catalog.schema.events e
LATERAL VIEW EXPLODE(e.contexts_com_acme_product_1) t AS p
WHERE e.derived_tstamp >= current_date() - INTERVAL 7 DAYS;
```

## Loader/physical quirks

Lake Loader's Delta output lands in tables that query like native Delta — the column layout and
unnest pattern above apply the same whether the table came from Lake Loader or any other Delta write
path. Catalog specifics — Unity Catalog vs. Hive metastore vs. Glue — vary by deployment and are a
runtime docs lookup rather than something to assume from this sheet.

**Fan-out warning:** same as every other warehouse — an event carrying N array elements for that
entity becomes N output rows, with the same `event_id` repeated. Aggregate or dedup on `event_id`
before joining this result onward.

## Beyond this sheet

Anything catalog- or loader-version-specific is a runtime docs lookup — use `fetch-snowplow-docs`
rather than relying on this sheet.
