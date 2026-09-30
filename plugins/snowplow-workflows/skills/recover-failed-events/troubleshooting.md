# Troubleshooting — warehouse failed-event recovery

Shared failure modes first, then a section per warehouse for the dialect-specific ones. The exact SQL
for a fix is in `templates/<warehouse>.md`; the typing rules behind it are in `reference/<warehouse>.md`.

Every entry is **Symptom → Cause → Verify → Fix**. Run the Verify step before applying the Fix:
several of these failures share a symptom, and the check is what tells them apart.

## Shared (any warehouse)

### The generated INSERT is missing the recovery expression (recovery column passed through instead)
**Symptom:** the generated INSERT lists the recovery column as a plain pass-through (its name only), not
the reconstruction expression, so the failed payload lands unrepaired.
**Cause:** the `<recovery_column>` you gave the generator doesn't match the good table's actual column
name (casing, wrong major version, a typo), so the generator's recovery-column branch never matched and
it fell through to pass-through.
**Verify:** search the generated INSERT for the recovery column's name. If it appears in the SELECT
list as a bare name rather than wrapped in the reconstruction, the branch didn't match. On Athena and
Databricks the local script's stderr summary prints only column counts and the pass-through / nulled
counts, plus a `WARNING` line when the recovery column isn't among the good table's columns — that
warning is the tell. BigQuery, Snowflake and the in-warehouse Databricks fallback print no summary, so
there the INSERT search is the whole check.
**Fix:** re-run the "finding the recovery column name" query (or the good-table `DESCRIBE` on Athena),
copy the exact `column_name`, and regenerate.

### Unexpected NULLs in the reconstructed column
**Symptom:** recovered rows have NULL where a value was expected.
**Cause:** a wrong JSON path (a field renamed in the schema vs the payload), or a value that didn't
coerce. On Databricks this happens silently (see its section).
**Verify:** re-run the Phase-3.5 profiling query for the affected field and read `_absent` and
`_uncoercible`. `_absent > 0` is a wrong or renamed path; `_uncoercible > 0` is a heterogeneous
population; both zero means the path in the recovery expression isn't the one you profiled.
**Fix:** a renamed field (`_absent > 0`) — map the payload key onto the target field name. An
un-coercible value (`_uncoercible > 0`) — the population isn't homogeneous, so partition it and recover
the coercible rows. Both zero — correct the path in the recovery expression to the profiled one.

### `additionalProperties` failure, or a field renamed between schema and payload
**Symptom:** the failure is `additionalProperties` / an extra field, or a payload key doesn't match a
schema field name.
**Cause:** the tracker sent a field the schema doesn't allow, or a misspelled key (e.g. payload
`nubmers` vs schema `numbers`).
**Verify:** run the payload inspection query (Phase 3) and list the payload's keys beside the target
column's field names from the good-table type. The stray key is the one with no matching field — and a
near-miss spelling is the tell for a rename rather than a genuine extra.
**Fix:** don't decide this yourself — **ask the user** whether the stray field should be dropped or
mapped onto a field the schema does define, per *Recovering an `additionalProperties` failure* in the
SKILL.md. Then reconstruct only the fields the target type lists (drop), or read the value from the
payload key and emit it under the target field name (map).

### It's a `ResolutionError`, not a `ValidationError`
**Symptom:** `failure_type` is `ResolutionError` — Iglu couldn't resolve the schema.
**Cause:** transient/misconfigured registry, a wrong URI (typo/nonexistent version), or a never-published
schema — the payload may conform fine.
**Verify:** read `failure_type` and the recorded URI from the drill-in (the pack's *Recorded schema
URI*). Then confirm the corrected URI resolves now — registry listing, `snowplow-cli`, or the Console —
and that a target column for it already exists in the good table. Both must hold before you recover.
**Fix:** see "Recovering a ResolutionError" in the SKILL.md. Filter failed rows on the URI **as recorded**
in the failure context, but derive the target column and `_schema_version` from the **corrected** URI.
Bail only if the schema can't be made to resolve or no target column can exist.

### The duplicate pre-check returns rows
**Symptom:** the pre-check lists `event_id`s already in the good table.
**Cause:** these events were recovered before; re-running would duplicate them.
**Verify:** re-run the pre-check with the exact window the recovery will use. It filters only on that
window, `app_id` and the failing schema — it has no source predicate — so compare its row count against
the identification count for the same schema + app_id, summed across sources. Equal means the whole set
was recovered before; fewer means a partial earlier run (on a mixed-source schema, possibly one source's
run) you'll have to exclude.
**Fix:** decide with the user — stop, narrow the window/scope to exclude the already-recovered rows, or
proceed knowingly (rare). Do not blindly re-run.

### Staging → good promote fails on column misalignment
**Symptom:** the `INSERT INTO good SELECT * FROM staging` errors on column count/type mismatch.
**Cause:** the staging table wasn't created as an exact mirror of the good table, so `SELECT *` doesn't
line up positionally.
**Verify:** list both tables' columns in `ordinal_position` order (`DESCRIBE` on Athena) and diff
them. The first position where the names differ is the misalignment.
**Fix:** recreate staging with the pack's staging-create (a `LIKE` / `SELECT * … LIMIT 0` of the good
table), re-run the recovery INSERT into it, then promote.

### Landed row count ≠ the identification count
**Symptom:** fewer (or more) rows landed than the identification query reported for the schema.
**Cause:** a mismatched time window between identification and recovery, a source split not applied
(contexts vs unstruct counted together), or the failure array wasn't flattened consistently.
**Verify:** re-run the identification query with the *recovery's* window and source scope. If the
counts now agree, the two queries were scoped differently. If they still don't, check every predicate
flattens the failure array rather than indexing `[0]`/`[1]`.
**Fix:** carry the **same** time window through every query. Scope both identification and recovery to one
`source`. Confirm every query flattens the failure array and matches the schema on the flattened element
(so an event whose target failure isn't first is counted and recovered the same way).

## Athena

### Test SELECT / INSERT errors: cast or coercion failure
**Symptom:** the Phase 4 test SELECT (or the INSERT) fails with a cast error such as
`Cannot cast 'abc' to bigint` on a recovered field.
**Cause:** a value in the payload genuinely doesn't convert to the target type — the failed rows don't
all share one recovery — or the expression was built before the Phase 3.5 profiling that would have
caught it.
**Verify:** run the **field profiling query** (`templates/athena.md`) for that field with its target
type in the `TRY_CAST`; a non-zero `_uncoercible` count confirms un-castable values exist.
**Fix:** if `_uncoercible > 0`, **partition the offending rows off** — list them, agree the scope with
the user, recover only the coercible population. Do **not** switch the recovery expression to
`TRY_CAST` to dodge the error: that hides un-castable values as silent NULLs and writes an incomplete
recovery. `TRY_CAST` belongs in the profiling query only.

### A reserved word is used as a ROW field name
**Symptom:** the `CAST(... AS ROW(...))` errors on a field named like a SQL keyword or a type (`date`,
`value`, `float`, …).
**Cause:** unquoted reserved/type-keyword identifiers in a Trino `ROW` type.
**Verify:** read the `ROW(...)` type in the generated statement — every field name should be
double-quoted. An unquoted one is the field that errors.
**Fix:** the generator quotes **every** struct field name (`"date"`, `"value"`) — this is always safe.
If hand-building, quote the field names. See the Hive→Athena conversion in `reference/athena.md`.

## BigQuery

### `CAST(NULL AS <type>)` on the failure column is rejected
**Symptom:** the generated INSERT errors on the failure column's `CAST(NULL AS <full type>)`.
**Cause:** the failure column's full nested type is unusual for a null cast.
**Verify:** run the failing cast on its own — `SELECT CAST(NULL AS <the type from
INFORMATION_SCHEMA.COLUMNS>)`. It reproduces the error without the rest of the INSERT in the way.
**Fix:** fall back to a simplified null of a compatible shape, e.g.
`CAST(NULL AS ARRAY<STRUCT<schema STRING, data JSON>>)`, or give the INSERT an explicit column list that
omits the failure column.

### Strict accessor errors with "not an integer" (or similar)
**Symptom:** `INT64(data.field)` (or another strict accessor) errors on a value.
**Cause:** the value isn't already that native JSON type (e.g. an int sent as `"5"`).
**Verify:** run `JSON_TYPE(data.field)` across all failed rows (the profiling probe) and read the
distinct types. Anything other than the native type you assumed — `"string"` where you expected
`"number"`, or a mix — means the strict accessor can't hold for the whole set.
**Fix:** use `CAST(JSON_VALUE(data.field) AS INT64)` for that field. The profiling gate flags which
fields are native (strict) vs string-encoded/mixed (`CAST(JSON_VALUE …)`). Never switch to `LAX_`.

## Databricks

### The test SELECT ran clean, but the casts may not have held
**Symptom:** the query succeeded, yet some recovered values are wrong or NULL.
**Cause:** `GET_JSON_OBJECT` returns NULL on a bad path and `CAST` returns NULL on an un-castable value
in legacy mode — neither errors. "It ran" is not proof (see `reference/databricks.md`).
**Verify:** run the per-field null-count check (`templates/databricks.md`) over the whole recovery
set and compare each field's null count against its `_absent` count from Phase-3.5 profiling. A null
count above `_absent` is the silent cast failure — those rows had a value and lost it.
**Fix:** run the per-field null-count check (`templates/databricks.md`) and eyeball the values; a non-zero
count on a required field means a wrong path or a bad value. The Phase-3.5 profiling gate pre-empts this.

### Delta INSERT errors on by-name struct field resolution
**Symptom:** the positional `INSERT ... SELECT` errors on the reconstructed struct column.
**Cause:** the `NAMED_STRUCT` field names/types/order don't match the target column's `full_data_type`.
**Verify:** print the target column's `full_data_type` and your `NAMED_STRUCT` side by side and walk
them field by field. Order counts, not just names and types.
**Fix:** read `full_data_type` exactly and match field names, types, and order. `_schema_version` first
for a `contexts_*` column; omit it for `unstruct_event_*` unless the type lists it.

### The in-warehouse generator's INSERT comes out with unquoted string literals (won't parse)
**Symptom:** the emitted INSERT has `app_id = test-app` (quotes gone) and won't parse.
**Cause:** Spark has **no** `''` escape — a doubled single quote coalesces into nothing. The in-warehouse
generator builds the INSERT as one Spark string literal.
**Verify:** look at the `app_id` and schema-URI predicates in the emitted INSERT. If they read
`app_id = test-app` rather than `app_id = 'test-app'`, the quotes coalesced away.
**Fix:** backslash-escape every single quote in the recovery expression (`\'`) for the in-warehouse
fallback. Better: use the local `scripts/generate_insert_databricks.py`, which assembles the SQL locally
so there's no string-literal layer to escape.

### `CAST(NULL AS <full_data_type>)` on the failure column is rejected
**Symptom:** the generated INSERT errors on the failure column's null cast.
**Cause:** the full nested type is unusual for a null cast.
**Verify:** run the cast on its own — `SELECT CAST(NULL AS <the full_data_type from
information_schema.columns>)` — to confirm it's the cast and not another column in the INSERT.
**Fix:** fall back to a simplified shape, e.g. `CAST(NULL AS ARRAY<STRUCT<schema:STRING, data:STRING>>)`,
or give the INSERT an explicit column list omitting the failure column.

## Snowflake

### Test SELECT errors on a `::TYPE` cast
**Symptom:** the Phase 4 test SELECT fails casting a `data:<field>` value to its target type — e.g.
`Numeric value '...' is not recognized` on `::INTEGER`.
**Cause:** some rows genuinely can't become the target type, so the failed rows do **not** all share
one recovery. Snowflake errors on a bad `::TYPE` cast rather than continuing, which is the correct,
loud behaviour — and the most common test-SELECT error here.
**Verify:** run the **profiling query** (`templates/snowflake.md`) and read `_uncoercible` and
`_variant_types` for that field. This is the Phase 3.5 gate that exists to catch it first.
**Fix:** if `_uncoercible = 0` for every field, the cast will run clean (an int sent as `"5"` still
coerces) — the error was on a field whose target type you had wrong, so correct it and re-run. If
`_uncoercible > 0`, **partition those rows off** and recover them separately, or fix at source. Do
**not** switch the recovery expression to `TRY_CAST` to dodge the error — Snowflake would then return
silent NULLs for exactly the values that need attention, and write an incomplete recovery.

### The reconstructed entity is the wrong shape, or is missing `_schema_version`
**Symptom:** validation shows the recovered VARIANT doesn't match a good row.
**Cause:** wrong wrapper (array vs single object) or a missing/extra `_schema_version`.
**Verify:** run the *inspect a validated event* query (`templates/snowflake.md`) and compare the good
row's object against yours key by key — wrapper first (array vs bare object), then whether
`_schema_version` is present.
**Fix:** a `contexts_*` recovery is `ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(...))` with `_schema_version`
first. An `unstruct_event_*` recovery is a single `OBJECT_CONSTRUCT(...)`, usually with no
`_schema_version` — but match whatever the validated good row showed rather than assuming either way.

### `TYPEOF` errors with "Invalid argument types for function 'TYPEOF'"
**Symptom:** the test SELECT's `TYPEOF(...::TYPE)` errors.
**Cause:** `TYPEOF` accepts only a VARIANT, but `::TYPE` returns a native scalar.
**Verify:** look at what you passed `TYPEOF`. If the argument ends in `::TYPE`, that's it — the cast
has already turned the VARIANT into a native scalar.
**Fix:** build the reconstructed column in a CTE first, then call `TYPEOF(recovered[0]:field)` (VARIANT
navigation into the array you built) in the outer query. See `templates/snowflake.md`.
