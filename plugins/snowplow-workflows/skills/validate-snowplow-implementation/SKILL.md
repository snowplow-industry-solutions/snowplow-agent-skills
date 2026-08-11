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

- Micro is not running (run setup-micro skill first)
- Testing against DEV/PROD pipeline (use pipeline troubleshooting instead)
- Designing schemas (use tracking-design skill)
- Need to add new events to existing tracker (use implementation-guidance skill)

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

**3.1 Instruct User to Trigger Events**

Provide clear instructions for generating test events:

- **Web**: "Open your application in a browser and navigate to trigger the events"
- **iOS**: "Build and run the app in a simulator or device, then navigate through the app"
- **Android**: "Build and run the app in an emulator or device, then navigate through the app"

**3.2 Alternative: Use Test Script**

If the tracker is web-based and testing basic events, offer to use the test script:

```bash
python scripts/send_test_event.py --port 9090 --event page_view
```

This sends a simple test event directly to Micro for quick validation.

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

**4.2 Analyze Results**

The script will report:
- **Count of good events**: Events that passed validation
- **Count of bad events**: Events that failed validation
- **Sample event data**: First few events from each endpoint
- **Validation errors**: Why events failed (if any bad events exist)

### 5. Diagnose Issues

**If bad events exist:**

Call the `debug-failed-events` skill to systematically diagnose and fix validation errors. This skill provides:
- Automated error categorization and analysis
- Step-by-step diagnostic workflows
- Detailed fixes for each error type
- Reference documentation for complex cases

The debug-failed-events skill will:
1. Analyze failed event data from Micro
2. Categorize errors (schema resolution, validation, enrichment, malformed)
3. Provide category-specific diagnostic workflows
4. Suggest actionable fixes
5. Guide through verification

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
- The `debug-failed-events` skill (called in step 5) will provide detailed diagnosis
- Follow the fixes suggested by debug-failed-events skill
- After applying fixes, return to step 3 to re-test

**If no events appear:**
- Implementation issue - events not reaching Micro
- See `troubleshooting/implementation_issues.md`
- Common causes: tracker not initialized, wrong endpoint, network issues
- After fixing, return to step 3 to re-test

### 7. Iterate

After fixes are applied:
- Re-run the application to generate new test events
- Re-check good/bad endpoints
- Repeat until all events validate successfully

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

- **Deploy schemas**: Use tracking-design skill or Console to deploy schemas to DEV/PROD
- **Test in live pipelines**: After Micro validation succeeds, test in DEV pipeline using pipeline-infrastructure skill
- **Debug complex enrichment issues**: Micro has limited enrichment support. For enrichment issues, test in DEV pipeline.
- **Performance testing**: Micro is for functional testing only, not load testing

**After successful validation:**
1. Deploy schemas to DEV (if using custom schemas)
2. Update tracker collector endpoint to DEV pipeline
3. Test events flow through DEV pipeline
4. Deploy schemas to PROD
5. Update tracker collector endpoint to PROD pipeline

For production deployment workflow, consult the implementation-guidance skill Stage 4-5.
