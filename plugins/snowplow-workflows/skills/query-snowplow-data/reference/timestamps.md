# Timestamps

**The decision this doc helps you make:** which of `atomic.events`' several timestamp columns to filter
and order by for a given purpose, and why the column a table is physically organised on is often not
the column your analysis logic should filter on.

## Which timestamp to use

| Column | What it is | When to use it |
|---|---|---|
| `derived_tstamp` | Snowplow's corrected event time — adjusts for device clock skew | The default for analysis: "when did this event actually happen" |
| `collector_tstamp` | When the event reached the collector | Redshift's default sort key — bound queries by this for performance, see `reference/dialect-redshift.md` |
| `dvce_created_tstamp` | Device-reported creation time | Raw device-clock value; can be skewed, which is exactly what `derived_tstamp` corrects for |
| `dvce_sent_tstamp` | Device-reported send time | Orders duplicate re-sends of the same `event_id` — see `reference/deduplication.md` |
| `etl_tstamp` | When enrichment processed the event | Enrichment-time diagnostics, not event-time analysis |
| `load_tstamp` | When the row landed in the warehouse | Typical BigQuery partition column — see `reference/dialect-bigquery.md` |

## The mismatch trap

Tables are commonly partitioned or sorted for load efficiency on `load_tstamp` or `collector_tstamp` —
not on the timestamp analysis actually cares about, `derived_tstamp`. Filtering only on `derived_tstamp`
against such a table means the engine can't prune on its physical layout, and on BigQuery with a
mandatory partition filter it's a hard error rather than just a slow scan.

Carry **both** predicates: the physical-layout column the table is organised on, and `derived_tstamp` for
the actual analysis window. See `reference/dialect-bigquery.md` for the mandatory partition filter and
`reference/dialect-redshift.md` for the sort-key predicate.
