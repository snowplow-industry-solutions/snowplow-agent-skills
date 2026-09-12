# Redshift — querying good events

**The decision this doc helps you make:** how to reach an entity's fields on Redshift correctly, so
the join back to `atomic.events` is both correct (no duplicate rows) and fast (uses the tables'
physical layout rather than fighting it).

## Column layout — the shredded model

Redshift has **no in-row entity columns**. Each entity or event schema is shredded out into its own
table — e.g. `contexts_com_acme_product_1` becomes the table `atomic.com_acme_product_1` — which you
join back to `atomic.events` to bring the entity's fields alongside the event. A schema that crossed
a major version has several such tables (`_1`, `_2`) — UNION ALL them per `schema-versions.md`.

## Join rule (correctness-critical)

Join on **both** keys, never `root_id` alone:

```sql
SELECT e.event_id, p.product_id
FROM atomic.events e
JOIN atomic.com_acme_product_1 p
  ON p.root_id = e.event_id
 AND p.root_tstamp = e.collector_tstamp
WHERE e.collector_tstamp >= DATEADD(day, -7, GETDATE());
```

Joining on `root_id` alone produces a **Cartesian product** when late-arriving duplicate events share
an `event_id` — the `root_tstamp = e.collector_tstamp` predicate is what disambiguates them, so it is
not optional.

## Physical layout

The default **dist key is the event ID**, so the join above is co-located and fast by design — no
network shuffle needed to bring `atomic.events` and a shredded entity table together. The default
**sort key is the collector timestamp**: always bound queries by `collector_tstamp` — on **both** sides
of the join — so the planner can prune blocks instead of scanning both tables in full.

## Beyond this sheet

Loader-version specifics — for example `SUPER`-typed columns on newer loaders, which change how a
shredded table's fields are typed — are a runtime docs lookup. Use `fetch-snowplow-docs` rather than
relying on this sheet.
