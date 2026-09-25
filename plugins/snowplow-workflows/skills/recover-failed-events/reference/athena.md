# Dialect pack — Athena / Iceberg

Load this in Phase 1 once the warehouse is Athena. Shared concepts (failure model, navigation,
classification, the gates) are in `reference/failure-context.md`; the runnable SQL is in
`templates/athena.md`.

## Dialect at a glance

| Concept | Athena / Iceberg (Trino) |
|---|---|
| Table qualifier | `database.table` |
| Grounding source (recovery-column type) | good-table `DESCRIBE` |
| Failure-array expand | `CROSS JOIN UNNEST(...) AS t(failure_ctx)` |
| Read a `data` scalar | `json_extract_scalar(failure_ctx.data, '$.f')` |
| Cast | `CAST(... AS <type>)`; `TRY_CAST` in profiling |
| contexts reconstruction | `CAST(ARRAY[ROW(...)] AS ARRAY(ROW(...)))`, `_schema_version` first |
| unstruct reconstruction | `CAST(ROW(...) AS ROW(...))`, no array, no `_schema_version` |
| Profiling probe (non-erroring) | `json_extract_scalar` + `TRY_CAST` + `count_if` |
| Validation signal | `typeof()` matches the target type field-for-field |
| Staging create | CTAS `WITH(table_type='ICEBERG', location=…)` + `WHERE 1=0` (needs an S3 path) |
| Time travel | `FOR TIMESTAMP AS OF` (engine v3) |
| Lookback date-math | `load_tstamp > current_timestamp - interval '<days>' day` |
| INSERT-build mechanism | local `scripts/generate_insert_athena.py` |
| Recovery-expr embedding | inline in the INSERT, verbatim — no escaping; only `app_id` and the schema URI are `''`-escaped |
| Good-entity array index | `[1]` (1-based) |
| Good-entity array size | `cardinality(<recovery_column>)` |
| Recorded schema URI | `failure_ctx.schema` (the URI **as recorded** — the ResolutionError filter) |

Athena is the strictest on typing: native `ARRAY(ROW(...))` entity columns, positional struct inserts,
**and** it needs Hive→Trino type conversion plus reserved-word quoting (below) that the other
warehouses don't. The failure `data` is a JSON string read with `json_extract_scalar`.

## Column classification, type conversion & the validation gate

**The decision this doc helps you make:** whether the reconstructed entity is shaped correctly enough
that the wide `INSERT ... SELECT` will type-check and land clean data — and what the generator does
with every other column. This is the judgment layer behind `scripts/generate_insert_athena.py` and the INSERT
template in `templates/athena.md`.

## Strict struct typing (the key Athena constraint)

Entity columns are native `ARRAY(ROW(...))`. Athena inserts **positionally** into a struct, so the
reconstructed entity's `ROW(...)` must have the **same field names, the same field types, and the same
field order** as the good-table column's type. Get that contract from the good-table `DESCRIBE` (see
`reference/failure-context.md`), and build the recovery expression as `CAST(ARRAY[ROW(...)] AS
ARRAY(ROW(...)))` to match it field-for-field, `_schema_version` first. The `ARRAY<STRUCT<...>>` form
that DESCRIBE prints is DDL-only and invalid in a query.

**Why order matters:** the generated INSERT lists columns explicitly but the *struct fields* inside the
recovery column are matched positionally, so a reordered field is a type mismatch even if the names are
right.

## Column classification (what the generator does, per column)

For every column in the **good** events table DESCRIBE, decide its SELECT expression:

1. **The failure column** (`contexts_com_snowplowanalytics_snowplow_failure_1`) → **exclude entirely**
   from both the column list and the SELECT. *Why:* re-carrying the failure context into the good
   table would contaminate it.
2. **`load_tstamp`** → `current_timestamp AS load_tstamp` (fresh timestamp for reprocessed rows).
3. **The recovery column** (the entity being repaired) → the user's confirmed `CAST(ARRAY[ROW(...)] AS
   ARRAY(ROW(...)))` expression, followed by `AS <column_name>`. Strip any trailing `AS <column_name>`
   the user already included before re-adding it.
4. **Any other column present in the failed table DESCRIBE** → pass through by name. This one rule
   covers both the atomic columns (the failed events table carries the full atomic set) and any
   materialised sibling entity (which can hold values for events that failed on a *different* entity).
5. **Column only in the good table** → `CAST(NULL AS <athena_type>) AS <column_name>`.

After classifying, report a sanity summary to the user:
`good columns: N | failed columns: M | pass-through: P | nulled: Q`.
Warn if the recovery column name is not found in the good DESCRIBE.

Because the failed events table already contains every atomic column, the good-vs-failed membership
comparison *is* the atomic-vs-custom classification — no hardcoded atomic-column list is needed. (The
Databricks sibling script classifies the same way.)

## Hive → Athena type conversion

DESCRIBE output uses Hive DDL types. Convert to Athena query-expression types for the
`CAST(NULL AS ...)` cases:

| Hive (DESCRIBE) | Athena (INSERT expression) |
|---|---|
| `string` | `varchar` |
| `int` | `integer` |
| `array<...>` | `array(...)` |
| `struct<...>` | `row(...)` |
| `map<k,v>` | `map(k,v)` |
| `field:type` (colon separator) | `"field" type` (quoted name, space separator) |

Mechanical steps: `array<`→`array(`, `struct<`→`row(`, `map<`→`map(`, every `>`→`)`, quote every struct
field name and drop its colon (`name:`→`"name" `), then `string`→`varchar` and `int`→`integer` on the
*type* tokens only. Quoting every field name unconditionally is always safe in a Trino row type and
protects a field named after a reserved word or a type keyword (`date`, `float`, `int`, `map`, …); the
keyword substitutions skip anything already inside quotes, so a field literally named `int` or `string`
is left intact.

### Reserved words inside ROW(...) definitions

If a struct **field name** equals a reserved word, it must be double-quoted or Athena rejects the
type, e.g. `row("timestamp" varchar, ...)`. Quote a field name when it (case-insensitive) is one of:

```
current_time current_date current_timestamp timestamp date time interval
year month day hour minute second zone value values table column row type
position filter over partition range select from where group order by having
limit union all distinct as in not and or is null true false case when then
else end exists between like natural cross join inner outer left right full on using
```

Confirmed real cases seen in Snowplow tables: `"current_time"` (media_player_2),
`"timestamp"` (spamreport_3, geolocation_context_1), `"all"` (consent_withdrawn_1),
`"type"` (ecommerce_action_1), `"value"` (http_cookie_1, http_header_1),
`"position"` (ecommerce_product_1).

## Parsing DESCRIBE output

- Lines may be **tab-separated** or **space-separated** depending on how the user copied them. For
  space-separated, split only on the *first* run of whitespace (`col_name` then the rest is the type)
  so complex types containing spaces stay intact.
- Skip blank lines and `#` comment lines.
- **Stop parsing** at a line starting with `# Partition spec` or `# Partition information` —
  everything after is the partition spec, not columns.

## Choosing the extractor per field (from profiling — Phase 3.5)

Run the profiling query (`templates/athena.md`) to learn, per field across *all* failed rows,
whether every value casts to the target type and whether the field is always present, then decide in
order:

1. **Any field `_uncoercible > 0`** → the failed rows don't share one recovery; some values can't
   become the target type. **Stop, surface the offending rows, and partition/scope** with the user.
   Don't suggest a recovery expression yet.
2. **Any field `_absent > 0`** → it's missing from some rows: if the schema requires the field,
   partition those rows off; if optional, the extractor returns NULL for them (fine).
3. **Otherwise** the population is uniform → build the expression with
   `CAST(json_extract_scalar(...) AS <type>)`, which coerces native and string-encoded values alike and
   **errors** (never silent-NULLs) on a bad value. Because profiling already ruled out un-castable
   values, the built expression is guaranteed to run clean. **Never use `TRY_CAST` in the recovery
   expression** — it hides un-recovered values as NULL (it belongs only in the profiling query).

## The validation gate (Phase 5 — do not skip)

Confirm all of these against the pasted test-SELECT output before generating the INSERT:

1. **Type match (decisive).** `recovered_type` (from `typeof(...)`) must equal the good-table column's
   type after Hive→Athena conversion — same field **names, types, and order**. Athena inserts
   positionally into a struct, so order matters. If `typeof` matches the target column type, the INSERT
   will type-check.
2. **Row count** equals the failed-event count for this schema + app_id (from the identification
   query).
3. **No unexpected nulls** in `recovered` — a null usually means a wrong `$.json_path` or a cast that
   silently returned null. Investigate before proceeding.
4. **Values are corrected** — the repaired field holds the fixed value (e.g. a proper integer, not a
   quoted string), and pass-through fields are intact.

If any check fails, fix the recovery expression and re-run the test SELECT (return to Phase 4). Only
generate the INSERT once the type matches and the values are correct. When a check fails and the cause
isn't obvious, see `troubleshooting.md`.
