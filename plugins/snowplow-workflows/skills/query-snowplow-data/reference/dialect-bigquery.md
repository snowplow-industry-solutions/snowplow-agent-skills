# BigQuery — querying good events

**The decision this doc helps you make:** how to reach into a self-describing event or entity column
correctly on BigQuery — including which struct-naming convention the table actually uses — so an
analysis query returns the real values instead of erroring on a missing partition filter or a wrong
column name.

## Column layout

- `contexts_<vendor>_<name>_<major>` — an entity, e.g. `contexts_com_acme_product_1` — is a
  **REPEATED STRUCT** column. Expand it with `UNNEST`, and index a single element with
  `[SAFE_OFFSET(n)]`; read fields with dot access (`p.product_id`).
- `unstruct_event_<vendor>_<name>_<major>` — the self-describing event — is a **single STRUCT**, not
  repeated. Read its fields directly with dot access; no `UNNEST`, no offset.
- A field whose schema crossed a major version lives in several version-suffixed columns — COALESCE
  across them per `schema-versions.md`.

## Loader v1 vs v2 gotcha

The BigQuery Loader has two versions with **different column-naming conventions** for the same entity:

- **v1** creates a new struct column per **minor** schema version: `contexts_com_acme_product_1_0_0`,
  `contexts_com_acme_product_1_0_1`, and so on.
- **v2** creates one struct column per **major** version — `contexts_com_acme_product_1` — the same
  convention as Snowflake and Databricks.

**Compatibility mode**, from the v1→v2 migration: a schema that was already populated at migration time
keeps its v1 (per-minor-version) columns going forward, while a schema seen for the first time after
migration gets the v2 (per-major-version) column. **One table can mix both conventions** across
different schemas. Always run `SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS` (or otherwise
inspect the table) before writing any entity reference — never assume which convention a given schema's
columns follow.

## Mandatory partition filter gotcha

If the table has `require_partition_filter` set, an unfiltered query is a **hard error**
("`Cannot query over table ... without a filter over ...`"), not just a slow scan. The partition
column is typically `load_tstamp`, while analysis usually wants to filter on `derived_tstamp` — carry
**both** predicates, not just one:

```sql
SELECT e.event_id, p.product_id
FROM `project.dataset.events` e, UNNEST(e.contexts_com_acme_product_1) AS p
WHERE DATE(e.load_tstamp) BETWEEN '2026-08-01' AND '2026-09-01'  -- partition filter (required)
  AND e.derived_tstamp >= TIMESTAMP('2026-08-01');               -- analysis filter
```

## Fan-out warning

Same as every other warehouse: an event carrying N array elements for that entity becomes N output
rows, with the same `event_id` repeated. Aggregate or dedup on `event_id` before joining this result
onward.

## Beyond this sheet

Anything catalog- or loader-version-specific beyond the v1/v2 naming split above (e.g. exact BigQuery
Loader release behaviour) is a runtime docs lookup — use `fetch-snowplow-docs` rather than relying on
this sheet.
