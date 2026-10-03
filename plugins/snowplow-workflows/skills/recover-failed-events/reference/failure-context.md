# Reference — the failure context, navigation & the gates (shared)

Warehouse-independent background for the recovery flow: what the failure context holds, how to read it,
the contexts-vs-unstruct distinction, and the classification / profiling / validation gates. The
**per-warehouse dialect** — the exact functions and syntax — is in `reference/<warehouse>.md`; the
runnable SQL is in `templates/<warehouse>.md`.

## Where the failure lives

Snowplow writes every schema-validation failure into a column always named
`contexts_com_snowplowanalytics_snowplow_failure_1`. It is an **array**, with one element per failed
entity (see "One event, several failures" below). Each element is a struct with these fields:

| Field | Meaning |
|---|---|
| `_schema_version` | Version of the failure-context schema itself |
| `component_name` / `component_version` | Pipeline component that rejected the event |
| `data` | The original event payload — read scalars out of it per the dialect (see the navigation table) |
| `errors` | One entry per validation error, carrying `source`, `path`, `keyword`, `message`, … `source` is the key one (below) |
| `failure_type` | e.g. `ValidationError`, `ResolutionError` |
| `schema` | Iglu URI of the schema that failed |
| `timestamp` | When the failure occurred |

## One event, several failures — flatten, don't index `[0]`

A single event can fail validation on **several entities at once**, so the failure array can hold more
than one element. Reading only the first element (`[0]` / `[1]` / `[SAFE_OFFSET(0)]`) would miss any
schema that isn't an event's *first* failure — it would never appear in the identification counts and
never match a recovery predicate, so those events would go unrecovered silently.

Every query therefore **flattens** the failure array (the dialect's *Failure-array expand* — see below)
and matches the target schema on the flattened element, wherever it sits. The flatten yields one row
per event **per source**: a schema that failed both as a context entity and as the self-describing
event carries the same URI on two entries, so matching on schema alone fans that event out to two rows
and inserts its `event_id` twice. Always scope on **`source`** as well as `schema` — see the next
section. **Recover one schema per run**, and re-run identification after each to see what remains.

## The `source` field — contexts vs unstruct (inside `errors`, never top-level)

Whether the event failed as a **context entity** or as the **self-describing (unstruct) event** is
recorded on each error's `source` — *not* a top-level failure field (reading the top-level `source`
returns NULL or doesn't exist). Read it from inside the `errors` element with the dialect's navigation.
Values:

- **`contexts`** → recovers into the `contexts_<vendor>_<name>_<major>` column, an **array of structs**
  (this skill's main path). The struct's first field is `_schema_version`.
- **`unstruct`** → the *same* schema failed as the self-describing event → recovers into the
  `unstruct_event_<vendor>_<name>_<major>` column, a **single struct** (not an array), usually with
  **no `_schema_version`** field. Different target column *and* different reconstruction (no array
  wrapper). Inspection/validation read the column directly — no array index, no size function; filter
  on `IS NOT NULL`. See "Recovering an unstruct failure" in the SKILL.md.

**One schema can fail both ways in the same window.** A mix of `contexts` and `unstruct` can't go
through one recovery expression: scope the run to one `source`, recover it, then handle the other as a
separate run into its own column.

**Valid entities the failed event also carried are preserved.** The failed-events table materialises a
passing attached entity in its own column, and the recovery's pass-through carries it into the good row
untouched. Recover only what failed; do **not** null the sibling entity columns.

## Per-warehouse navigation table

The one table that maps the shared concepts above onto each dialect. The pack (`reference/<warehouse>.md`)
expands on the typing rules; the SQL is in `templates/<warehouse>.md`.

| Concept | Athena / Trino | Snowflake | BigQuery | Databricks |
|---|---|---|---|---|
| Failure `data` type | JSON string | VARIANT | `JSON` | JSON string |
| Read a `data` scalar | `json_extract_scalar(data,'$.f')` | `data:f::TYPE` | `JSON_VALUE(data.f)` / strict `INT64()` | `GET_JSON_OBJECT(data,'$.f')` |
| Read a nested `data` object/array | `CAST(json_extract(data,'$.o') AS ROW(…))` / `AS ARRAY(ROW(…))` (`json_extract` already returns JSON — no `json_parse`) | `data:o` (already VARIANT — no extractor) | no JSON→STRUCT cast; rebuild per field: `STRUCT(JSON_VALUE(data.o.x) AS x, …)` / `ARRAY(SELECT STRUCT(JSON_VALUE(e.x) AS x, …) FROM UNNEST(JSON_QUERY_ARRAY(data.a)) AS e WITH OFFSET i ORDER BY i)` | `FROM_JSON(GET_JSON_OBJECT(data,'$.o'),'<schema>')` |
| `errors` element | `array(varchar)` JSON strings | array of VARIANT objects | `ARRAY<JSON>` | `ARRAY<STRING>` JSON strings |
| `source` path | `json_extract_scalar(errors[1],'$.source')` | `errors[0]:source::STRING` | `JSON_VALUE(errors[SAFE_OFFSET(0)].source)` | `GET_JSON_OBJECT(errors[0],'$.source')` |
| Failure-array expand | `CROSS JOIN UNNEST(...) AS t(failure_ctx)` | `LATERAL FLATTEN(input => ...) f` | `, UNNEST(...) AS f` | `LATERAL VIEW explode(...) t AS f` |
| Good-entity array index | `[1]` (1-based) | `[0]` | `[SAFE_OFFSET(0)]` | `[0]` |
| Good-entity array size | `cardinality(<col>)` | `ARRAY_SIZE(<col>)` | `ARRAY_LENGTH(<col>)` | `size(<col>)` |
| Recorded schema URI | `failure_ctx.schema` | `f.value:schema::STRING` | `f.schema` | `f.schema` |
| Grounding source (recovery-column type) | good-table `DESCRIBE` | a **validated good row** (VARIANT, no DDL) | `INFORMATION_SCHEMA` `data_type` | `information_schema` `full_data_type` |

Bare `data` / `errors` in the cells are fields of the flattened element: qualify them with the expand
alias, as the schema-URI row does (`failure_ctx.data`, `f.value:data`, `f.data`). The recovery CTEs
re-alias that element, so inside a recovery expression read `failure_data` (Athena),
`failure_entry:data` (Snowflake) or `failure_entry.data` (BigQuery); Databricks keeps `f.data`.

**A nested field is not a scalar.** The scalar extractors don't return a typed value for an object or
array field: `json_extract_scalar` and `JSON_VALUE` return NULL, and `GET_JSON_OBJECT` returns the JSON
text as a STRING, which Databricks refuses to `CAST` to an `ARRAY`/`STRUCT`. Use the nested-read form in
the row above. On Databricks that form can still be wrong silently: `FROM_JSON` returns NULL for a field
whose name (case-sensitive) or type doesn't match the schema string, so a mismatched nested field comes
back NULL on every row instead of erroring. Profile the field in Phase 3.5 like any other, and include
its sub-fields in the Phase 5 null-count check.

Two genuine outliers, not just syntax:

- **Snowflake is schemaless.** Columns are VARIANT, so there is no strict struct-type contract — no
  field-order or reserved-word concern. Ground the target types from a **validated good row**, not a
  DDL type. See `reference/snowflake.md`.
- **Databricks can silently NULL.** A wrong JSON path or an un-castable value yields NULL rather than an
  error, so "the query ran" is *not* proof the recovery is correct. Validation leans on a per-field
  null-count check. See `reference/databricks.md`.

## Grounding the target shape (never guess it)

The values come from the failed payload, but the **types and field names you extract into are not
defined by that payload** — the payload is exactly what failed validation. They are defined by the Iglu
schema, materialised in the recovery column's type. Resolve the intended shape from ground truth:

1. **The recovery column's type** (the pack's grounding source). On Athena, BigQuery and Databricks this
   is the authoritative struct contract: field names, types, order, and whether `_schema_version` is a
   field. On Snowflake the column is VARIANT and carries no type information, so this step yields nothing.
2. **A validated good-table row for the same entity — always query one.** Run the pack's *inspect a
   validated event* query. It is the only grounding Snowflake has, and on the other three it is what
   catches a column type you misread. Never assert a shape you have not observed: whether an unstruct
   column carries `_schema_version` is a question you answer by looking, not by defaulting.

Do not infer types from the failed payload.

### No validated events in the good table → stop, don't recover

If the good table holds **no validated events for this entity** — the recovery column is absent, or it
exists but every row is NULL — **do not build a recovery.** Say so plainly and stop.

The reason is the loader, not the SQL. Inserting into a column the loader has never populated means
*you* are establishing that column's shape: adding the column outright, or fixing a struct contract the
loader hasn't set yet. If that differs from what the loader later creates — a field order, a type width,
a nullable flag — the loader can fail on its next write, turning a failed-events problem into a broken
pipeline.

Tell the user to send one valid event of this schema through the pipeline first and let the loader
create and populate the column, then re-run the recovery. The failed events aren't going anywhere.

Widen the lookback before concluding the table is empty — a validated example may simply predate the
default window. "Zero rows in the last 7 days" is not "no validated events".

## Column classification (what the generator does, per column)

For every column in the **good** events table, the generated INSERT decides one SELECT expression:

1. **The failure column** (`contexts_com_snowplowanalytics_snowplow_failure_1`) → excluded / `CAST(NULL …)` — never re-carried into the good table.
2. **`load_tstamp`** → `CURRENT_TIMESTAMP()` (fresh for reprocessed rows).
3. **The recovery column** → the validated recovery expression.
4. **Any other column present in the failed table** → pass through by name. This covers the atomic
   columns (the failed table carries the full atomic set) and any materialised sibling entity — so
   membership in the failed table *is* the atomic-vs-custom classification; no hardcoded column list.
5. **Column only in the good table** → `CAST(NULL AS <type>)`.

## Profiling gate (Phase 3.5)

Before building any recovery expression, profile **every field you'll recover** across **all**
failed rows with a query that *cannot error* (the pack's *Profiling probe (non-erroring)*). Decide
per field, in order: any value **un-coercible** to the target type → stop and partition (the
population isn't homogeneous, so one expression won't fit); any value **absent** → required field
partitions, optional field can be NULL; else uniform and coercible → build it. This confirms one
expression covers the whole set before you write it (and, on Databricks, pre-empts the silent-NULL
trap).

## Validation gate (Phase 5)

On the test SELECT output, confirm: the reconstructed column's type/shape matches the target
field-for-field (order matters on the strict warehouses); the row count equals the failed-event count
for this schema + app_id + source; no unexpected NULLs (on Databricks a NULL is a silent bad-cast, not an
error — the decisive check there); and the repaired values are actually corrected. Pass the gate only
when all four hold.
