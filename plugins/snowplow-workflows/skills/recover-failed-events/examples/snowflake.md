# Worked example — recovering a string-typed field back to INTEGER

A complete, realistic run of the flow end to end, so you can see how the phases connect and what the
intermediate outputs look like. **This is an illustration, not a template to copy** — the table
names, schema, and field types are specific to this case. For the reusable statements with
placeholders, use `templates/snowflake.md`; for the reasoning, `reference/`.

## The scenario

- **Failed table:** `ACME_PROD.ATOMIC_FAILED.EVENTS`
- **Good table:** `ACME_PROD.ATOMIC.EVENTS`
- **Failing schema:** `iglu:com.acme/user_entity/jsonschema/1-0-0`
- **app_id:** `web`
- **When:** failures started ~2026-03-02, so we bound to `2026-03-01`–`2026-03-10`.
- **The bug:** the tracker sent `user_id` as a **string** (`"1042"`) and `account_age_days` as a
  string (`"365"`), but the schema types them as integers. `user_name` was always a valid string. So
  two of three fields need a string→INTEGER coercion.

The good-table entity column found in Phase 4 turns out to be `contexts_com_acme_user_entity_1` (a
semi-structured `ARRAY` column — Snowflake has no strict struct type to match, so the target types
come from a validated good row, not the column's `data_type`).

## Phase 2 — identify

Summary query returns (abridged):

| failing_schema | app_id | failure_type | source | failed_events | first_seen | last_seen |
|---|---|---|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | web | SchemaViolation | contexts | 3,418 | 2026-03-02 08:14 | 2026-03-09 23:51 |

We pick that schema. The row-level drill-in shows `errors` complaining that `user_id` is a string
where integer is expected — our hypothesis. Duplicate pre-check returns **0** (never recovered). It's
a custom schema, so we ask the user for the Iglu JSON as a cross-check on field names/types.

## Phase 3 — inspect the payload

Payload-inspection query (`LATERAL FLATTEN` + `f.value:data:<field>`) returns real values:

| failing_schema | user_id | user_name | account_age_days |
|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | "1042" | "ada.lovelace" | "365" |
| iglu:com.acme/user_entity/jsonschema/1-0-0 | "1043" | "alan.turing" | "410" |

The `LIMIT 10` sample suggests `user_id`/`account_age_days` are quoted integers and `user_name` a
plain string — but that's a sample, so we profile before choosing casts.

## Phase 3.5 — profile & confirm coercibility

The field profiling query (one block per field, target types from a validated good row) returns
across all 3,418 rows:

| field | variant_types | absent | uncoercible (→ target) |
|---|---|---|---|
| user_id | `VARCHAR` | 0 | 0 → INTEGER |
| account_age_days | `INTEGER,VARCHAR` | 0 | 0 → INTEGER |
| user_name | `VARCHAR` | 0 | 0 → STRING |

Every field is present in every row and 0 uncoercible → the whole population shares one recovery.
Because Snowflake's `::TYPE` cast coerces both native and string-encoded values, a single
`::INTEGER` handles the mixed `account_age_days` (`INTEGER,VARCHAR`) column too.

## Phase 4 — recovery expression + test SELECT

Built as a VARIANT array of one object, `_schema_version` first, each field cast with `::TYPE`:

```sql
ARRAY_CONSTRUCT(
    OBJECT_CONSTRUCT(
        '_schema_version', '1-0-0',
        'user_id', failure_entry:data:user_id::INTEGER,
        'user_name', failure_entry:data:user_name::STRING,
        'account_age_days', failure_entry:data:account_age_days::INTEGER
    )
)
```

The test SELECT's `prep` CTE `LATERAL FLATTEN`s the failure array and keeps the element matching the
schema, as `failure_entry`, so an event whose target failure isn't first is still recovered. It builds
`recovered` in a CTE, then reads its fields back with
`TYPEOF(recovered[0]:<field>)` in the outer query — `TYPEOF()` needs a VARIANT, so it can't wrap the
`::TYPE` casts directly. Because profiling already proved every value coerces, and Snowflake errors on
a bad `::TYPE` cast, a clean run *is* proof here. Output spot-check:

| event_id | recovered | user_id_type | account_age_days_type |
|---|---|---|---|
| 5f3c…a1 | [{_schema_version:"1-0-0", user_id:1042, user_name:"ada.lovelace", account_age_days:365}] | INTEGER | INTEGER |
| 7b90…c4 | [{_schema_version:"1-0-0", user_id:1043, user_name:"alan.turing", account_age_days:410}] | INTEGER | INTEGER |

## Phase 5 — validate (gate)

- Ran clean ✅ (profiling ruled out un-coercible values; `::TYPE` errors rather than silent-NULL)
- `TYPEOF()` = `INTEGER`, `VARCHAR`, `INTEGER`; `_schema_version` present ✅
- Row count 3,418 = identification count ✅
- `user_id` is now `1042` (integer), not `"1042"` ✅

Gate passes.

## Phase 6 — write path

Chose **staging** (recommended). Created it as an exact mirror:

```sql
CREATE TABLE ACME_PROD.ATOMIC.EVENTS_RECOVERY_STAGING
    LIKE ACME_PROD.ATOMIC.EVENTS;
```

## Phase 7 — generate the INSERT

Ran the INSERT-generator with `<target_*> = ACME_PROD.ATOMIC.EVENTS_RECOVERY_STAGING`,
`<recovery_column> = contexts_com_acme_user_entity_1`, the validated expression (single quotes
doubled `''`), and the same window/app_id/schema. It returned one cell: a positional
`INSERT ... WITH prep AS (...) SELECT ...` where the failure column is `CAST(NULL AS ...)`,
`load_tstamp` is `CURRENT_TIMESTAMP()`, `contexts_com_acme_user_entity_1` carries the
`ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(...))`, atomic columns pass through, and good-only columns are
`CAST(NULL AS ...)`. Reviewed it, column count matched the good table.

## Phase 8 — run, validate, promote

Ran the INSERT into staging → 3,418 rows. Spot-checked `contexts_com_acme_user_entity_1[0]` in
staging: correct. Promoted:

```sql
INSERT INTO ACME_PROD.ATOMIC.EVENTS
SELECT * FROM ACME_PROD.ATOMIC.EVENTS_RECOVERY_STAGING;
```

Re-validated the good table (row count + spot-check), then dropped the staging table.

## What this example demonstrates

- The Iglu schema (via a validated good row) — not the payload — dictates the field types; the
  payload values are exactly what failed validation.
- Profiling first (not the `LIMIT 10` sample) is what let us cast confidently: `::INTEGER` coerces
  both the string-encoded `user_id` and the **mixed** (`INTEGER,VARCHAR`) `account_age_days`. No
  `TRY_CAST` in the recovery expression, no query that could error, no silent NULLs.
- Had profiling shown `uncoercible > 0` on any field, the population would *not* have shared one
  recovery — the flow would stop and partition instead of assuming.
- Fields that were already valid (`user_name`) still get carried through the reconstruction; you
  don't only rebuild the broken ones.
- Snowflake has no strict struct typing, so key order and reserved words are not concerns — the keys
  are plain string literals.
- Staging + duplicate pre-check keep the write safe and idempotent.
