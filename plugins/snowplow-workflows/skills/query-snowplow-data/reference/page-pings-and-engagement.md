# Page pings and engagement

**The decision this doc helps you make:** whether an event count includes page pings by mistake, and
how to turn ping counts into an engaged-time figure instead of a page-view figure.

## Page pings are heartbeats, not page views

A page ping (`event_name = 'page_ping'`) is emitted on a fixed interval while the user is active on the
page — it is a heartbeat, not a distinct user action. **Never count page pings as page views.** Filter
them out of event counts by default:

```sql
SELECT *
FROM atomic.events
WHERE event_name != 'page_ping';
```

Any event-count metric that doesn't explicitly exclude `page_ping` will be inflated by however many
heartbeats fired during the session, not just the actions the user actually took.

## Engaged-time pattern

Two tracker configuration values drive the calculation, both set in `enableActivityTracking(...)`:
`minimumVisitLength` (the delay before the **first** ping fires) and `heartbeatDelay` (the interval
between every **subsequent** ping). They are configuration, not constants — ask the user or check
the tracker configuration for the actual values rather than assuming defaults.

```
-- pseudo-code: epoch_seconds() stands for the dialect's epoch extraction
engaged_time = heartbeat * (n_distinct_ping_buckets - 1) + min_visit_length
n_distinct_ping_buckets = COUNT(DISTINCT FLOOR(epoch_seconds(dvce_created_tstamp) / heartbeat))
```

Two details make this formula right where a naive `ping count * heartbeat` is wrong:

- **Bucketing, not counting rows:** flooring each ping's `dvce_created_tstamp` epoch by the
  heartbeat groups imperfectly timed pings and duplicates into the interval they belong to, so each
  interval counts once no matter how many pings landed in it.
- **The `- 1`:** the first bucket is paid for by the `min_visit_length` term (that's the delay that
  triggered its ping), not by a heartbeat interval — charging every bucket the full heartbeat price
  overstates engaged time.

Reference implementation: dbt-snowplow-unified's
[`snowplow_unified_pv_engaged_time.sql`](https://github.com/snowplow/dbt-snowplow-unified/blob/6df7562dbc963d13d58f75d39ca2e3ab2de7d41b/models/views/scratch/snowplow_unified_pv_engaged_time.sql).
