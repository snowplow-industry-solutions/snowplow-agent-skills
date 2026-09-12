# Snowflake — querying good events

**The decision this doc helps you make:** how to reach into a self-describing event or entity column
correctly on Snowflake, so an analysis query returns the real values instead of NULLs or a fan-out you
didn't expect.

## Column layout

- `contexts_<vendor>_<name>_<major>` — an entity (context), e.g. `contexts_com_acme_product_1` — is a
  semi-structured **ARRAY of OBJECT** (VARIANT). One row can carry several instances of the same
  entity, one array element each.
- `unstruct_event_<vendor>_<name>_<major>` — the self-describing event itself — is a **single OBJECT**,
  not an array. Don't index it with `[0]`; read its fields directly.
- Native (non-Iceberg) tables are schemaless VARIANT throughout: navigate with `:` (e.g.
  `f.value:product_id`) and cast with `::TYPE` (e.g. `::VARCHAR`).
- A field whose schema crossed a major version lives in several `_<major>` columns — COALESCE across
  them per `schema-versions.md`.

## Unnest and join

Expand an entity array with `LATERAL FLATTEN` and read fields off `f.value` with `:` navigation and
`::TYPE` casts:

```sql
SELECT e.event_id, f.value:product_id::VARCHAR AS product_id
FROM atomic.events e,
LATERAL FLATTEN(input => e.contexts_com_acme_product_1) f
WHERE e.derived_tstamp >= DATEADD(day, -7, CURRENT_DATE)    -- analysis filter
  AND e.collector_tstamp >= DATEADD(day, -8, CURRENT_DATE);  -- physical-pruning bound (slightly wider to avoid clock-skew events at edge)
```

**Fan-out warning:** an event carrying N array elements for that entity becomes N output rows — the
same `event_id` repeats once per element. Aggregate or dedup on `event_id` before joining this result
onward, or a downstream join will multiply rows further.

## Loader/physical quirks

**Iceberg gotcha:** Lake Loader writes to Iceberg external tables, where custom event and entity
columns are exposed as **strongly typed structs** — every sub-column has a concrete type (`INTEGER`,
`STRING`, …), so you access them with plain dot notation and no cast is needed. That is a different
access pattern from native Snowflake tables, which are schemaless VARIANT and need `:` paths plus
`::TYPE` casts. Same warehouse, two shapes depending on which table you're on — check which you have
before writing any entity access, rather than assuming the VARIANT pattern above applies everywhere.

## Beyond this sheet

Anything catalog- or loader-version-specific (e.g. exact Iceberg column typing for a given Lake Loader
release) is a runtime docs lookup — use `fetch-snowplow-docs` rather than relying on this sheet.
