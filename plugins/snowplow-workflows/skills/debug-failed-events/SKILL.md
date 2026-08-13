---
name: debug-failed-events
description: "Diagnose individual Snowplow events failing validation — a pasted bad-row error, Micro's /bad endpoint during local testing, or bad rows surfaced from a real pipeline via Console, MCP, or a warehouse bad-rows table — categorizing schema resolution, schema validation, enrichment, and malformed-event errors with actionable fixes. For pipeline-wide health (events missing entirely, enrichment latency, loader failures) use the official snowplow plugin's troubleshooting skill. Triggers: failed events, bad rows, validation error, Micro bad endpoint, schema resolution error, event failing validation, prod bad rows."
tools:
  - get_failed_events_metrics
---

# Debug Failed Events

This skill is local-first: it assumes the failure is reproducible against Micro or that the user has pasted a bad-row payload. When the problem is production-pipeline-wide (events missing entirely, enrichment latency, loader failures) and the official `snowplow` plugin is installed, hand off to its `troubleshooting` skill instead of continuing here.

Systematically debug Snowplow events that fail validation, identify root causes, and provide actionable fixes. Works regardless of where the failed event originated — pasted error message, Snowplow Micro (local), or a real pipeline (prod/QA).

## When To Use This Skill

Use this skill when:

- The user pastes a Snowplow validation error or bad-row payload and asks what's wrong
- Events appear in Snowplow Micro's `/bad` endpoint during local testing
- A real pipeline (prod/QA) emits bad rows — surfaced via Snowplow Console UI, the Snowplow MCP `get_failed_events_metrics` tool, or a warehouse bad-rows table
- Schema validation errors occur
- Events are rejected by enrichments
- Need to diagnose why tracking implementation isn't working

Don't use this skill when:

- Events are validating successfully (no errors observed in any source)
- Need to set up initial tracking (use install-snowplow-tracking skill)
- Testing works but need to deploy to production (use implementation-guidance skill)
- No failed event data is available yet (use validate-snowplow-implementation skill first to surface it)

## Prerequisites

- A failed event is observable from at least one source: error pasted by user, Micro `/bad`, Snowplow MCP, Console UI, or pipeline bad-rows storage
- Access to the error message (and ideally the event payload)
- Schema definitions are accessible (in Console or locally)
- Basic understanding of the tracking implementation

## Instructions

### 1. Gather Failed Event Data

Pick the path that matches where the failed event came from. The downstream diagnostic logic (Steps 2–5) is identical across sources.

**Path A — User pasted an error message or bad-row payload**

Skip the fetch. Treat the pasted text as your single failed event:

- Identify the error message string (often inside `"errors": [...]` or a `"failure"` object in a bad-row JSON)
- Identify the Iglu URI if present (`iglu:vendor/name/jsonschema/M-R-A`)
- Identify the event payload (often inside `"payload"` or `"data"`)

Then jump to Step 2. If the user pasted only the error and not the payload, ask for the payload before attempting schema-validation diagnosis.

**Path B — Snowplow Micro (local testing)**

```bash
python scripts/analyze_failed_events.py --source micro --port 9090
```

Or fetch the raw events for manual inspection:

```bash
curl http://localhost:9090/micro/bad | jq
```

To browse failed events visually, open `http://localhost:9090/micro/ui` in a browser. The UI is the most reliable source of truth for Micro.

**Path C — Real pipeline (prod / QA)**

Failed events from a real pipeline can be reached several ways. Prefer them in this order:

1. **Snowplow MCP** (if available) — use `get_failed_events_metrics` with the **pipeline** ID to surface counts and recent failures. Important caveat: this tool is **pipeline-only**. If you pass a Console-hosted Micro ID it silently returns `"No failed events found"` regardless of actual state — do not use it for Micros (use Path B instead).
2. **Snowplow Console UI** — Data Quality / Failed Events view shows recent bad rows with errors and payloads.
3. **Bad-rows storage** (warehouse table, S3 bucket, etc.) — query directly when MCP/Console can't give you the payload depth you need.

Once you have one or more failed event JSON objects from any of these sources, save them to a file and analyze:

```bash
# Save MCP/Console/warehouse output as a JSON array of failed events, then:
python scripts/analyze_failed_events.py --source file --input failed_events.json
```

### 2. Categorize the Failure

Failed events fall into these categories. Identify which applies:

**Category A: Schema Resolution Errors**
- "Schema not found"
- "Registry timeout"
- "Schema lookup failed"

→ See `reference/schema_resolution_errors.md`

**Category B: Schema Validation Errors**
- "Missing required property"
- "Additional property not allowed"
- "Type mismatch"
- "Pattern validation failed"

→ See `reference/schema_validation_errors.md`

**Category C: Enrichment Failures**
- "Enrichment error"
- "API enrichment timeout"
- "Invalid enrichment configuration"

→ See `reference/enrichment_errors.md`

**Category D: Malformed Events**
- "Invalid JSON"
- "Missing required Snowplow fields"
- "Corrupt event payload"

→ See `reference/malformed_events.md`

### 3. Diagnostic Workflow

Follow the category-specific diagnostic workflow:

#### For Schema Resolution Errors:

1. **Verify schema exists**
   - Check if schema is deployed to the correct environment (DEV/PROD)
   - Verify Iglu URI matches exactly (vendor, name, version)

2. **Check registry configuration**
   - Ensure Micro/pipeline can access the Iglu registry
   - Verify registry credentials are valid
   - Test registry connectivity

3. **Validate schema version**
   - Confirm the version in tracking code matches deployed version
   - Check if schema was recently deleted or moved

**Fix Pattern:**
```bash
# Check schema deployment — returns the schema JSON if deployed
curl -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event/jsonschema/1-0-0"

# If not deployed, deploy to appropriate environment
# Then retry event
```

#### For Schema Validation Errors:

1. **Compare event data with schema**
   ```bash
   # Fetch the schema, then compare field-by-field against the failing event
   curl -H "apikey: YOUR_API_KEY" \
     "https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event/jsonschema/1-0-0" > schema.json
   jq '{required, properties: (.properties | map_values(.type))}' schema.json
   jq 'keys' failed_event.json
   ```

2. **Identify specific violation**
   - Missing required field? → Add field to tracking code
   - Extra field? → Remove from tracking code or add to schema
   - Wrong type? → Convert value to correct type
   - Pattern mismatch? → Fix value format or update schema pattern

3. **Verify fix**
   - Update tracking code
   - Re-run implementation
   - Check if event now appears in /good

**Common Patterns:**

See `reference/schema_validation_errors.md` for detailed fixes for:
- Required property missing
- Additional properties not allowed
- Type mismatches (string vs number, etc.)
- Enum violations
- Format/pattern violations
- Array/object structure errors

#### For Enrichment Failures:

1. **Identify failing enrichment**
   - Check error message for enrichment name
   - Review enrichment configuration

2. **Check enrichment prerequisites**
   - API enrichments: Verify external API is accessible
   - Lookup enrichments: Ensure lookup tables are populated
   - Custom enrichments: Check enrichment code/configuration

3. **Test enrichment in isolation**
   - API enrichments: call the external API directly (`curl -v` with the same payload the enrichment sends)
   - Other enrichments: run the event through Micro with only that enrichment enabled (see the setup-micro skill)

**Fix Pattern:**
- Update enrichment configuration
- Fix external dependencies
- Handle edge cases in event data

#### For Malformed Events:

1. **Validate JSON structure**
   ```bash
   python3 -m json.tool failed_event.json
   ```

2. **Check required Snowplow fields**
   - Ensure all required fields are present (platform, app_id, etc.)
   - Verify tracker is properly initialized

3. **Review tracking code**
   - Look for data serialization issues
   - Check for special characters or encoding problems
   - Verify event construction logic

**Fix Pattern:**
- Fix JSON serialization in tracking code
- Properly escape special characters
- Ensure complete tracker initialization

### 4. Apply Fix and Verify

1. **Update code/configuration** based on diagnosis
2. **Reset state** so the next event is observable cleanly:
   - **Micro (local):** `curl -X POST http://localhost:9090/micro/reset`
   - **Pipeline (prod/QA):** no reset needed — note the current timestamp and look only at events emitted after the fix
   - **Pasted error path:** N/A (you're not re-running, you're advising the user how to fix their tracking)
3. **Re-emit the event** from the tracking implementation
4. **Verify fix** using the same source as Step 1:
   - **Micro:** check `http://localhost:9090/micro/ui` for the event in /good, or `curl http://localhost:9090/micro/good | jq`
   - **Pipeline via MCP:** re-run `get_failed_events_metrics` against the pipeline ID and confirm the failure count has not grown
   - **Pipeline via Console:** check the Data Quality view for new bad rows after the fix timestamp
   - **Pipeline via warehouse:** query bad-rows table filtered to `collector_tstamp > <fix-time>`
5. **If still failing**, return to step 2 and re-categorize — the new error may be different from the original

### 5. Document and Prevent

After fixing:

1. **Document the issue**
   - What caused the failure?
   - What was the fix?
   - How to prevent in the future?

2. **Update tests** (if applicable)
   - Add test case for this scenario
   - Validate schema changes before deployment

3. **Share learnings**
   - Update team documentation
   - Add to common failures list

## Scripts

- `scripts/analyze_failed_events.py` — Categorize and summarize failed events from either Micro or a JSON file (any source that produced failed events: MCP, Console export, warehouse query, manual paste).
  - From Micro: `python scripts/analyze_failed_events.py --source micro --port 9090`
  - From file: `python scripts/analyze_failed_events.py --source file --input failed_events.json`
  - Run with `--help` for full usage details.

The script's `file` mode expects a JSON array of failed-event objects. Each object should have an `errors` array of `{message: ...}` entries (the same shape Micro returns). When pulling from MCP, Console, or a warehouse, reshape the output into that array before passing it in — or paste a single bad-row JSON wrapped in `[...]`.

## Reference Documentation

- `reference/schema_resolution_errors.md` - Diagnosing and fixing "schema not found" errors
- `reference/schema_validation_errors.md` - Complete guide to validation errors with examples and fixes
- `reference/enrichment_errors.md` - Enrichment failure patterns and debugging steps
- `reference/malformed_events.md` - Handling corrupt or incomplete event payloads

## Common Patterns

**Pattern 1: Schema Not Found in DEV**
```
Error: Schema iglu:com.example/event/jsonschema/1-0-0 not found
→ Schema exists but not deployed to DEV
→ Deploy schema to DEV environment
→ Retry event
```

**Pattern 2: Field Name Typo**
```
Error: Missing required property "user_id"
Event has: "userId"
→ Field name doesn't match schema (camelCase vs snake_case)
→ Update tracking code to use correct field name
→ Or update schema if field name should change
```

**Pattern 3: Wrong Data Type**
```
Error: Expected number, got string
Field: "amount": "29.99"
→ Value sent as string but schema expects number
→ Convert to number in tracking code: amount: 29.99
→ Retry event
```

**Pattern 4: Extra Properties**
```
Error: Additional property "debug_flag" not allowed
→ Field sent but not defined in schema
→ Remove field from tracking code
→ Or add field to schema and deploy new version
```

## Troubleshooting

When standard diagnostic workflow doesn't resolve the issue:

- **Intermittent failures**: usually registry timeouts or rate limits — check registry health and connectivity, not the schema itself
- **Multiple error types**: fix in pipeline order — schema resolution first, then schema validation, then enrichment
- **Schema appears correct but validation fails**: suspect caching — restart Micro (`docker compose restart micro`) or wait 1–2 minutes after a schema deployment
- **Events work in Micro but fail in pipeline**: compare environments — schema deployed to DEV but not PROD, or enrichments enabled in one but not the other

## Best Practices

1. **Fix one error type at a time** - Don't try to fix multiple issues simultaneously
2. **Verify schema first** - Most errors are schema-related; confirm schema exists and is correct
3. **Compare carefully** - Schema validation errors often stem from subtle differences (field names, types)
4. **Test incrementally** - After each fix, test immediately to confirm resolution
5. **Use scripts** - Automated analysis is faster and more accurate than manual inspection

## Limits and Alternatives

This skill focuses on debugging validation failures. It does not cover:

- **Pipeline infrastructure issues** - Use pipeline troubleshooting skill for collector/enrichment infrastructure problems
- **Performance issues** - Events arriving but slowly; use performance monitoring
- **Schema design** - Use design-tracking-plan skill for creating/modifying schemas
- **Initial implementation** - Use install-snowplow-tracking skill for setting up tracking from scratch

For production pipeline failures, this skill provides debugging methodology but may require additional pipeline-specific tools and access.
