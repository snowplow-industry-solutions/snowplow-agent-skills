# Bot filtering

**The decision this doc helps you make:** which signals are actually available to separate bot traffic
from real users in a given dataset, and why a filter that works on one site's data can be silent (or
wrong) on another's.

## Starting point

Column names and enrichment/plugin setup for bot filtering change over time and across deployments —
don't rely on built-in knowledge of exact column names here. Before writing any bot-filtering query,
fetch `https://docs.snowplow.io/docs/events/filtering-bot-events/` at runtime, via the
`fetch-snowplow-docs` skill or a direct fetch, and use it for the current column names and the
enrichment/plugin setup it depends on.

## Signals, in order of preference

Prefer enrichment-derived signals over inferring bot-ness from raw behaviour:

1. **IAB Spiders & Robots context** — enrichment-derived classification against a known bot/spider list.
2. **YAUAA context** — user-agent parsing that can surface non-browser or bot-like clients.
3. **IP/ASN lookup** — enrichment-derived network ownership, useful for known hosting/datacenter ranges.
4. **Client-side bot-detection plugin's context** — only present when that tracker plugin is enabled in
   the tracking setup.

Each of these is a column that **only exists if its enrichment or plugin was turned on** — and even
where it's on today, it is **absent on events collected before it was enabled**. Any filter logic built
on these columns must tolerate NULL or entirely missing contexts on historical data, not assume the
column is always populated.

## Behavioural traits — exploratory, not hard-coded

Beyond the enrichment signals, behavioural traits can point at bot traffic: thousands of events from a
single IP, bursts of events sharing an identical timestamp, or high event volume paired with near-zero
engaged time. Treat these as the starting point for an **exploratory analysis you run together with the
user** — look at the site's actual distribution and agree thresholds with them — never as hard-coded
filter rules. What counts as "thousands of events from one IP" or "near-zero engaged time" is
site-specific: a high-traffic news site and a small ecommerce site have completely different normal
ranges, and a threshold copied from one will misclassify real users on the other.
