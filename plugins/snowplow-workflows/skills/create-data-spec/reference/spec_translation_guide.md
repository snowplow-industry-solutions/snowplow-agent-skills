# Spec Translation Guide

The judgment this skill runs on: how to read a PRD for the events it implies, how granular to make them, how to prove a KPI is actually computable, and the failure modes PM-written specs arrive with. Read this before extracting an event or KPI under either entry point of `create-data-spec`.

## Finding the Events Hiding in PRD Language

PRD prose rarely says "track an event here." It describes the product, and the events are implicit in three kinds of sentence:

- **State changes** — "the cart moves to `abandoned` after 30 minutes idle," "a subscription lapses at the end of the billing period." Each transition is a candidate event (`cart_abandoned`, `subscription_lapsed`), even though the sentence never uses the word "event."
- **User decisions** — "the shopper can choose to save the item for later," "the admin approves or rejects the request." A decision with more than one outcome is at least one event per outcome (`item_saved_for_later`; `request_approved` and `request_rejected`, not one `request_reviewed` event that hides which way it went).
- **System outcomes** — "a discount is applied automatically at checkout," "the system retries the failed charge up to three times." Outcomes the product produces on its own are as trackable as ones the user triggers (`discount_applied`, `charge_retried`) — don't restrict candidate events to user-initiated actions.

Read every sentence describing behaviour, not just the ones under a "Tracking" or "Analytics" heading — most PRDs don't have one, and the events are scattered through the feature description instead.

## Choosing Event Granularity

One event per decision point, not per click. A decision point is a moment where the outcome could plausibly have gone another way and someone downstream needs to know which way it went.

- **Too fine**: an event per keystroke or per field change in a multi-field form. Nobody's KPI is computed from individual field edits, and the volume drowns the signal. Capture the decision — `form_submitted` — not the mechanics of filling it in.
- **Too coarse**: a single `checkout_completed` event standing in for the whole checkout flow. If the KPI is where shoppers drop off, one event can't answer it — each stage that can fail on its own (`shipping_selected`, `payment_submitted`, `order_confirmed`) needs its own event.

The test: if two different business questions need to distinguish between two moments, they're two events, even if a single UI screen produces both.

## The KPI-Computability Test

A KPI belongs in a data spec only once you can write its formula entirely in terms of named events already in the Events table. Run every KPI through this test before it leaves the spec:

1. Write the KPI's formula as a ratio or aggregate over event occurrences.
2. Check that every event the formula references has a row in the Events table.
3. If an event is missing, the KPI is unfinished — add the event or drop the KPI. Never leave the formula in prose without the events that back it.

**Worked example.** The spec names "checkout conversion" as a KPI with the definition "the share of shoppers who complete checkout after starting it." Written as a formula, that's:

```
checkout_conversion = count(complete_checkout) / count(start_checkout)
```

Both `complete_checkout` and `start_checkout` must be rows in the Events table — the metric needs a denominator (people who started) as much as a numerator (people who finished). A spec that lists `complete_checkout` alone passes a casual read but fails the test: there is no event to divide by, so the KPI cannot actually be computed from the spec as written. The fix is adding `start_checkout` to the Events table, not rewording the KPI definition.

## Common PM-Spec Failure Modes

**Vanity events with no KPI.** An event makes it into the spec because it seemed worth knowing — `page_viewed`, `button_hovered` — but no KPI in the table computes from it and no open question depends on it. Fix: for every event, name the KPI or question row that consumes it; if none exists, drop the event or attach it to a real one.

**Missing failure-path events.** The spec tracks the success path (`payment_completed`) and stops there, so nothing distinguishes "never tried" from "tried and failed" — a drop-off KPI can't tell which stage lost the user. Fix: for every stage that can fail independently, add the failure event (`payment_failed`) alongside the success event, not just a single outcome event with a status property buried inside it.

**Entities modelled as event properties.** The same object's fields — `product_id`, `product_name`, `product_price` — get repeated as properties on `view_product`, `add_to_cart`, and `remove_from_cart` instead of being pulled out as a `product` entity attached to all three. Fix: any field set that recurs across more than one event is an entity, not a property; only fields specific to a single event stay as properties on that event.
