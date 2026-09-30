# Worked example — recovering a string-typed field back to INT64

A complete, realistic run of the flow end to end, so you can see how the phases connect and what the
intermediate outputs look like. **This is an illustration, not a template to copy** — the table
names, schema, and field types are specific to this case. For the reusable statements with
placeholders, use `templates/bigquery.md`; for the reasoning, `reference/`.

## The scenario

- **Failed table:** `acme-prod.atomic_failed.events`
- **Good table:** `acme-prod.atomic.events`
- **Failing schema:** `iglu:com.acme/user_entity/jsonschema/1-0-0`
- **app_id:** `web`
- **When:** failures started ~2026-03-02, so we bound to `2026-03-01`–`2026-03-10`.
- **The bug:** the tracker sent `user_id` as a **string** (`"1042"`) and `account_age_days` as a
  string (`"365"`), but the schema (and the good-table column) type them as `INT64`. `user_name` was
  always a valid string. So two of three fields need a string→INT64 coercion.

The good-table entity column and its type (from the Phase 4 lookup) turn out to be:

```
column_name = contexts_com_acme_user_entity_1
data_type   = ARRAY<STRUCT<_schema_version STRING, user_id INT64, user_name STRING, account_age_days INT64>>
```

That `data_type` is the contract the reconstruction must match field-for-field.

## Phase 2 — identify

Summary query returns (abridged):

| failing_schema | app_id | failure_type | source | failed_events | first_seen | last_seen |
|---|---|---|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | web | SchemaViolation | contexts | 3,418 | 2026-03-02 08:14 | 2026-03-09 23:51 |

We pick that schema. The row-level drill-in shows `errors` complaining that `user_id` is a string
where integer is expected — our hypothesis. Duplicate pre-check returns **0** (never recovered).

## Phase 3 — inspect the payload

Payload-inspection query (`UNNEST` + `JSON_VALUE(f.data.<field>)`) returns real values:

| failing_schema | user_id | user_name | account_age_days |
|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | "1042" | "ada.lovelace" | "365" |
| iglu:com.acme/user_entity/jsonschema/1-0-0 | "1043" | "alan.turing" | "410" |

The `LIMIT 10` sample suggests `user_id`/`account_age_days` are quoted integers and `user_name` a
plain string — but that's a sample, so we profile before choosing extractors.

## Phase 3.5 — profile & confirm coercibility

The field profiling query (one block per field, target types from `data_type`) returns across all
3,418 rows:

| field | json_types | absent | uncoercible (→ target) |
|---|---|---|---|
| user_id | `string` | 0 | 0 → INT64 |
| account_age_days | `number,string` | 0 | 0 → INT64 |
| user_name | `string` | 0 | 0 → STRING |

Every field is present in every row and 0 uncoercible → the whole population shares one recovery.
Per-field extractor choice: `user_name` is uniformly native `string` → **strict `STRING()`**;
`user_id` is string-encoded and `account_age_days` is **mixed** (`number,string`) → **`CAST(JSON_VALUE
… AS INT64)`**. (This is where a single expression handles the mixed string/int column.)

## Phase 4 — recovery expression + test SELECT

Built to match `data_type` exactly (order: `_schema_version`, `user_id`, `user_name`,
`account_age_days`), using the extractor profiling selected for each field:

```sql
[STRUCT(
    '1-0-0'                                                         AS _schema_version,
    CAST(JSON_VALUE(failure_entry.data.user_id) AS INT64)          AS user_id,          -- string-encoded → coerce
    STRING(failure_entry.data.user_name)                           AS user_name,        -- native string → strict
    CAST(JSON_VALUE(failure_entry.data.account_age_days) AS INT64) AS account_age_days  -- mixed number,string → coerce
)]
```

The test SELECT wraps this over the failed rows (its `prep` CTE `UNNEST`s the failure array and keeps
the element matching the schema, as `failure_entry`, so an event whose target failure isn't first is
still recovered). Because profiling already proved every value coerces,
and both `STRING()` and `CAST(JSON_VALUE …)` error on a bad value, a clean run *is* proof here. Output
spot-check:

| event_id | recovered |
|---|---|
| 5f3c…a1 | [{_schema_version:"1-0-0", user_id:1042, user_name:"ada.lovelace", account_age_days:365}] |
| 7b90…c4 | [{_schema_version:"1-0-0", user_id:1043, user_name:"alan.turing", account_age_days:410}] |

## Phase 5 — validate (gate)

- Ran clean ✅ (profiling ruled out un-coercible values; strict/`CAST` error rather than silent-NULL)
- Struct shape = `_schema_version, user_id INT64, user_name STRING, account_age_days INT64`, matches
  `data_type`, `_schema_version` first ✅
- Row count 3,418 = identification count ✅
- `user_id` is now `1042` (integer), not `"1042"` ✅

Gate passes.

## Phase 6 — write path

Chose **staging** (recommended). Created it as an exact mirror:

```sql
CREATE TABLE `acme-prod.atomic.events_recovery_staging`
LIKE `acme-prod.atomic.events`;
```

## Phase 7 — generate the INSERT

Ran the INSERT-generator with `<target_*> = acme-prod.atomic.events_recovery_staging`,
`<recovery_column> = contexts_com_acme_user_entity_1`, the validated expression (triple-quoted), and
the same window/app_id/schema. It returned one cell: a positional `INSERT ... WITH prep AS (...)
SELECT ...` where the failure column is `CAST(NULL AS ...)`, `load_tstamp` is `CURRENT_TIMESTAMP()`,
`contexts_com_acme_user_entity_1` carries the `[STRUCT(...)]`, atomic columns pass through, and
good-only columns are `CAST(NULL AS ...)`. Reviewed it, column count matched the good table.

## Phase 8 — run, validate, promote

Ran the INSERT into staging → 3,418 rows. Spot-checked `contexts_com_acme_user_entity_1[SAFE_OFFSET(0)]` in
staging: correct. Promoted:

```sql
INSERT INTO `acme-prod.atomic.events`
SELECT * FROM `acme-prod.atomic.events_recovery_staging`;
```

Re-validated the good table (row count + spot-check), then dropped the staging table.

## What this example demonstrates

- The `data_type` — not the payload — dictates field names, types, and order.
- Profiling first (not the `LIMIT 10` sample) is what let us pick extractors confidently: strict
  `STRING()` where the value was native, `CAST(JSON_VALUE … AS INT64)` where it was string-encoded or
  **mixed** (`account_age_days`). No `LAX_`, no query that could error, no silent NULLs.
- Had profiling shown `uncoercible > 0` on any field, the population would *not* have shared one
  recovery — the flow would stop and partition instead of assuming.
- Fields that were already valid (`user_name`) still get carried through the reconstruction; you
  don't only rebuild the broken ones.
- Staging + duplicate pre-check keep the write safe and idempotent.
