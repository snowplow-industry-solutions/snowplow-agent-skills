# Querying across schema major versions

**The decision this doc helps you make:** how to query the full history of a field whose schema has
crossed a major version boundary — e.g. `product_id` surviving versions 1-0-0 → 1-0-1 → 2-0-0 —
without silently dropping every event written under the other major version.

## One field, several columns

Minor and patch schema bumps mutate the **same** warehouse column; only a **major** bump creates a
new one (exception: BigQuery Loader v1 / compatibility mode, below). So after a major bump,
`contexts_com_acme_product_1` and `contexts_com_acme_product_2` are both live history for the same
entity, and a query that reads only one of them silently misses every event validated against the
other.

## Why COALESCE works

Any single event validates against exactly one schema version, so on any given row at most one
major-version column is populated. COALESCE across the versions never has two non-NULL candidates
to choose between — it simply picks whichever column this row's schema version landed in:

```sql
SELECT COALESCE(
  contexts_com_acme_product_1[0].product_id,
  contexts_com_acme_product_2[0].product_id
) AS product_id
FROM atomic.events;
```

## Per-dialect mechanics

- **Snowflake:** VARIANT paths and casts on each leaf —
  `COALESCE(contexts_com_acme_product_1[0]:product_id::VARCHAR, contexts_com_acme_product_2[0]:product_id::VARCHAR)`.
  For unnesting, coalescing the whole columns works because VARIANT is untyped:
  `LATERAL FLATTEN(input => COALESCE(contexts_com_acme_product_1, contexts_com_acme_product_2))`.
- **Databricks and BigQuery:** coalesce the extracted **leaf fields**, never the whole arrays — the
  array-of-struct types differ between major versions (different field sets), so a whole-array
  COALESCE can fail strict typing.
- **BigQuery:** under Loader v1 or compatibility mode the coalesce list may need per-**minor**
  columns too (`_1_0_0`, `_1_0_1`, `_2_0_0`). Inspect `INFORMATION_SCHEMA.COLUMNS` first — already
  the standing rule in `dialect-bigquery.md`.
- **Redshift:** no in-row columns — each major version is its own shredded table
  (`atomic.com_acme_product_1`, `atomic.com_acme_product_2`). UNION ALL the tables with aligned
  select lists (their column sets differ across majors), or LEFT JOIN each to `atomic.events` and
  COALESCE — either way keeping the both-keys join rule from `dialect-redshift.md`
  (`root_id = event_id AND root_tstamp = collector_tstamp`) on every table.
