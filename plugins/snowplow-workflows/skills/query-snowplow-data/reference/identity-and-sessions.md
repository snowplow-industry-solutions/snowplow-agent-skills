# Identity and sessions

**The decision this doc helps you make:** which identity column actually answers "how many users", and
whether a session-count mismatch against a GA-style tool is a bug or just a different definition of a
session.

## Identity columns

- **`user_id`** — set by the application, typically at login. NULL for anonymous traffic, so it only
  identifies users who have authenticated.
- **`domain_userid`** — a first-party cookie value, scoped per browser+device. It's cleared whenever the
  cookie is cleared, and a person using two browsers or two devices gets two different
  `domain_userid` values.
- **`network_userid`** — a cookie set by the collector, giving a server-side view of identity
  independent of client-side cookie handling.

Counting "users" as `COUNT(DISTINCT domain_userid)` **overcounts** actual people whenever someone uses
more than one browser or device — each combination gets its own value. Reconciling those into a single
person is an identity-stitching exercise (matching `domain_userid`s to a shared `user_id` or other
cross-device signal), not a matter of picking a different column to count.

## Sessions

`domain_sessionid` and `domain_sessionidx` come from the tracker's own client-side sessionization, not
from a server-side session store. Session counts from Snowplow data commonly differ from GA-style
analytics tools because the two use different timeout rules for when a session ends, and because one
resets sessions client-side (tracker-side, as Snowplow does) while the other may reset them server-side
— a mismatch is expected from the difference in sessionization logic, not necessarily a data quality bug.
