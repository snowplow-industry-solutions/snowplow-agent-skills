# Deduplication

**The decision this doc helps you make:** whether a query is actually deduplicated, or only looks
deduplicated because it happens to scan a window where the duplicate hasn't landed yet.

## Root cause

Snowplow trackers guarantee **at-least-once** delivery: if a tracker cannot confirm an event it already
sent successfully was received, it re-sends it. The re-sent copy shares the original's `event_id` and
every other field **except `dvce_sent_tstamp`** (the send-time), and it can arrive **days, weeks, or
even months after** the original — a network retry queued on a device, a delayed batch flush, anything
that holds an event before it finally reaches the collector. Any dedup logic scoped to a single day's
partition or a narrow date window will miss duplicates that land outside that window; it is not a safe
substitute for deduping on identity.

## Canonical pattern

Dedup on `event_id`, keeping the earliest send:

```sql
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY event_id
      ORDER BY dvce_sent_tstamp
    ) AS rn
  FROM atomic.events
  WHERE derived_tstamp >= '2026-08-01'   -- plus your warehouse's partition/sort predicate
)
SELECT * FROM deduped WHERE rn = 1;
```

`rn = 1` keeps the tracker's first send; any row with `rn > 1` is a duplicate re-send of the same event.

## Order of operations

Dedup **before** joining or unnesting entities, not after. Each duplicate row fans out across every
entity it carries, so deduping downstream of a join or unnest multiplies the duplicates instead of
removing them — you'd need to dedup again post-join, and by a different key.

## Redshift variant

On Redshift, entities live in separate shredded tables, not in-row arrays. Dedup `atomic.events` first,
then join the (still-deduplicated) result to each child table on `root_id` **and** `root_tstamp` — see
`reference/dialect-redshift.md` for the exact join. The child tables carry the same duplicate rows as
`atomic.events`, so joining a deduplicated `atomic.events` against an un-deduplicated child table
reintroduces the duplicates from the child side.
