# Dialect pack — Snowflake

Load this in Phase 1 once the warehouse is Snowflake. Shared concepts (failure model, navigation,
classification, the gates) are in `reference/failure-context.md`; the runnable SQL is in
`templates/snowflake.md`.

## Dialect at a glance

| Concept | Snowflake |
|---|---|
| Table qualifier | `database.schema.table` (three-part) |
| Grounding source (recovery-column type) | a **validated good row** (VARIANT — no DDL type to read) |
| Failure-array expand | `LATERAL FLATTEN(input => ...) f` |
| Read a `data` scalar | `f.value:data:field::TYPE` (the payload is under `data` — `f.value:field` is NULL) |
| Cast | `::TYPE`; `TRY_CAST` in profiling |
| contexts reconstruction | `ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(...))`, `_schema_version` first |
| unstruct reconstruction | `OBJECT_CONSTRUCT(...)`, no array, no `_schema_version` |
| Profiling probe (non-erroring) | `LISTAGG(DISTINCT TYPEOF(...))` + `TRY_CAST` + `COUNT_IF` |
| Validation signal | `TYPEOF()` on the built VARIANT (build `recovered` in a CTE first — `TYPEOF` needs a VARIANT, not a `::TYPE` scalar) |
| Staging create | `CREATE TABLE ... LIKE` |
| Time travel | `AT (TIMESTAMP => ...)` |
| Lookback date-math | `load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'` |
| INSERT-build mechanism | in-warehouse generator (`\|\|` concat + `LISTAGG(...) WITHIN GROUP`) |
| Recovery-expr escaping (generator string) | double single quotes (`''`) |
| Good-entity array index | `[0]` |

**Snowflake is schemaless.** Entity columns are VARIANT, so there is **no** strict struct-type contract:
no field-order requirement, no reserved-word quoting, no Hive→type conversion. The keys in
`OBJECT_CONSTRUCT` are plain string literals. Ground the target types from a **validated good row**
(read its fields' `TYPEOF`), since there is no DDL type to read — this is the one place the flow's
"grounding source" isn't a metadata type.

## Column classification, the profiling decision & the validation gate

**The decision this doc helps you make:** what the INSERT-generator does with every column, whether
the whole failed population shares one recovery (the Phase-3.5 profiling gate), and whether the
reconstructed entity is correct enough to promote (the Phase-5 validation gate). This is the judgment
layer behind the INSERT-generator template in `templates/snowflake.md`.

## No strict struct typing (the key Snowflake contrast)

Unlike BigQuery/Athena, Snowflake entity columns are semi-structured `ARRAY`/`VARIANT`, not native
structs. So the reconstruction has **no field-order requirement and no reserved-word quoting** — the
keys in `OBJECT_CONSTRUCT(...)` are plain string literals, and you cast each value with `::TYPE`
(e.g. `::INTEGER`, `::STRING`, `::BOOLEAN`). There is **no** Hive→engine type conversion. The one
mandatory key is `_schema_version`, first, for the Snowflake Streaming Loader.

## Column classification (what the generator does, per column)

For the INSERT, every column in the **good** events table is classified. The generator query joins
`good` and `failed` `INFORMATION_SCHEMA.COLUMNS` and, per column in good-table `ordinal_position`
order, decides:

1. **The failure column** (`contexts_com_snowplowanalytics_snowplow_failure_1`) → `CAST(NULL AS ...)`
   — kept in position (positional INSERT), always null in recovered rows. *Why null:* re-carrying the
   failure context into the good table would contaminate it.
2. **`load_tstamp`** → `CURRENT_TIMESTAMP()` — a fresh timestamp for reprocessed rows.
3. **The recovery column** (the entity being repaired) → the confirmed
   `ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(...))` expression.
4. **Column present in both good and failed tables** → pass through by name. This covers all atomic
   columns *and* any custom column that holds values for events which failed on a *different* entity.
5. **Column only in the good table** → `CAST(NULL AS <target_data_type>)`.

Because the failed events table already contains every atomic column, the good-vs-failed join does
the atomic-vs-custom classification for you — there is **no separate atomic list to maintain** and no
Hive→engine type conversion. The canonical atomic set is retained at the bottom of this file for
reference only.

## Confirming coercibility (the Phase-3.5 profiling gate)

Do **not** build the recovery expression on faith. Run the profiling query (`templates/snowflake.md`)
to learn, per field across *all* failed rows, the VARIANT types present (`TYPEOF`) and whether every
value casts to the target type (`TRY_CAST`, which can't error). Decide per field, in order:

1. **Any field has `_uncoercible > 0`** → the failed rows don't share one recovery; some values can't
   become the target type. Stop, surface the offending rows, and partition/scope with the user. Don't
   suggest a recovery expression yet.
2. **Any field has `_absent > 0`** → it's missing from some rows: partition those off if the schema
   requires the field; if optional, the cast returns NULL for them (fine).
3. **Once every field is coercible** → the population is uniform; build the expression. Snowflake's
   `::TYPE` cast coerces both native and string-encoded values, and profiling has confirmed none will
   error, so the built expression is guaranteed to run clean.

**Never use `TRY_CAST` in the recovery expression itself** — it hides an un-coercible value as a
silent NULL. `TRY_CAST` belongs only in the profiling query, where its non-erroring behaviour is the
whole point.

## The validation gate (Phase 5 — do not skip)

Confirm all of these against the pasted test-SELECT output before generating the INSERT:

1. **The query ran clean (decisive).** Every `::TYPE` cast succeeded — Snowflake errors on a bad cast
   rather than silently returning null, so a successful run is strong evidence the types match (and
   Phase 3.5 already proved coercibility).
2. **Field types** — each `TYPEOF()` on a reconstructed field returns the intended type
   (e.g. `INTEGER`, `VARCHAR`, `BOOLEAN`), and `_schema_version` is present in the reconstructed object.
3. **Row count** equals the failed-event count for this schema + app_id (from the identification query).
4. **No unexpected nulls** in `recovered` — a null usually means a wrong `:` path. Investigate.
5. **Values are corrected** — the repaired field holds the fixed value, and pass-through fields are intact.

If any check fails, fix the recovery expression and re-run the test SELECT (return to Phase 4). Only
generate the INSERT once the casts hold and the values are correct. When a check fails and the cause
isn't obvious, see `troubleshooting.md`.

## Canonical atomic column set (reference only)

In Snowflake the good-vs-failed join classifies columns for you, so this list is informational — it
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
