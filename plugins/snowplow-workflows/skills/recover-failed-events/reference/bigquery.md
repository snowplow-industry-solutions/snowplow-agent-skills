# Dialect pack — BigQuery

Load this in Phase 1 once the warehouse is BigQuery. Shared concepts (failure model, navigation,
classification, the gates) are in `reference/failure-context.md`; the runnable SQL is in
`templates/bigquery.md`.

## Dialect at a glance

| Concept | BigQuery |
|---|---|
| Table qualifier | `project.dataset.table` (backticked) |
| Grounding source (recovery-column type) | `data_type` (`INFORMATION_SCHEMA.COLUMNS`) |
| Failure-array expand | `, UNNEST(...) AS f` |
| Read a `data` scalar | `JSON_VALUE(f.data.field)`; strict `INT64()`/`STRING()`/`FLOAT64()`/`BOOL()` where native |
| Cast | strict accessor **or** `CAST(JSON_VALUE(...) AS <T>)`; `SAFE_CAST` in profiling |
| contexts reconstruction | `[STRUCT(... AS field)]`, `_schema_version` first |
| unstruct reconstruction | `STRUCT(...)`, no array, usually no `_schema_version` (confirm on a good row) |
| Profiling probe (non-erroring) | `JSON_TYPE` + `JSON_VALUE` + `SAFE_CAST` + `COUNTIF` (with a `_json_null` counter) |
| Validation signal | no `TYPEOF`; compare struct shape vs `data_type` — a clean run proves the casts held |
| Staging create | `CREATE TABLE ... LIKE` |
| Time travel | `FOR SYSTEM_TIME AS OF` |
| Lookback date-math | `DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)` |
| INSERT-build mechanism | in-warehouse generator (`FORMAT("""…""")` + `STRING_AGG`) |
| Recovery-expr embedding | triple-quoted `'''…'''` (no escaping; survives a wrapped paste) |
| Good-entity array index | `[SAFE_OFFSET(0)]` |
| Good-entity array size | `ARRAY_LENGTH(<recovery_column>)` |
| Recorded schema URI | `f.schema` (the URI **as recorded** — the ResolutionError filter) |

BigQuery is the only warehouse with **strict typed JSON accessors**, so extraction is a per-field
choice: the strict accessor where the value is already the native JSON type, `CAST(JSON_VALUE(...) AS
<T>)` where it's string-encoded or mixed — the profiling gate picks per field. **Never use the `LAX_`
accessors** (they swallow an un-coercible value into a silent NULL).

## Strict struct typing, column classification & the validation gate

**The decision this doc helps you make:** whether the reconstructed entity is shaped correctly enough
that a positional `INSERT ... SELECT` will succeed and land clean data — and how the generator decides
what to do with every other column. This is the judgment layer behind the INSERT-generator template
in `templates/bigquery.md`.

## Strict struct typing (the key BigQuery constraint)

Context entity columns are native `ARRAY<STRUCT<...>>`; the **self-describing (unstruct) event column
is a single `STRUCT<...>`, not an array**. A positional `INSERT ... SELECT` requires the SELECT's
output type for each column to **match the target column's type exactly**. For the reconstructed entity
this means the value you build must have the **same field names, the same field types, and the same
field order** as the target column's declared type — wrapped as `[STRUCT(...)]` for a `contexts_*`
column, or a bare `STRUCT(...)` for an `unstruct_event_*` column. The field set can differ too: the
`contexts_*` struct carries `_schema_version`, the `unstruct_event_*` struct usually does not. Match
whatever the type lists.

Get that contract from the recovery column's `data_type` in `INFORMATION_SCHEMA`, e.g.:

```
ARRAY<STRUCT<_schema_version STRING, user_id INT64, user_name STRING>>
```

Build the recovery expression to match it field-for-field, in order. Never guess the shape — read it
from this `data_type` and/or a validated good-table row (see `reference/failure-context.md`).

**Why order matters:** the generated INSERT has no explicit column list — it is positional. The
recovery struct's fields are written in the order you give them, and BigQuery matches the struct
type positionally, so a reordered field is a type mismatch even if the names are right.

## Column classification (what the generator does, per column)

For the INSERT, every column in the **good** events table is classified. The generator query joins
`good` and `failed` `INFORMATION_SCHEMA.COLUMNS` and, per column in good-table `ordinal_position`
order, decides:

1. **The failure column** (`contexts_com_snowplowanalytics_snowplow_failure_1`) →
   `CAST(NULL AS <good data_type>)` — kept in position (positional INSERT), always null in recovered
   rows. *Why null:* re-carrying the failure context into the good table would contaminate it.
2. **`load_tstamp`** → `CURRENT_TIMESTAMP()` — a fresh timestamp for reprocessed rows.
3. **The recovery column** (the entity being repaired) → the confirmed `[STRUCT(...)]` expression.
4. **Column present in both good and failed tables** → pass through by name. This covers all atomic
   columns *and* any custom column that holds values for events which failed on a *different* entity.
5. **Column only in the good table** → `CAST(NULL AS <target_data_type>)`.

Because the failed events table already contains every atomic column, the good-vs-failed join does
the atomic-vs-custom classification for you — there is **no separate atomic list to maintain**. The
canonical atomic set is retained at the bottom of this file for reference only.

## Choosing the extractor per field (from profiling — Phase 3.5)

Do **not** fix on one extraction function. Run the profiling query (`templates/bigquery.md`) to
learn, per field across *all* failed rows, the JSON types present and whether every value coerces to
the target type, then pick the strictest option the data supports. In order:

1. **Any field has `_uncoercible > 0`** → the failed rows don't share one recovery — stop, surface the
   offending rows, and partition/scope with the user. Don't suggest a recovery expression yet.
2. **Any field has `_absent > 0` or `_json_null > 0`** → some rows carry no value: the field is missing
   (`_absent`) or present but explicitly JSON `null` (`_json_null` — which BigQuery would otherwise slip
   past *both* `_absent` and `_uncoercible`, landing a silent NULL in the good table). Both extract to
   SQL NULL. Partition those rows off if the schema requires the field; if optional, NULL is an
   acceptable recovered value. Decide with the user.
3. **Per field, once all are coercible:**
   - `_json_types` is exactly the **native** type (`number` for INT64/FLOAT64, `string` for STRING,
     `boolean` for BOOL) → **strict accessor** (`INT64()/STRING()/FLOAT64()/BOOL()`) — reads the native
     value, self-validating.
   - a **wrong or mixed** encoding (e.g. `string`, or `number,string`) → **`CAST(JSON_VALUE(...) AS
     <TYPE>)`** — coerces via a string round-trip.

Both the strict accessors and `CAST` **error** on an un-castable value, so nothing silently NULLs; and
because profiling already ruled out un-castable values, the built expression is guaranteed to run
clean. **Never use the lenient `LAX_` accessors** — they hide un-recovered values as NULL.

## The validation gate (Phase 5 — do not skip)

Confirm all of these against the pasted test-SELECT output before generating the INSERT:

1. **Profiling confirmed + the query ran clean (decisive).** Phase 3.5 already proved every value
   coerces to its target type, and the chosen extractors (strict or `CAST(JSON_VALUE(...))`) **error**
   on a bad value rather than silently NULLing — so a test SELECT that runs clean is strong proof the
   casts hold. If a *required* field shows unexpected NULLs, a JSON path is wrong; an *optional* field
   may be NULL where the value was absent or explicitly JSON `null` (profiling's `_absent` / `_json_null`
   counts told you which).
2. **Struct shape matches the target** — the reconstructed struct's field names, types, and order
   match the recovery column's `data_type` exactly (this is what the positional INSERT requires). On a
   **contexts** recovery `_schema_version` is also present as the first field; on an **unstruct** one,
   match whatever the validated good row showed.
3. **Row count** equals the failed-event count for this schema + app_id + source (from the
   identification query).
4. **No unexpected nulls** in `recovered` — a null usually means a wrong JSON path. Investigate.
5. **Values are corrected** — the repaired field holds the fixed value, and pass-through fields are intact.

If any check fails, fix the recovery expression and re-run the test SELECT (return to Phase 4). Only
generate the INSERT once the casts hold, the shape matches, and the values are correct. When a check
fails and the cause isn't obvious, see `troubleshooting.md`.

## Canonical atomic column set (reference only)

In BigQuery the good-vs-failed join classifies columns for you, so this list is informational — it is
the set of columns that are "atomic" (always present, pass through by name). Anything else is a
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
