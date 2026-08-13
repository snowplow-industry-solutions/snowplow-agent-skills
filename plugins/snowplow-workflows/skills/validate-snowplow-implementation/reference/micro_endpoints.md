# Micro Endpoints Reference

Understanding Snowplow Micro's API endpoints and response formats for testing and validation.

## Core Endpoints

### /micro/good

Returns all events that passed schema validation.

**Request:**
```bash
curl http://localhost:9090/micro/good
```

**Response:**
```json
[
  {
    "event": {
      "event": "page_view",
      "app_id": "my-app",
      "platform": "web",
      "event_id": "abc-123",
      // ... full event payload
    },
    "eventType": "page_view",
    "schema": null,
    "contexts": [],
    "timestamp": "2024-05-12T10:30:00.000Z"
  }
]
```

### /micro/bad

Returns all events that failed validation with error details.

**Request:**
```bash
curl http://localhost:9090/micro/bad
```

**Response:**
```json
[
  {
    "collectorPayload": "...",
    "errors": [
      {
        "level": "error",
        "message": "Schema iglu:com.example/event/jsonschema/1-0-0 not found"
      }
    ],
    "timestamp": "2024-05-12T10:30:00.000Z"
  }
]
```

### /micro/reset

Clears all stored good and bad events. Useful for starting fresh between test runs.

**Request:**
```bash
curl -X POST http://localhost:9090/micro/reset
```

**Response:**
```
Micro state reset
```

### /micro/ui

Browser-based UI for manually inspecting events. Useful for exploring event payloads and validation errors without querying the API directly.

**Access:** Open `http://localhost:9090/micro/ui` in your browser.

Provides a visual list of good and bad events, full event payload inspection, and validation error details.

### /micro/all

Returns both good and bad events in a single response.

**Request:**
```bash
curl http://localhost:9090/micro/all
```

**Response:**
```json
{
  "good": [ /* array of good events */ ],
  "bad": [ /* array of bad events */ ]
}
```

## Response Structure

### Good Event Structure

Each event in `/micro/good` contains:

- `event`: Full event payload with all Snowplow fields
  - `event`: Event type (page_view, struct, unstruct, etc.)
  - `app_id`: Application identifier
  - `platform`: Platform (web, mob, srv, etc.)
  - `event_id`: Unique event identifier
  - `user_id`: User identifier (if set)
  - `domain_userid`: Client cookie ID
  - `unstruct_event`: Self-describing event JSON (for custom events)

- `eventType`: Simplified event type label
- `schema`: Iglu schema URI (for self-describing events)
- `contexts`: Array of context entities attached to the event
- `timestamp`: When Micro received the event

### Bad Event Structure

Each event in `/micro/bad` contains:

- `collectorPayload`: Raw payload received by Micro (base64 encoded)
- `errors`: Array of validation errors
  - `level`: Error severity (error, warning)
  - `message`: Human-readable error description
- `timestamp`: When Micro received the event

## Query Parameters

Some endpoints support query parameters for filtering:

### Filter by Event Type

```bash
curl http://localhost:9090/micro/good?event_type=page_view
```

Returns only page_view events from the good events.

### Limit Results

```bash
curl http://localhost:9090/micro/good?limit=10
```

Returns only the first 10 good events.

## Using Endpoints for Testing

### Test Workflow

1. **Reset Micro** before each test run to start with a clean state:
   ```bash
   curl -X POST http://localhost:9090/micro/reset
   ```

2. **Generate events** by running your application or sending test events

3. **Check good events** to verify successful tracking:
   ```bash
   curl http://localhost:9090/micro/good
   ```

4. **Check bad events** to identify validation errors:
   ```bash
   curl http://localhost:9090/micro/bad
   ```

5. **Analyze errors** and fix implementation

6. **Repeat** from step 1

### Automated Testing Scripts

This skill provides scripts that wrap these endpoints:

```bash
# Check good/bad event counts and show samples
python scripts/check_good_bad.py --port 9090

# Show full event details
python scripts/check_good_bad.py --port 9090 --show-details

# Reset Micro state
curl -X POST http://localhost:9090/micro/reset
```

## Event Fields to Check

When validating good events, verify:

- **app_id**: Matches configured application ID
- **platform**: Correct platform identifier (web, mob, srv, etc.)
- **event**: Correct event type
- **unstruct_event**: For custom events, check schema URI and data payload
- **contexts**: For entities, verify all expected contexts are attached
- **user_id**: Set if user identification is configured
- **domain_userid**: Present for web tracking (client cookie)

## Troubleshooting with Endpoints

### No Events Appearing

If both `/micro/good` and `/micro/bad` return empty arrays:
- Tracker may not be sending to Micro endpoint
- Check tracker initialization (collector endpoint configuration)
- Verify network requests in browser/device debugger
- Ensure Micro is accessible from application (not blocked by firewall/network)

### All Events in /bad

If all events appear in `/micro/bad`:
- Usually indicates schema not found in Iglu registry
- Check error messages for specific validation failures
- Verify schemas are deployed to DEV environment
- Ensure Micro is configured with correct Iglu registry

### Unexpected Event Structure

If good events don't have expected fields:
- Check tracker configuration (plugins, settings)
- Verify OOTB event tracking is enabled (for page views, clicks, etc.)
- Ensure custom events use correct tracking method (trackSelfDescribingEvent)

## Additional Resources

For more details on Micro's capabilities:
- Fetch Snowplow Micro documentation using `fetch_documentation_page` with path `/docs/testing-debugging/snowplow-micro/`
