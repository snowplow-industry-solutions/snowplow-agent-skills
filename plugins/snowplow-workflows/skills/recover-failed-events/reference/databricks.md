# Dialect pack — Databricks

Load this in Phase 1 once the warehouse is Databricks. Shared concepts (failure model, navigation,
classification, the gates) are in `reference/failure-context.md`; the runnable SQL is in
`templates/databricks.md`.

## Dialect at a glance

| Concept | Databricks |
|---|---|
| Table qualifier | `catalog.schema.table` (Unity Catalog, three-part) |
| Grounding source (recovery-column type) | `full_data_type` (`information_schema.columns`) |
| Failure-array expand | `LATERAL VIEW explode(...) t AS f` |
| Read a `data` scalar | `GET_JSON_OBJECT(f.data, '$.field')` |
| Cast | `CAST(... AS <type>)`; `try_cast` in profiling |
| contexts reconstruction | `ARRAY(NAMED_STRUCT('_schema_version','1-0-0', 'f', CAST(...)))` |
| unstruct reconstruction | `NAMED_STRUCT(...)`, no array, no `_schema_version` |
| Profiling probe (non-erroring) | `get_json_object` + `try_cast` + `count_if` |
| Validation signal | **no-unexpected-NULLs** (per-field null-count) — a clean run is *not* proof |
| Staging create | CTAS `SELECT * ... LIMIT 0` (or `LIKE`) |
| Time travel | `TIMESTAMP AS OF` / `VERSION AS OF` |
| Lookback date-math | `DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)` (bare integer, no `INTERVAL`) |
| INSERT-build mechanism | local `scripts/generate_insert_databricks.py` (primary); in-warehouse `concat` generator (fallback) |
| Recovery-expr escaping (in-warehouse fallback only) | backslash `\'` — Spark has **no** `''` escape; the script path leaves quotes unchanged |
| Good-entity array index | `[0]` |

**Databricks silent-NULL trap:** `GET_JSON_OBJECT` returns NULL on a bad path and `CAST` returns NULL on
an un-castable value in legacy mode (only ANSI mode errors), so a test SELECT that runs is **not** proof
the recovery is correct. The Phase-3.5 profiling gate confirms coercibility up front and the per-field
null-count check makes the post-hoc check mechanical — both are load-bearing here, not optional.

## Strict struct typing, column classification & the validation gate

**The decision this doc helps you make:** whether the reconstructed entity is shaped correctly enough
that a positional `INSERT ... SELECT` into a Delta table will succeed and land clean data — and how
each other column is classified. This is the judgment layer behind the INSERT generation in
`templates/databricks.md`.

Like the Athena flow, the wide INSERT is assembled by a **local script** (`scripts/generate_insert_databricks.py`)
from the good and failed tables' `information_schema.columns` pastes — not by an in-warehouse generator
query, because building the INSERT as a Spark string literal means every quote in the payload must be
backslash-escaped and one wrong escape silently drops it (see `troubleshooting.md`). The
classification below is what the script applies per column;
the in-warehouse generator (kept only as a no-Python fallback) applies the same rules. Like the
Athena/BigQuery flow, Databricks struct typing is **strict**: the reconstructed entity's field names,
types, and order must match the target column's type.

## Strict struct typing (the key Databricks constraint)

Context entity columns are native `ARRAY<STRUCT<...>>`; the **self-describing (unstruct) event column
is a single `STRUCT<...>`, not an array**. When you `INSERT ... SELECT` into a Delta table, the
reconstructed value must be **type-compatible** with the target column. Delta resolves struct fields
**by name**, so the field **names must match exactly**; keep the field **types** matching too, and
keep the **order** matching so the generated positional INSERT reads cleanly and reviews easily.

Read the shape from the recovery column's `full_data_type` and build to match it: `ARRAY(NAMED_STRUCT(...))`
for a `contexts_*` column, a bare `NAMED_STRUCT(...)` for an `unstruct_event_*` column. Note the field
set can differ too — the `contexts_*` struct carries `_schema_version`, the `unstruct_event_*` struct
usually does not. Match whatever the type lists; don't assume.

Get that contract from the recovery column's `full_data_type` in `INFORMATION_SCHEMA` (see "Finding
the recovery column name" in `templates/databricks.md`), e.g.:

```
ARRAY<STRUCT<_schema_version: STRING, user_id: BIGINT, user_name: STRING>>
```

Build the recovery expression to match it field-for-field, in order. Never guess the shape — read it
from this `full_data_type` and/or a validated good-table row (see `reference/failure-context.md`).

**Why order matters:** the generated INSERT has no explicit column list — it is positional. The
recovery struct's fields are written in the order you give them, so a reordered field breaks the
positional line-up and reviews poorly even when the names are right.

## Column classification (what the generator does, per column)

For the INSERT, every column in the **good** events table is classified. The script (or the fallback
generator query) reads both tables' `information_schema.columns` and decides, per column in good-table
`ordinal_position` order:

1. **The failure column** (`contexts_com_snowplowanalytics_snowplow_failure_1`) →
   `CAST(NULL AS <good full_data_type>)` — kept in position (positional INSERT), always null in
   recovered rows. *Why null:* re-carrying the failure context into the good table would contaminate it.
2. **`load_tstamp`** → `CURRENT_TIMESTAMP()` (fresh timestamp for reprocessed rows).
3. **The recovery column** (the entity being repaired) → the confirmed `ARRAY(NAMED_STRUCT(...))`
   expression.
4. **Column present in both good and failed tables** → pass through by name (covers all atomic
   columns and any custom column that holds values for events which failed on a *different* entity).
5. **Column only in the good table** → `CAST(NULL AS <target full_data_type>)`.

Because the failed events table already contains every atomic column, the good-vs-failed join does
the atomic-vs-custom classification for you — there is **no separate atomic list to maintain**. The
canonical atomic set is retained at the bottom of this file for reference only.

## Choosing the extractor per field (from profiling — Phase 3.5)

Before writing any recovery expression, run the profiling query (`templates/databricks.md`) to
learn, per field across *all* failed rows, whether every value casts to its target type and whether
the field is always present. This is also how you pre-empt Databricks' **silent-NULL trap**: confirm
coercibility up front rather than discovering NULLs after the write. Decide, per field:

1. **Any field `_uncoercible > 0`** → some values can't cast to the target type → **stop, list the
   offending rows, and partition/scope** with the user; the failed rows don't share one recovery.
2. **Any field `_absent > 0`** → the field is missing from some rows → required→partition,
   optional→NULL.
3. **Otherwise** → the population is uniform; build the recovery expression
   (`CAST(GET_JSON_OBJECT(...) AS <type>)` coerces native and string-encoded values, and profiling has
   confirmed every value converts — no silent NULLs).

## The validation gate (Phase 5 — do not skip)

Confirm all of these against the pasted test-SELECT output before generating the INSERT:

1. **No unexpected NULLs (decisive here).** Unlike Snowflake/BigQuery, Databricks can return NULL
   silently — `GET_JSON_OBJECT` on a wrong path returns NULL, and `CAST` returns NULL on a bad value in
   legacy (non-ANSI) mode. So a null where a value was expected is the primary signal of a wrong JSON
   path or a genuinely un-castable value — investigate every one before proceeding. Use the per-field
   null-count check; every required field should be 0. **Do not** treat "the query ran" as proof the
   casts held.
2. **Values are corrected** — the repaired field(s) hold the corrected values (e.g. the string is now
   a proper integer, not NULL), and pass-through fields are intact.
3. **Struct shape matches the target** — the reconstructed struct's field names, types, and order
   match the recovery column's `full_data_type` exactly (Delta resolves struct fields by name for the
   INSERT), and `_schema_version` is present as the first field.
4. **Row count** equals the failed-event count for this schema + app_id (from the identification query).

If any check fails, fix the recovery expression and re-run the test SELECT (return to Phase 4). Only
generate the INSERT once the values are correct (no unexpected nulls), the shape matches, and the row
count is right. When a check fails and the cause isn't obvious, see `troubleshooting.md`.

## Canonical atomic column set (reference only)

In Databricks the good-vs-failed join classifies columns for you, so this list is informational — it
is the set of columns that are "atomic" (always present, pass through by name). Anything else is a
custom `contexts_*` / `unstruct_event_*` column.

```
app_id platform etl_tstamp collector_tstamp dvce_created_tstamp
event event_id txn_id name_tracker v_tracker v_collector v_etl
user_id user_ipaddress user_fingerprint domain_userid domain_sessionidx
network_userid geo_country geo_region geo_city geo_zipcode
geo_latitude geo_longitude geo_region_name ip_isp ip_organization
ip_domain ip_netspeed page_url page_title page_referrer
page_urlscheme page_urlhost page_urlport page_urlpath page_urlquery
page_urlfragment refr_urlscheme refr_urlhost refr_urlport refr_urlpath
refr_urlquery refr_urlfragment refr_medium refr_source refr_term
mkt_medium mkt_source mkt_term mkt_content mkt_campaign
se_category se_action se_label se_property se_value
tr_orderid tr_affiliation tr_total tr_tax tr_shipping
tr_city tr_state tr_country ti_orderid ti_sku ti_name
ti_category ti_price ti_quantity pp_xoffset_min pp_xoffset_max
pp_yoffset_min pp_yoffset_max useragent br_name br_family
br_version br_type br_renderengine br_lang br_features_pdf
br_features_flash br_features_java br_features_director
br_features_quicktime br_features_realplayer br_features_windowsmedia
br_features_gears br_features_silverlight br_cookies br_colordepth
br_viewwidth br_viewheight os_name os_family os_manufacturer
os_timezone dvce_type dvce_ismobile dvce_screenwidth dvce_screenheight
doc_charset doc_width doc_height tr_currency tr_total_base
tr_tax_base tr_shipping_base ti_currency ti_price_base base_currency
geo_timezone mkt_clickid mkt_network etl_tags dvce_sent_tstamp
refr_domain_userid refr_dvce_tstamp domain_sessionid derived_tstamp
event_vendor event_name event_format event_version event_fingerprint
true_tstamp load_tstamp
```
