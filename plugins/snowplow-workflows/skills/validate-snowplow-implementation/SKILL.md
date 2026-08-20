---
name: validate-snowplow-implementation
description: "Test and validate a Snowplow tracking implementation against Micro — check good/bad event counts, inspect attached entities, and surface validation errors and common implementation issues before deploying to production. Use after instrumenting or changing tracking code. Triggers: validate tracking, verify implementation, check events in Micro, good bad events, test tracking."
---

# Validate Snowplow Implementation

Validate Snowplow tracking implementations by testing against a local Micro instance, identifying validation errors, and providing actionable feedback.

## When To Use This Skill

Use this skill when:

- Testing a newly implemented Snowplow tracker
- Validating tracker sends events successfully
- Debugging why events are appearing in Micro's /bad endpoint
- Verifying event structure matches schema requirements
- Checking tracking implementation before moving to DEV/PROD

Don't use this skill when:

- No tracking implementation exists yet (use install-snowplow-tracking skill first)
- Testing against DEV/PROD pipeline (use the official snowplow plugin's troubleshooting skill instead)
- Designing schemas (use design-tracking-plan skill)
- Need to add new events to existing tracker (use the official snowplow plugin's implementation-guidance skill)

## Prerequisites

- Snowplow tracking implementation exists in the application
- Micro instance is running and accessible
- Tracker is configured to send events to Micro endpoint
- Application can be run/executed to generate test events

## Instructions

### 1. Verify Micro is Running

Check that Micro is accessible and responding:

```bash
python scripts/check_micro_status.py --port 9090
```

If Micro is not running:
- Run the setup-micro skill first, or
- Start existing Micro instance: `docker compose up -d`

### 2. Identify Test Events

Ask the user which events they want to test. Common options:

**For Web/JavaScript:**
- Page view events (visit a page)
- Click events (click links/buttons)
- Form events (interact with forms)

**For iOS/Android:**
- Screen view events (navigate to a screen)
- App lifecycle events (app open/close)
- Custom events (trigger specific user actions)

If they're unsure, recommend testing the most basic event first (page view or screen view).

### 3. Generate Test Events

The validation loop is: **reset Micro → exercise triggers → read `/micro/good` and `/micro/bad` → compare against the expected event list from step 2.** Steps 3–4 are one pass through that loop.

**3.1 Reset Micro**

Start from a clean slate so every event you read back is attributable to this run:

```bash
curl -X POST http://localhost:9090/micro/reset
```

**3.2 Drive the Application Yourself**

Drive the application with whatever browser automation is available — a webapp-testing skill, a Playwright or Chrome DevTools MCP server, or a scripted driver — and exercise every trigger on the expected event list: navigate the pages, click the buttons, submit the forms. For iOS/Android, drive the simulator/emulator the same way where tooling allows. This step is complete when every expected event has had its trigger exercised.

**3.3 Fallbacks — only when no automation is available**

- Ask the user to exercise each trigger in the application and tell you when done.
- For web trackers, `python scripts/send_test_event.py --port 9090 --event page_view` sends a synthetic event directly to Micro — useful to confirm the Micro plumbing works, but it does not exercise the application's own tracking code.

### 4. Check Event Status

**4.1 Query Micro Endpoints**

Run the validation script to check good and bad events:

```bash
python scripts/check_good_bad.py --port 9090
```

This queries:
- `/micro/good` - Successfully validated events
- `/micro/bad` - Events that failed validation

Alternatively, open `http://localhost:9090/micro/ui` in a browser to manually inspect events and validation errors.

For ad-hoc inspection of the raw JSON, use the `jq` one-liners in the setup-micro skill's "Reading Micro Output" section — they keep the transcript reviewable and re-runnable.

**4.2 Analyze Results**

The script will report:
- **Count of good events**: Events that passed validation
- **Count of bad events**: Events that failed validation
- **Sample event data**: First few events from each endpoint
- **Validation errors**: Why events failed (if any bad events exist)

Compare the results against the expected event list from step 2. Validation is complete only when every expected event appears in `/micro/good` and `/micro/bad` is empty.

### 5. Diagnose Issues

**If `/micro/bad` is non-empty: invoke the `debug-failed-events` skill before editing any code.**

This is a gate, not a suggestion. That skill owns the error categorization table (schema resolution, schema validation, enrichment, malformed) and the category-specific fixes — apply it rather than re-deriving the diagnosis inline, so every bad row gets categorized consistently.

**If no events appear (neither good nor bad):**

This indicates a tracker/implementation issue, not a validation problem:

- **Check tracker initialization**: Verify collector endpoint configuration
- **Verify tracking calls**: Ensure application executes tracking code
- **Check network**: Use browser/device debugger to see if requests are sent
- **Verify Micro accessibility**: Ensure Micro is reachable from application

See `troubleshooting/implementation_issues.md` for detailed guidance on:
- Events not reaching Micro (endpoint misconfigured)
- Tracker not properly initialized
- Plugin not installed or configured
- Context not attached or malformed

### 6. Provide Feedback and Next Steps

Based on the validation results:

**If all events are good:**
- ✓ Implementation is working correctly
- All events passed schema validation
- Recommend next steps:
  1. Deploy schemas to DEV (if using custom schemas)
  2. Update collector endpoint to DEV pipeline
  3. Test in DEV pipeline
  4. After DEV validation, deploy to PROD

**If bad events exist:**
- Failed events detected - debugging required
- The `debug-failed-events` skill (invoked at the step 5 gate) provides the diagnosis
- Follow the fixes suggested by debug-failed-events skill
- After applying fixes, return to step 3 to re-test

**If no events appear:**
- Implementation issue - events not reaching Micro
- See `troubleshooting/implementation_issues.md`
- Common causes: tracker not initialized, wrong endpoint, network issues
- After fixing, return to step 3 to re-test

### 7. Iterate

After fixes are applied, run the loop again: reset Micro, exercise the triggers (step 3), read good/bad, compare against the expected list. Repeat until every expected event is in `/micro/good` and `/micro/bad` is empty.

## Scripts

- `scripts/check_micro_status.py` - Verify Micro is running and accessible
  Usage: `python scripts/check_micro_status.py --port 9090`

- `scripts/check_good_bad.py` - Query Micro's /good and /bad endpoints for event status
  Usage: `python scripts/check_good_bad.py --port 9090 [--show-details]`

- `scripts/send_test_event.py` - Send a simple test event directly to Micro (web only)
  Usage: `python scripts/send_test_event.py --port 9090 --event page_view`

Run any script with `--help` for full usage details.

## Reference Documentation

- `reference/validation_errors.md` - Common Iglu validation errors, causes, and fixes
- `reference/micro_endpoints.md` - Understanding Micro's API endpoints and response formats

## Common Issues

- **No events appearing**: Tracker may not be sending to Micro endpoint. Check tracker configuration in code. See `troubleshooting/implementation_issues.md`.

- **All events in /bad**: Usually schema not found in Iglu registry. Ensure schemas are deployed to DEV. See `reference/validation_errors.md`.

- **Events validate locally but fail in DEV**: Schema versions may differ between Micro and DEV. Ensure Micro is using DEV schemas.

- **Can't access Micro endpoints**: Verify Micro is running (`docker ps`). Check port configuration matches tracker endpoint.

## Limits and Next Steps

This skill validates implementations against a local Micro instance. It does not:

- **Deploy schemas**: Use design-tracking-plan skill or Console to deploy schemas to DEV/PROD
- **Test in live pipelines**: After Micro validation succeeds, test in DEV pipeline using the official snowplow plugin's pipeline-infrastructure skill
- **Debug complex enrichment issues**: Micro has limited enrichment support. For enrichment issues, test in DEV pipeline.
- **Performance testing**: Micro is for functional testing only, not load testing

**After successful validation:**
1. Deploy schemas to DEV (if using custom schemas)
2. Update tracker collector endpoint to DEV pipeline
3. Test events flow through DEV pipeline
4. Deploy schemas to PROD
5. Update tracker collector endpoint to PROD pipeline

For production deployment workflow, consult the official snowplow plugin's implementation-guidance skill.
